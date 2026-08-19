# Requirements Document

## Introduction

Phase 3 of the DAST pipeline integrates OWASP ZAP as a dynamic scanner into the
existing standalone DAST service (built in Phases 1 and 2). Where nuclei answers
"are we exposed to anything already publicly known?", ZAP answers "does *our own
code* have injection, XSS, or access-control flaws?" — bugs no signature database
can know about because we wrote them last week.

ZAP is the hardest tool to integrate for one reason: it only attacks URLs already
on its internal map. Hand it three endpoints and it checks three endpoints and
reports "all secure" while the rest of the application goes untested. An unseeded
ZAP scan reports zero findings and exits successfully — a false all-clear. Making
that failure mode impossible is the core of this work, and it ties directly into
the Phase 2 liveness/trust model that already exists to keep "zero findings"
honest.

This feature MUST fit the existing architecture rather than reinvent it. The ZAP
integration reuses the `DastAdapter` protocol, `DastScope`, `ScanOutcome`,
`ToolActivity`, and `ToolCoverage` data models, plugs into the two-tier runner
(read-only tools run concurrently, mutating tools run serially), and sends its
findings through the same normalize → dedupe → baseline chain with stable
`finding_id`s that nuclei already uses. ZAP runs as a long-lived sidecar container
driven over its REST API, so no per-scan JVM startup cost is paid.

## Glossary

- **DAST_Service**: The standalone FastAPI service that queues and runs dynamic
  scans against a running target. The system under specification.
- **Zap_Adapter**: The new adapter component that implements the `DastAdapter`
  protocol and drives OWASP ZAP over its REST API. The primary subject of these
  requirements.
- **ZAP_Sidecar**: A long-lived OWASP ZAP container running in daemon mode,
  reachable by the `Zap_Adapter` over ZAP's REST API on a configured host and port.
- **Runner**: The existing DAST runner that splits adapters into read-only
  (concurrent) and mutating (serial) tiers and aggregates their findings and
  coverage.
- **DastScope**: The existing input model describing what to scan: `target_url`,
  `commit_sha`, `auth_header`, `spec_paths`, and `profile`.
- **ScanOutcome**: The existing per-tool output model carrying `findings` and a
  `ToolActivity` record.
- **ToolActivity**: The existing evidence model recording `units_executed`,
  `requests_made`, `request_errors`, `timeouts`, `exit_code`, and
  `duration_seconds`.
- **ToolCoverage**: The existing per-tool status model recording `status`
  (`complete` | `incomplete`), `reason`, and `activity`.
- **Passive_Scan**: ZAP observation mode — it inspects traffic already in its map
  and sends no attack payloads. Fast; classified read-only.
- **Active_Scan**: ZAP attack mode — it sends real attack payloads to every mapped
  endpoint. Slow; classified mutating; staging only.
- **ZAP_Session**: ZAP's in-memory state for one scan, including its site tree
  (map) and recorded alerts.
- **Site_Tree**: ZAP's internal map of known endpoints. ZAP only scans what is on
  this map; seeding it from the OpenAPI spec is "filling the map".
- **Spec_Paths**: The OpenAPI path templates already fetched during preflight and
  carried on `DastScope.spec_paths`.
- **Canary_Endpoint**: A deliberately vulnerable endpoint (e.g. reflected XSS)
  present only in the staging build behind a build flag. The "test button" for the
  scanner's alarm.
- **Fast_Profile**: The `fast` scan profile, run on every deploy. Includes ZAP
  passive scanning.
- **Deep_Profile**: The `deep` scan profile, run nightly against staging. Includes
  ZAP active scanning; advisory-only.
- **Auth_Header**: The full `Authorization` header value carried on
  `DastScope.auth_header`, injected on every outgoing ZAP request.
- **Logout_URL**: A configured URL (e.g. `/logout`) that must be excluded from
  scanning so the scanner does not log itself out mid-scan.
- **Finding_Id**: The stable hash of `(rule_identity, endpoint_identity)` produced
  by the shared normalize chain, used for deduplication and baseline diffing.
- **Production_Target**: A target identified as a production environment, against
  which active scanning is forbidden.

## Requirements

### Requirement 1: ZAP sidecar in daemon mode over REST

**User Story:** As a DAST operator, I want ZAP to run as a long-lived sidecar
driven over its REST API, so that scans avoid a per-scan JVM startup cost and reuse
a warm process.

#### Acceptance Criteria

1. THE Zap_Adapter SHALL drive the ZAP_Sidecar exclusively over the ZAP REST API at
   the configured host and port.
2. THE Zap_Adapter SHALL NOT start a new ZAP process per scan.
3. WHEN a scan begins, THE Zap_Adapter SHALL confirm the ZAP_Sidecar is reachable
   over its REST API before issuing scan commands.
4. THE DAST_Service SHALL read the ZAP_Sidecar host and port from `DAST_`-prefixed
   configuration settings.

### Requirement 2: Fresh session per scan

