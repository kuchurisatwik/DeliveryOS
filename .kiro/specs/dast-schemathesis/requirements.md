# Requirements Document

## Introduction

Phase 4 of the DAST pipeline integrates Schemathesis as a dynamic scanner into the
existing standalone DAST service (built in Phases 1–3). Where nuclei answers "are we
exposed to anything already publicly known?" and ZAP answers "does *our own code*
have injection, XSS, or access-control flaws?", Schemathesis answers "does our API
behave the way its OpenAPI spec promises?". It reads the target's OpenAPI schema and
generates thousands of valid and deliberately malformed requests, then checks the
responses. An unhandled 500 is a security finding, not just a bug — it means
unvalidated input reached our code and usually leaked a stack trace. Schemathesis
also catches endpoints that answer without authentication and responses that violate
their own declared schema.

Schemathesis carries a second payoff unique to this phase: it is run **through ZAP as
an HTTP proxy**. One execution yields two results — Schemathesis reports its own
failing cases, and ZAP's site tree fills with real, authenticated, valid traffic for
ZAP's active scanner to work on. The difference matters: ZAP guessing `id=1` mostly
gets 404s, while a request carrying an ID that actually exists reaches real business
logic. This makes the ZAP integration from Phase 3 materially more effective at the
same time.

This feature MUST fit the existing architecture rather than reinvent it. The
Schemathesis integration reuses the `DastAdapter` protocol, `DastScope`,
`ScanOutcome`, `ToolActivity`, `ToolCoverage`, and the shared `Finding` model; plugs
into the two-tier runner (`dast/runner.py` `default_adapters(profile)` / `run_scan`);
and sends its findings through the same normalize → dedupe → baseline chain with
stable `finding_id`s that nuclei and ZAP already use. Schemathesis is part of the fast
profile (~5 minutes, staging), so its output must feed the same Phase 2 liveness/trust
model that keeps "zero findings" honest: real request evidence drives
complete/incomplete, and an unreachable or failed run yields `incomplete`, never a
false clean.

## Glossary

- **DAST_Service**: The standalone FastAPI service that queues and runs dynamic scans
  against a running target. The system under specification.
- **Schemathesis_Adapter**: The new adapter component that implements the
  `DastAdapter` protocol and drives Schemathesis against the target's API. The primary
  subject of these requirements.
- **Runner**: The existing DAST runner (`dast/runner.py`) that splits adapters into
  read-only (concurrent) and mutating (serial) tiers via each adapter's `mutating`
  flag, and aggregates findings and coverage.
- **DastScope**: The existing input model describing what to scan: `target_url`,
  `commit_sha`, `auth_header`, `spec_paths`, and `profile`.
- **ScanOutcome**: The existing per-tool output model carrying `findings` and a
  `ToolActivity` record.
- **ToolActivity**: The existing evidence model recording `units_executed`,
  `requests_made`, `request_errors`, `timeouts`, `exit_code`, and `duration_seconds`.
- **ToolCoverage**: The existing per-tool status model recording `status`
  (`complete` | `incomplete`), `reason`, and `activity`.
- **Finding**: The shared finding model imported from the SAST package, carrying a
  scanner name, `rule_id`, web location, severity, message, and raw payload.
- **Finding_Id**: The stable hash of `(rule_identity, endpoint_identity)` produced by
  the shared normalize chain, used for deduplication and baseline diffing.
- **OpenAPI_Schema**: The target's OpenAPI specification, referenced either by URL
  (derived from `target_url` + the configured OpenAPI path) or by file, from which
  Schemathesis generates requests.
- **Base_URL**: The base URL of the running target that generated requests are sent
  to, carried on `DastScope.target_url`.
- **Auth_Header**: The full `Authorization` header value carried on
  `DastScope.auth_header`, attached to every outgoing Schemathesis request.
- **ZAP_Proxy**: The Phase 3 ZAP sidecar acting as an HTTP proxy through which
  Schemathesis routes its traffic, so ZAP observes and maps every request.
- **Generated_Case**: One request Schemathesis generates from the OpenAPI_Schema —
  either a valid request or a deliberately malformed one.
- **Failing_Case**: A Generated_Case whose response violates an expectation (an
  unhandled server error, an unauthenticated success, or a schema violation).
- **Unhandled_Server_Error**: A `5xx` response indicating unvalidated input reached
  application code; treated as a security finding.
- **Schema_Violation**: A response whose status code, headers, or body does not
  conform to the OpenAPI_Schema's declared contract for that operation.
- **Reproducing_Request**: The exact request (method, path, headers, body) needed to
  reproduce a Failing_Case, recorded on the corresponding Finding.