**User Story:** As a DAST operator, I want every scan to start from a clean ZAP
session, so that findings from a previous run or a different target never bleed into
the current report.

#### Acceptance Criteria

1. WHEN a scan begins, THE Zap_Adapter SHALL start a new ZAP_Session before seeding
   the Site_Tree or scanning.
2. WHEN a new ZAP_Session is started, THE Zap_Adapter SHALL ensure no alerts or
   Site_Tree entries from any previous scan remain in the ZAP_Session.
3. IF starting a fresh ZAP_Session fails, THEN THE Zap_Adapter SHALL raise a
   `ScannerError` so the Runner records an `incomplete` ToolCoverage entry.

### Requirement 3: Authenticated scanning via injected header

**User Story:** As a DAST operator, I want the configured Authorization header
injected on every outgoing ZAP request, so that the whole authenticated surface is
covered rather than only the login page.

#### Acceptance Criteria

1. WHERE `DastScope.auth_header` is set, THE Zap_Adapter SHALL attach the
   Auth_Header value to every outgoing request the ZAP_Sidecar makes to the target.
2. WHERE `DastScope.auth_header` is not set, THE Zap_Adapter SHALL scan the target
   without an Authorization header.
3. THE Zap_Adapter SHALL apply the Auth_Header to both Passive_Scan and Active_Scan
   traffic.

### Requirement 4: Logout URL exclusion

**User Story:** As a DAST operator, I want the logout URL excluded from scanning, so
that the scanner does not log itself out mid-scan and continue as an anonymous user.

#### Acceptance Criteria

1. WHERE a Logout_URL is configured, THE Zap_Adapter SHALL register the Logout_URL
   as excluded from scanning in the ZAP_Session before any scan begins.
2. WHILE a scan is running, THE Zap_Adapter SHALL NOT send requests to any URL
   matching the configured Logout_URL exclusion.
3. THE DAST_Service SHALL read the Logout_URL exclusion pattern from a `DAST_`-
   prefixed configuration setting.

### Requirement 5: Seed the site tree from the OpenAPI spec

**User Story:** As a DAST operator, I want ZAP's site tree seeded from the target's
OpenAPI spec, so that ZAP scans the real application surface instead of the handful
of endpoints it can discover on its own.

#### Acceptance Criteria

1. WHERE `DastScope.spec_paths` is non-empty, THE Zap_Adapter SHALL import the
   OpenAPI-declared endpoints into the ZAP_Session Site_Tree before scanning.
2. WHEN seeding completes, THE Zap_Adapter SHALL record the count of endpoints added
   to the Site_Tree.
3. IF `DastScope.spec_paths` is empty, THEN THE Zap_Adapter SHALL record an
   `incomplete` ToolCoverage entry with a reason stating the Site_Tree was not
   seeded.
4. WHEN seeding from the spec, THE Zap_Adapter SHALL apply the Auth_Header to the
   requests used to populate the Site_Tree.

### Requirement 6: Passive on every deploy, active nightly and advisory, staging only

**User Story:** As a DAST operator, I want passive scanning on every deploy and
active scanning nightly against staging only, so that fast safe feedback ships
continuously while attack traffic is confined to a safe environment and time.

#### Acceptance Criteria

1. WHEN a scan runs under the Fast_Profile, THE Zap_Adapter SHALL perform a
   Passive_Scan.
2. WHEN a scan runs under the Fast_Profile, THE Zap_Adapter SHALL NOT perform an
   Active_Scan.
3. WHEN a scan runs under the Deep_Profile against a non-production target, THE
   Zap_Adapter SHALL perform an Active_Scan.
4. IF a scan requests an Active_Scan against a Production_Target, THEN THE
   Zap_Adapter SHALL refuse to perform the Active_Scan and record the refusal.
5. WHERE findings originate from an Active_Scan, THE DAST_Service SHALL mark those
   findings advisory-only so they do not block a release.

### Requirement 7: Canary verification tied to the liveness model

**User Story:** As a DAST operator, I want the canary endpoint checked at the start
and end of every run, so that an unseeded or blind ZAP scan cannot report a false
"clean".

#### Acceptance Criteria

1. WHEN a scan begins, THE Zap_Adapter SHALL verify the Canary_Endpoint is detected
   by ZAP.
2. WHEN a scan ends, THE Zap_Adapter SHALL verify the Canary_Endpoint is detected by
   ZAP.
3. IF the Canary_Endpoint is not detected at the start of a scan, THEN THE
   Zap_Adapter SHALL record an `incomplete` ToolCoverage entry indicating the
   scanner's own detection is not working.
4. IF the Canary_Endpoint is detected at the start of a scan but not at the end,
   THEN THE Zap_Adapter SHALL record an `incomplete` ToolCoverage entry indicating
   that something began blocking the scanner mid-scan.
5. WHEN the Canary_Endpoint is detected at both the start and the end of a scan, THE
   Zap_Adapter SHALL record the canary verification as passed in its ToolActivity.