- **Random_Seed**: The seed controlling Schemathesis data generation, fixed on the
  Fast_Profile for reproducibility and left unset on the Deep_Profile.
- **Fast_Profile**: The `fast` scan profile, run on every deploy against staging.
  Includes Schemathesis with a fixed Random_Seed.
- **Deep_Profile**: The `deep` scan profile, run nightly against staging. Includes
  Schemathesis with no fixed Random_Seed, where exploring new cases is the point.
- **Production_Target**: A target identified as a production environment, against
  which Schemathesis's malformed and state-changing traffic is forbidden.

## Requirements

### Requirement 1: Schemathesis adapter implementing the shared protocol

**User Story:** As a DAST operator, I want Schemathesis exposed as an adapter that
matches the existing tool interface, so that it plugs into the pipeline exactly as
nuclei and ZAP do without special-case handling.

#### Acceptance Criteria

1. THE Schemathesis_Adapter SHALL expose a `name` attribute that is a non-empty,
   constant string identifying the adapter and that remains identical across every
   instantiation and invocation.
2. THE Schemathesis_Adapter SHALL expose a `mutating` attribute whose value is a
   boolean.
3. THE Schemathesis_Adapter SHALL expose a `scan(scope)` method that accepts a single
   `DastScope` argument and returns exactly one `ScanOutcome` object.
4. IF `scan` is invoked with an argument that is not a `DastScope`, THEN THE
   Schemathesis_Adapter SHALL raise an error and SHALL NOT return a `ScanOutcome`.
5. THE Schemathesis_Adapter SHALL provide a parsing function that, given a saved
   Schemathesis output fixture, returns zero or more `Finding` objects, performs no
   network or filesystem I/O, and returns identical results on repeated invocations
   over the same input.
6. THE DAST_Service SHALL read every Schemathesis configuration value from a setting
   whose name begins with the `DAST_` prefix, and SHALL NOT read any Schemathesis
   configuration value from a setting whose name begins with the `SECURITY_` prefix.

### Requirement 2: Read the OpenAPI schema, base URL, and auth token

**User Story:** As a DAST operator, I want Schemathesis driven from the target's
OpenAPI schema, base URL, and auth token, so that it generates requests against the
real, authenticated application surface.

#### Acceptance Criteria

1. WHEN a scan begins AND the configured OpenAPI path resolves to a file reference,
   THE Schemathesis_Adapter SHALL load the OpenAPI_Schema from that file before
   generating requests.
2. WHEN a scan begins AND no file reference is configured, THE Schemathesis_Adapter
   SHALL load the OpenAPI_Schema from the URL derived from `DastScope.target_url` and
   the configured OpenAPI path, completing the load within the configured schema-load
   timeout read from a `DAST_`-prefixed setting.
3. THE Schemathesis_Adapter SHALL send every generated request to the Base_URL carried
   on `DastScope.target_url`, and SHALL NOT send any generated request to a host other
   than that Base_URL.
4. WHERE `DastScope.auth_header` is set, THE Schemathesis_Adapter SHALL attach the
   exact Auth_Header value as the `Authorization` header on every outgoing generated
   request; WHERE `DastScope.auth_header` is not set, THE Schemathesis_Adapter SHALL
   send every outgoing generated request with no `Authorization` header.
5. IF the OpenAPI_Schema cannot be retrieved within the configured schema-load
   timeout, or is retrieved but cannot be parsed as a valid OpenAPI document, THEN THE
   Schemathesis_Adapter SHALL raise a `ScannerError` without sending any generated
   request, so the Runner records an `incomplete` ToolCoverage entry whose reason
   indicates the schema was unavailable or invalid.

### Requirement 3: Route traffic through ZAP as a proxy

**User Story:** As a DAST operator, I want Schemathesis to send its traffic through
the ZAP proxy, so that a single execution both reports its own failures and fills
ZAP's site tree with real, authenticated, valid traffic for ZAP's active scanner.

#### Acceptance Criteria

1. WHERE a ZAP_Proxy is configured, THE Schemathesis_Adapter SHALL route every
   outgoing generated request through the ZAP_Proxy such that no generated request
   reaches the Base_URL except by way of the ZAP_Proxy.
2. THE DAST_Service SHALL read the ZAP_Proxy host and port from `DAST_`-prefixed
   configuration settings, and SHALL treat the ZAP_Proxy as not configured when either
   the host or the port setting is absent or empty.
3. WHEN routing a generated request through the ZAP_Proxy, THE Schemathesis_Adapter
   SHALL attach the unmodified Auth_Header value to that proxied request so ZAP's site
   tree is seeded with authenticated traffic.
4. IF a ZAP_Proxy is configured but a connection to its configured host and port
   cannot be established within a configured connection timeout (default 5 seconds)
   when a scan begins, THEN THE Schemathesis_Adapter SHALL send no generated requests
   and SHALL raise a `ScannerError` so the Runner records an `incomplete` ToolCoverage
   entry rather than silently sending unproxied traffic.

### Requirement 4: Reproducible generation via seeding

**User Story:** As a DAST operator, I want deterministic generation on every deploy
and exploratory generation nightly, so that per-deploy results are reproducible while
the nightly run keeps finding new cases.

#### Acceptance Criteria

1. WHEN a scan runs under the Fast_Profile and a fixed Random_Seed is configured, THE
   Schemathesis_Adapter SHALL initialise Schemathesis generation with that fixed
   Random_Seed so that two runs against an unchanged OpenAPI_Schema and unchanged
   configuration produce an identical set of Generated_Cases.
2. WHEN a scan runs under the Deep_Profile, THE Schemathesis_Adapter SHALL run without
   a fixed Random_Seed so that each run's set of Generated_Cases differs from prior
   runs against the same OpenAPI_Schema.
3. THE DAST_Service SHALL read the fixed Random_Seed value, interpreted as an integer,
   from a `DAST_`-prefixed configuration setting.
4. IF a scan runs under the Fast_Profile and no fixed Random_Seed is configured, or
   the configured value is not a valid integer, THEN THE Schemathesis_Adapter SHALL
   raise a `ScannerError` so the Runner records an `incomplete` ToolCoverage entry
   indicating the seed was unavailable, rather than running with non-reproducible
   generation.

### Requirement 5: Detect unhandled server errors

**User Story:** As a DAST operator, I want unhandled 500 responses reported as
findings, so that unvalidated input reaching our code — and the stack traces it leaks
— is caught before release.

#### Acceptance Criteria

1. WHEN a Generated_Case elicits a response with a status code in the range 500–599
   that is not a declared response for the invoked operation in the OpenAPI_Schema,
   THE Schemathesis_Adapter SHALL record an Unhandled_Server_Error Failing_Case for
   the responsible endpoint.
2. WHEN a Generated_Case elicits a 5xx response that the OpenAPI_Schema declares for
   the invoked operation, THE Schemathesis_Adapter SHALL NOT record an
   Unhandled_Server_Error Failing_Case for that response.
3. THE Schemathesis_Adapter SHALL convert each Unhandled_Server_Error Failing_Case
   into a `Finding` carrying a severity of `high` and an endpoint location expressed
   as the HTTP method and the templatised path of the responsible operation.
4. THE Schemathesis_Adapter SHALL assign each Unhandled_Server_Error `Finding` a
   `rule_id` that is stable across runs for the same endpoint and response status.

### Requirement 6: Detect unauthenticated access

**User Story:** As a DAST operator, I want endpoints that answer without
authentication reported as findings, so that broken access control on protected
operations is caught.

#### Acceptance Criteria

1. WHEN a Generated_Case for an operation whose OpenAPI_Schema declares a security
   requirement is sent with the Auth_Header omitted and the target returns a status
   code in the range 200–299, THE Schemathesis_Adapter SHALL record a Failing_Case for
   that endpoint.
2. THE Schemathesis_Adapter SHALL convert each unauthenticated-access Failing_Case
   into a `Finding` carrying the endpoint location, the observed response status code,
   and a severity reflecting broken access control.

### Requirement 7: Detect schema violations

**User Story:** As a DAST operator, I want responses that violate their declared
schema reported as findings, so that contract breaks between the API and its OpenAPI
spec are caught.

#### Acceptance Criteria

1. WHEN a target response for an invoked operation has a status code, headers, or
   response body that does not conform to the OpenAPI_Schema's declared contract for
   that operation, THE Schemathesis_Adapter SHALL record a Schema_Violation
   Failing_Case for the responsible endpoint.
2. WHEN a target response conforms to every status code, header, and body constraint
   declared by the OpenAPI_Schema for the invoked operation, THE Schemathesis_Adapter
   SHALL NOT record a Schema_Violation Failing_Case for that response.
3. THE Schemathesis_Adapter SHALL convert each Schema_Violation Failing_Case into a
   `Finding` carrying the endpoint location, a severity reflecting a contract
   violation, and a description identifying which contract element (status code,
   header, or body) was violated.