### Requirement 8: Findings flow through the shared normalize, dedupe, and baseline chain

**User Story:** As a DAST operator, I want ZAP findings to flow through the same
normalize → dedupe → baseline chain as nuclei, so that ZAP results are deduplicated,
diffed against the baseline, and reported with stable identities.

#### Acceptance Criteria

1. THE Zap_Adapter SHALL return ZAP alerts as shared `Finding` objects carrying a
   scanner name, a stable `rule_id`, a web location, a severity, and a message.
2. WHEN a ZAP alert reports a URL containing variable path segments, THE Zap_Adapter
   SHALL templatise the URL using `DastScope.spec_paths` so the resulting
   Finding_Id is stable across runs.
3. WHEN two ZAP alerts share the same rule identity and endpoint identity, THE
   DAST_Service SHALL deduplicate them to a single Finding_Id.
4. THE DAST_Service SHALL diff ZAP findings against the target's stored baseline
   using the same Finding_Id chain used for nuclei findings.

### Requirement 9: Read-only/mutating classification with real request evidence

**User Story:** As a DAST operator, I want passive classified read-only and active
classified mutating with recorded request evidence, so that the runner tiers ZAP
correctly and "zero findings" stays trustworthy.

#### Acceptance Criteria

1. WHERE the Zap_Adapter is performing a Passive_Scan, THE Zap_Adapter SHALL declare
   itself read-only so the Runner may run it concurrently with other read-only
   tools.
2. WHERE the Zap_Adapter is performing an Active_Scan, THE Zap_Adapter SHALL declare
   itself mutating so the Runner serialises it.
3. WHEN a scan completes, THE Zap_Adapter SHALL populate ToolActivity with the count
   of requests the ZAP_Sidecar actually sent to the target and the count of those
   requests that failed.
4. IF the recorded `requests_made` is zero, THEN THE DAST_Service SHALL mark the ZAP
   ToolCoverage `incomplete` rather than reporting a clean result.
5. IF the recorded `request_errors` equals or exceeds `requests_made`, THEN THE
   DAST_Service SHALL mark the ZAP ToolCoverage `incomplete`.

### Requirement 10: Done-when acceptance signals

**User Story:** As a DAST operator, I want the integration to prove itself against
the plan's done-when criteria, so that I can trust ZAP is seeded, live, and running
on every deploy.

#### Acceptance Criteria

1. WHEN a scan seeds the Site_Tree from a spec declaring N endpoints, THE
   Zap_Adapter SHALL discover an endpoint count within a configured tolerance of N.
2. IF the discovered endpoint count falls below the configured tolerance of the
   spec-declared count, THEN THE Zap_Adapter SHALL record an `incomplete`
   ToolCoverage entry indicating the map was under-seeded.
3. WHEN a scan runs against a staging build containing the Canary_Endpoint, THE
   Zap_Adapter SHALL report a finding for the canary XSS.
4. WHEN a deploy triggers a Fast_Profile scan, THE DAST_Service SHALL include a ZAP
   Passive_Scan in that scan.

### Requirement 11: Pinned image and version reproducibility

**User Story:** As a DAST operator, I want the ZAP image version pinned, so that the
tool deciding whether our build passes cannot change without review.

#### Acceptance Criteria

1. THE DAST_Service SHALL reference the ZAP_Sidecar image by a pinned version
   identifier rather than a mutable tag such as `latest`.
2. THE DAST_Service SHALL read the pinned ZAP image reference from configuration or
   the service's container definition so upgrades occur through a reviewed change.

### Requirement 12: Rate throttling for a single-worker target

**User Story:** As a DAST operator, I want ZAP request throughput throttled, so that
a single-worker staging target is not jammed into producing a falsely clean scan.

#### Acceptance Criteria

1. THE DAST_Service SHALL read a maximum ZAP request rate from a `DAST_`-prefixed
   configuration setting.
2. WHILE a scan is running, THE Zap_Adapter SHALL limit outgoing request throughput
   to the configured maximum request rate.
3. IF the count of request timeouts exceeds the configured threshold, THEN THE
   DAST_Service SHALL mark the ZAP ToolCoverage `incomplete` with a reason
   indicating the target may be overloaded.

### Requirement 13: Graceful degradation when the sidecar is unreachable

**User Story:** As a DAST operator, I want an unreachable ZAP sidecar to produce an
incomplete result, so that a missing scanner is never mistaken for a clean
application.

#### Acceptance Criteria

1. IF the ZAP_Sidecar is unreachable over its REST API when a scan begins, THEN THE
   Zap_Adapter SHALL raise a `ScannerError` so the Runner records an `incomplete`
   ToolCoverage entry.
2. IF the ZAP_Sidecar becomes unreachable during a scan, THEN THE Zap_Adapter SHALL
   record an `incomplete` ToolCoverage entry rather than returning a clean result.
3. WHEN the Zap_Adapter fails for any reason, THE Runner SHALL continue running the
   remaining tools in the scan.