4. WHEN a single response violates more than one declared contract element, THE
   Schemathesis_Adapter SHALL record the response as one Schema_Violation Failing_Case
   whose description enumerates every violated contract element.

### Requirement 8: Every finding carries its reproducing request

**User Story:** As a DAST operator, I want each finding to include the exact request
that produced it, so that a developer can reproduce and fix the failure without
guesswork.

#### Acceptance Criteria

1. WHEN the Schemathesis_Adapter produces a `Finding` for a Failing_Case, THE
   Schemathesis_Adapter SHALL attach the Reproducing_Request for that Failing_Case to
   the `Finding`.
2. THE Schemathesis_Adapter SHALL record on each Reproducing_Request the HTTP method,
   the request path including any query string, every request header sent, and the
   request body, so the recorded request can be reissued unchanged.
3. WHERE the Failing_Case's request carried no body, THE Schemathesis_Adapter SHALL
   record the Reproducing_Request body as an explicit empty value rather than omitting
   the body field.
4. WHERE the outgoing request carried the Auth_Header, THE Schemathesis_Adapter SHALL
   include that Auth_Header among the recorded request headers so the reissued request
   reaches the same authenticated surface.
5. IF the Reproducing_Request for a Failing_Case cannot be captured, THEN THE
   Schemathesis_Adapter SHALL attach an indication that the reproducing request is
   unavailable to the `Finding` rather than emitting a `Finding` with no request
   detail.

### Requirement 9: Findings flow through the shared normalize, dedupe, and baseline chain

**User Story:** As a DAST operator, I want Schemathesis findings to flow through the
same normalize → dedupe → baseline chain as nuclei and ZAP, so that results are
deduplicated, diffed against the baseline, and reported with stable identities.

#### Acceptance Criteria

1. THE Schemathesis_Adapter SHALL return each Failing_Case as a shared `Finding`
   object populated with a non-empty scanner name identifying Schemathesis, a
   `rule_id` that is identical across runs for the same rule identity, a non-empty web
   location, a severity value drawn from the shared `Finding` model's defined severity
   scale, and a non-empty message.
2. WHEN a Failing_Case reports a URL containing variable path segments, THE
   Schemathesis_Adapter SHALL replace each concrete path segment that corresponds to a
   templated segment in `DastScope.spec_paths` with that template's placeholder before
   the Finding_Id is computed, so the resulting Finding_Id is identical across runs
   that reach the same endpoint with differing segment values.
3. WHEN two Failing_Cases share both the same rule identity and the same endpoint
   identity, THE DAST_Service SHALL collapse them into a single Finding_Id and SHALL
   retain exactly one representative `Finding`.
4. THE DAST_Service SHALL diff Schemathesis findings against the target's stored
   baseline using the same Finding_Id chain used for nuclei and ZAP findings,
   classifying each finding as new when its Finding_Id is absent from the baseline and
   as known when its Finding_Id is present in the baseline.
5. IF no stored baseline exists for the target when the diff runs, THEN THE
   DAST_Service SHALL classify every Schemathesis finding as new.

### Requirement 10: Two-tier runner integration and profile membership

**User Story:** As a DAST operator, I want Schemathesis wired into the existing runner
and profiles, so that it runs on every deploy and is tiered correctly against the
other tools.

#### Acceptance Criteria

1. WHEN `default_adapters` is built for the Fast_Profile, THE DAST_Service SHALL
   include exactly one Schemathesis_Adapter in the returned adapter set.
2. WHEN `default_adapters` is built for the Deep_Profile, THE DAST_Service SHALL
   include exactly one Schemathesis_Adapter in the returned adapter set.
3. THE Schemathesis_Adapter SHALL expose its `mutating` flag with the value true, so
   the Runner assigns it to the serial mutating tier rather than the concurrent
   read-only tier.
4. WHILE building the serial mutating tier, WHEN both the Schemathesis_Adapter and the
   ZAP active scan adapter are present, THE Runner SHALL place the Schemathesis_Adapter
   at an execution position earlier than the ZAP active scan adapter, so ZAP's site
   tree is seeded by Schemathesis traffic before the active scan runs.
5. WHILE building the serial mutating tier, WHEN the Schemathesis_Adapter is present
   and the ZAP active scan adapter is absent, THE Runner SHALL include and run the
   Schemathesis_Adapter without requiring the ZAP active scan adapter.

### Requirement 11: Real request evidence drives complete/incomplete

**User Story:** As a DAST operator, I want Schemathesis coverage judged by the traffic
it actually sent, so that "zero findings" stays trustworthy and a scan that never
reached the target cannot report clean.

#### Acceptance Criteria

1. WHEN a scan terminates, whether normally or by error, THE Schemathesis_Adapter
   SHALL populate ToolActivity with `requests_made` (the count of requests transmitted
   to the target that returned any response) and `request_errors` (the count of
   requests that failed at the transport level or timed out).
2. IF the recorded `requests_made` is zero, THEN THE DAST_Service SHALL mark the
   Schemathesis ToolCoverage `incomplete` with a reason indicating no requests reached
   the target, rather than reporting a clean result.
3. IF `requests_made` is greater than zero AND `request_errors` is greater than or
   equal to `requests_made`, THEN THE DAST_Service SHALL mark the Schemathesis
   ToolCoverage `incomplete` with a reason indicating all requests failed.
4. THE Schemathesis_Adapter SHALL derive `requests_made` solely from requests that
   actually reached the target and SHALL NOT derive it from the count of
   Generated_Cases produced.

### Requirement 12: Graceful degradation on failure

**User Story:** As a DAST operator, I want a failed Schemathesis run to produce an
incomplete result, so that a missing or broken scanner is never mistaken for a clean
application.

#### Acceptance Criteria

1. IF the target cannot be connected to when a scan begins — connection refused, DNS
   resolution failure, or no connection established within a configured connection
   timeout (default 30 seconds, read from a `DAST_`-prefixed setting) — THEN THE
   Schemathesis_Adapter SHALL raise a `ScannerError` so the Runner records an
   `incomplete` ToolCoverage entry whose reason indicates the target was unreachable.
2. IF the Schemathesis run terminates by a non-zero exit, an unhandled exception, or
   interruption before all Generated_Cases complete, THEN THE Schemathesis_Adapter
   SHALL cause an `incomplete` ToolCoverage entry with a reason describing the failure
   rather than returning a clean result.
3. WHEN the Schemathesis_Adapter fails for any reason, THE Runner SHALL continue
   running the remaining tools and SHALL preserve the other adapters' findings and
   ToolCoverage unchanged.
4. WHEN the Schemathesis_Adapter fails, THE Schemathesis_Adapter SHALL populate the
   failure-path ToolActivity with the `requests_made`, `request_errors`, and
   `exit_code` evidence available at the point of failure.

### Requirement 13: Rate throttling for a single-worker target

**User Story:** As a DAST operator, I want Schemathesis request throughput throttled,
so that a single-worker staging target is not jammed into producing a falsely clean
scan.

#### Acceptance Criteria

1. THE DAST_Service SHALL read a maximum Schemathesis request rate, expressed in
   requests per second and constrained to the range 1 to 1000 requests per second,
   from a `DAST_`-prefixed configuration setting.
2. IF the maximum Schemathesis request rate setting is absent or falls outside the
   range 1 to 1000 requests per second, THEN THE DAST_Service SHALL apply a default
   maximum request rate of 10 requests per second.
3. WHILE a scan is running, THE Schemathesis_Adapter SHALL limit outgoing request
   throughput so that the number of requests sent to the target within any 1-second
   sliding window does not exceed the configured maximum request rate.
4. THE DAST_Service SHALL read a maximum request-timeout threshold, expressed as a
   count of request timeouts and constrained to the range 1 to 100000, from a
   `DAST_`-prefixed configuration setting.
5. IF the count of request timeouts recorded in ToolActivity exceeds the configured
   maximum request-timeout threshold, THEN THE DAST_Service SHALL mark the
   Schemathesis ToolCoverage `incomplete`, set its `reason` to indicate the target may
   be overloaded, and retain the findings produced before the threshold was exceeded.

### Requirement 14: Pinned version and staging-only execution

**User Story:** As a DAST operator, I want the Schemathesis version pinned and its
malformed traffic confined to staging, so that the tool deciding whether our build
passes cannot change without review and attack-like traffic never hits production.

#### Acceptance Criteria

1. THE DAST_Service SHALL reference the Schemathesis version by an exact, immutable
   version identifier that names a single released version, and SHALL NOT reference it
   by a mutable tag such as `latest` or a branch reference, so that any version change
   requires a reviewed change to the pinned identifier.
2. WHEN a scan begins, THE Schemathesis_Adapter SHALL determine whether the scan's
   target is a Production_Target from the target's configured environment designation
   before sending any generated request.
3. IF a scan requests Schemathesis against a Production_Target, THEN THE
   Schemathesis_Adapter SHALL refuse to run, SHALL send zero generated requests to the
   target, and SHALL raise a `ScannerError` so the Runner records an `incomplete`
   ToolCoverage entry whose reason states the scan was refused because the target is a
   Production_Target.
