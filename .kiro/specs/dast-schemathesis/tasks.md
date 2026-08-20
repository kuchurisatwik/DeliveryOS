# Implementation Plan: DAST Schemathesis Integration (Phase 4)

## Overview

This plan integrates Schemathesis as a dynamic scanner into the existing standalone
DAST service (built in Phases 1–3). It follows the design: a `SchemathesisAdapter`
that mirrors the **`NucleiAdapter` CLI structure** (not ZAP's REST-sidecar structure)
— a pure `parse()` classmethod over Schemathesis's machine-readable report and an
impure `scan()` that drives the pinned Schemathesis CLI as a subprocess through the
shared `run_scanner` helper. It plugs into the existing two-tier runner, declares
`mutating = True`, and is ordered **before** the active `ZapAdapter` in the serial
mutating tier so its authenticated traffic seeds ZAP's site tree (Req 10.4). Each step
builds on the previous one and ends by wiring Schemathesis into the runner and
deployment so nothing is left orphaned.

The work reuses the existing `DastAdapter` protocol, `DastScope`, `ScanOutcome`,
`ToolActivity`, `ToolCoverage`, the shared `Finding`, the `make_web_location` /
`endpoint_identity` helpers, and the normalize → dedupe → baseline chain. Unlike
Phase 3 (ZAP), there is **no shared-model change**: Schemathesis reuses `scanner`,
`rule_id`, `location`, `severity`, `message`, `category`, and carries the reproducing
request in the existing `Finding.raw`. All trust guarantees route through the existing
`_run_one` / `_assess_activity` logic in `dast/runner.py`. The ZAP proxy is reused via
the existing `DAST_ZAP_HOST` / `DAST_ZAP_PORT` settings — no new proxy plumbing.

Implementation language: **Python** (matches the existing `dast/` and `app/security/`
packages, and the design's code). Property-based tests use Hypothesis, already in the
repo (`tests/security/`, `.hypothesis` cache).

## Tasks

- [x] 1. Add Schemathesis configuration (no shared-model change)
  - [x] 1.1 Add `DAST_SCHEMATHESIS_*` settings to `dast/config.py`
    - Add `DAST_SCHEMATHESIS_VERSION` (pinned exact version, never `latest`/branch),
      `DAST_SCHEMATHESIS_SCHEMA_FILE`, `DAST_SCHEMATHESIS_SCHEMA_TIMEOUT`,
      `DAST_SCHEMATHESIS_SEED`, `DAST_SCHEMATHESIS_RATE_LIMIT`,
      `DAST_SCHEMATHESIS_CONNECT_TIMEOUT`, `DAST_SCHEMATHESIS_PROXY_CONNECT_TIMEOUT`,
      `DAST_SCHEMATHESIS_TIMEOUT`, `DAST_SCHEMATHESIS_TIMEOUT_THRESHOLD`, and
      `DAST_SCHEMATHESIS_PROD_URL_PATTERN` with the documented defaults, all
      `DAST_`-prefixed
    - Do NOT add a shared-model field: unlike Phase 3's `Finding.advisory`, Schemathesis
      needs no new `Finding` field. The ZAP proxy host/port reuse the existing
      `DAST_ZAP_HOST` / `DAST_ZAP_PORT`; the schema URL reuses the existing
      `DAST_OPENAPI_PATH`
    - _Requirements: 1.6, 2.2, 3.4, 4.3, 12.1, 12.2, 13.1, 13.2, 13.4, 14.1_

  - [x] 1.2 Write unit tests for config defaults and the pinned version
    - Assert defaults load and that `DAST_SCHEMATHESIS_VERSION` is an exact version,
      never `latest` or a branch reference (Req 14.1)
    - New file `tests/dast/test_schemathesis_config.py`
    - _Requirements: 1.6, 13.2, 14.1_

- [x] 2. Implement the pure SchemathesisAdapter.parse layer
  - [x] 2.1 Create `SchemathesisAdapter` scaffold and pure `parse()` in `dast/adapters/schemathesis_adapter.py`
    - Define `name = "schemathesis"` / `mutating = True` class attributes and the
      constructor (`settings`, `binary`); implement `parse(report, *, spec_paths,
      scanner_name)` as a pure classmethod, mirroring `NucleiAdapter.parse`, that maps
      the three finding kinds to shared `Finding` objects via `make_web_location`:
      undeclared 5xx (`not_a_server_error`) → `HIGH`; `ignored_auth` → access-control
      severity + observed status; schema-conformance checks → contract-violation
      severity with a description enumerating every violated element
    - Assign a stable `rule_id` per endpoint + failure kind + response status (e.g.
      `server_error:GET /api/users/{id}:500`); record the reproducing request
      (method, path+query, all headers incl. auth, body-as-explicit-empty-when-absent,
      or an explicit `{"unavailable": true}` marker) and the observed response under
      `Finding.raw`; perform no network or filesystem I/O
    - _Requirements: 1.5, 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2_

  - [x] 2.2 Write property test: parse is pure and deterministic
    - **Property 1: parse() is pure and deterministic**
    - **Validates: Requirements 1.5**
    - New file `tests/dast/test_schemathesis_prop01_parse_pure.py`

  - [x] 2.3 Write property test: parsed findings are fully populated with stable identity
    - **Property 2: parsed findings are fully populated with stable identity**
    - **Validates: Requirements 5.4, 9.1**
    - New file `tests/dast/test_schemathesis_prop02_findings_populated.py`

  - [x] 2.4 Write property test: URL templatisation yields stable finding identity
    - **Property 3: URL templatisation yields stable finding identity**
    - **Validates: Requirements 9.2**
    - New file `tests/dast/test_schemathesis_prop03_templatise_identity.py`

  - [x] 2.5 Write property test: duplicate failing cases collapse to one finding
    - **Property 4: duplicate failing cases collapse to one finding**
    - **Validates: Requirements 9.3, 9.4, 9.5**
    - New file `tests/dast/test_schemathesis_prop04_dedupe.py`

  - [x] 2.6 Write property test: undeclared 5xx becomes high-severity, declared does not
    - **Property 5: undeclared 5xx becomes a high-severity finding; declared 5xx does not**
    - **Validates: Requirements 5.1, 5.2, 5.3**
    - New file `tests/dast/test_schemathesis_prop05_server_error.py`

  - [x] 2.7 Write property test: unauthenticated 2xx on a secured operation becomes a finding
    - **Property 6: an unauthenticated 2xx on a secured operation becomes a finding**
    - **Validates: Requirements 6.1, 6.2**
    - New file `tests/dast/test_schemathesis_prop06_unauth_access.py`

  - [x] 2.8 Write property test: non-conforming response becomes one enumerating schema-violation finding
    - **Property 7: a non-conforming response becomes one schema-violation finding enumerating all breaks**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    - New file `tests/dast/test_schemathesis_prop07_schema_violation.py`

  - [x] 2.9 Write property test: every finding carries a complete, reissuable reproducing request
    - **Property 8: every finding carries a complete, reissuable reproducing request**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**
    - New file `tests/dast/test_schemathesis_prop08_reproducing_request.py`

  - [x] 2.10 Write unit test for parse against a saved Schemathesis report fixture
    - Capture a real machine-readable report as
      `tests/dast/fixtures/schemathesis_report.json` and assert Schemathesis field
      names map correctly through `parse()` into the three finding kinds with their
      reproducing requests
    - New file `tests/dast/test_schemathesis_adapter.py`
    - _Requirements: 5.1, 6.1, 7.1, 8.1_

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement the impure SchemathesisAdapter.scan orchestration
  - [x] 4.1 Implement `SchemathesisAdapter.scan()` in `dast/adapters/schemathesis_adapter.py`
    - Orchestrate the sequence behind a narrow command-builder + runner seam:
      argument-type guard (not a `DastScope` → raise, no `ScanOutcome`) → production
      refusal (`DAST_SCHEMATHESIS_PROD_URL_PATTERN` match → send nothing, raise
      `ScannerError`) → seed resolution (fast profile reads `DAST_SCHEMATHESIS_SEED`,
      missing/non-integer → `ScannerError`; deep profile runs unseeded) → schema source
      (file when configured, else URL from `target_url` + `DAST_OPENAPI_PATH` within
      the schema-load timeout) → proxy TCP reachability check when
      `DAST_ZAP_HOST`/`DAST_ZAP_PORT` are both set (unreachable → `ScannerError`, no
      unproxied traffic) → build the CLI arg vector (`--base-url`, `--header
      Authorization` only when `auth_header` set, `--checks all`, clamped
      `--rate-limit`, seed, report path, `--request-proxy`) plus `HTTP_PROXY`/
      `HTTPS_PROXY` env → run via the shared `run_scanner` with the hard
      `DAST_SCHEMATHESIS_TIMEOUT`
    - Classify hard failures (schema unavailable/invalid, target unreachable, non-zero
      exit before any request) as `ScannerError`; read `requests_made`,
      `request_errors`, and `timeouts` from **Schemathesis's own run statistics**
      (never the generated-case count) and build a truthful `ToolActivity`, populating
      `requests_made`/`request_errors`/`exit_code` even on the failure path; return
      `ScanOutcome(findings=parse(report, spec_paths=scope.spec_paths), activity=...)`
    - _Requirements: 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.4, 11.1, 11.4, 12.1, 12.2, 12.4, 13.3, 14.2, 14.3_

  - [x] 4.2 Export `SchemathesisAdapter` from `dast/adapters/__init__.py`
    - Add `SchemathesisAdapter` to the package exports alongside `NucleiAdapter` and
      `ZapAdapter`
    - _Requirements: 1.1, 10.1, 10.2_

  - [x] 4.3 Implement the in-memory fake and saved fixtures for tests
    - Add a `tests/dast/_schemathesis_fakes.py` helper that substitutes the
      command-builder + `run_scanner` seam: it records the exact argument vector and
      subprocess environment (including `--header`, `--request-proxy`, `HTTP_PROXY`,
      `--base-url`, seed, rate limit) the adapter *would* execute and returns a
      configurable fake report + run-stats, so property tests run with no subprocess
      and no network; save a `tests/dast/fixtures/schemathesis_run_stats.*` fixture of
      a real run summary
    - _Requirements: (test infrastructure supporting Properties 9–14, 16, 17)_

  - [x] 4.4 Write property test: auth header attached to every outgoing request, or none
    - **Property 9: the auth header is attached to every outgoing request, or none**
    - **Validates: Requirements 2.4, 3.3**
    - New file `tests/dast/test_schemathesis_prop09_auth_everywhere.py`

  - [x] 4.5 Write property test: every generated request routes through the proxy when configured
    - **Property 10: every generated request routes through the proxy when one is configured**
    - **Validates: Requirements 3.1, 3.2**
    - New file `tests/dast/test_schemathesis_prop10_proxy_routing.py`

  - [x] 4.6 Write property test: requests target only the configured base URL
    - **Property 11: requests target only the configured base URL**
    - **Validates: Requirements 2.3**
    - New file `tests/dast/test_schemathesis_prop11_base_url.py`

  - [x] 4.7 Write property test: generation is reproducible on fast and exploratory on deep
    - **Property 12: generation is reproducible on fast and exploratory on deep**
    - **Validates: Requirements 4.1, 4.2, 4.4**
    - New file `tests/dast/test_schemathesis_prop12_seed_determinism.py`

  - [x] 4.8 Write property test: the rate limit is clamped into range with a safe default
    - **Property 14: the rate limit is clamped into range with a safe default**
    - **Validates: Requirements 13.1, 13.2**
    - New file `tests/dast/test_schemathesis_prop14_rate_limit.py`

  - [x] 4.9 Write property test: a scan against a production target sends nothing and reports incomplete
    - **Property 16: a scan against a production target sends nothing and reports incomplete**
    - **Validates: Requirements 14.2, 14.3**
    - New file `tests/dast/test_schemathesis_prop16_prod_refusal.py`

  - [x] 4.10 Write property test: any hard failure yields an incomplete entry and never aborts the scan
    - **Property 17: any hard failure yields an incomplete entry and never aborts the scan**
    - **Validates: Requirements 1.4, 2.5, 3.4, 12.1, 12.2, 12.3, 12.4**
    - New file `tests/dast/test_schemathesis_prop17_hard_failure.py`

  - [x] 4.11 Write unit tests for scan edge cases and run-stats parsing
    - Anonymous run when `auth_header` unset → no `--header`, no `Authorization` in env
      (Req 2.4); proxy off when host/port absent → no `--request-proxy`, no `HTTP_PROXY`
      (Req 3.2); empty/invalid seed on fast → `ScannerError` (Req 4.4); deep runs
      without a seed (Req 4.2); production refusal sends nothing and raises (Req 14.3);
      `requests_made`/`request_errors`/`timeouts` read from the saved run-stats fixture,
      not the generated-case count (Req 11.4)
    - New file `tests/dast/test_schemathesis_scan.py`
    - _Requirements: 2.4, 3.2, 4.2, 4.4, 11.4, 14.3_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Wire Schemathesis into the runner
  - [x] 6.1 Add `SchemathesisAdapter` to `default_adapters(profile)` in `dast/runner.py`
    - Append `SchemathesisAdapter()` (present in both `fast` and `deep`) **before** the
      active `ZapAdapter(active=True)` so the runner, which builds the serial mutating
      tier by filtering while preserving list order, executes Schemathesis first and
      seeds ZAP's site tree before the active scan; Schemathesis still runs on its own
      when the active ZAP adapter is absent (fast profile)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x] 6.2 Write property test: present in both profiles and ordered before the active ZAP scan
    - **Property 15: Schemathesis is present in both profiles and ordered before the active ZAP scan**
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5**
    - New file `tests/dast/test_schemathesis_prop15_profile_order.py`

  - [x] 6.3 Write property test: request evidence, not generated-case count, drives complete/incomplete
    - **Property 13: request evidence, not generated-case count, drives complete/incomplete**
    - **Validates: Requirements 11.2, 11.3, 11.4, 13.5**
    - New file `tests/dast/test_schemathesis_prop13_request_evidence.py`

  - [x] 6.4 Write unit tests for profile selection and the mutating flag
    - `default_adapters("fast")` and `default_adapters("deep")` each contain exactly one
      Schemathesis adapter (Req 10.1, 10.2); in `deep` it precedes the active ZAP adapter
      in the mutating tier (Req 10.4); `mutating is True` (Req 10.3)
    - New file `tests/dast/test_runner_schemathesis.py`
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 7. Bake the pinned Schemathesis CLI into deployment
  - [x] 7.1 Add the pinned Schemathesis install to `Dockerfile.dast` and DAST env wiring to docker-compose
    - Add a `pip install "schemathesis==${SCHEMATHESIS_VERSION}"` layer to
      `Dockerfile.dast` (pinned to an exact released version via an `ARG`, never
      `latest`, verified with `schemathesis --version`), mirroring the pinned-nuclei
      pattern — no Schemathesis sidecar; set the `DAST_SCHEMATHESIS_*` env vars on the
      DAST service in docker-compose and reuse the Phase 3 ZAP sidecar as the proxy via
      the existing `DAST_ZAP_HOST` / `DAST_ZAP_PORT`
    - _Requirements: 3.2, 14.1_

- [x] 8. Integration and final validation
  - [x] 8.1 Write integration tests against real Schemathesis + the ZAP sidecar + a buggy API target
    - Dual payoff: a scan through the ZAP proxy leaves ZAP's site tree populated with
      authenticated endpoints, before the active ZAP scan (Req 3.1, 3.3, 10.4); an
      endpoint that 500s on malformed input yields a high-severity finding with a
      reissuable reproducing request (Req 5.1); a response violating its schema yields a
      schema-violation finding (Req 7.1); a completed run produces a `schemathesis`
      coverage entry with non-zero `requests_made` read from the tool's own stats
      (Req 11.1)
    - New file `tests/dast/test_schemathesis_integration.py`
    - _Requirements: 3.1, 3.3, 5.1, 7.1, 10.4, 11.1_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test tasks and can be skipped for a faster MVP.
- Each task references specific requirements (granular clauses) for traceability.
- Property tests validate the 17 universal correctness properties from the design;
  each property is its own sub-task placed close to the code it checks (Properties 1–8
  next to `parse()`, 9–14/16/17 next to `scan()`, 13/15 next to the runner wiring).
- Unit and integration tests cover examples, edge cases, and the Schemathesis CLI /
  network / ZAP-proxy boundary that property tests deliberately fake out via the
  command-builder + `run_scanner` seam.
- Every property test file should be tagged with a comment in the form
  `# Feature: dast-schemathesis, Property {number}: {property_text}` and run ≥100
  examples (Hypothesis `max_examples` ≥ 100).
- There is **no shared-model change** in this phase; the reproducing request rides in
  the existing `Finding.raw`, and all trust guarantees route through the existing
  runner (`_run_one` / `_assess_activity`). The ZAP proxy reuses the Phase 3
  `DAST_ZAP_HOST` / `DAST_ZAP_PORT` settings — no new proxy plumbing.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "7.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "2.5", "2.6", "2.7", "2.8", "2.9", "2.10", "4.1"] },
    { "id": 3, "tasks": ["4.2", "4.3"] },
    { "id": 4, "tasks": ["4.4", "4.5", "4.6", "4.7", "4.8", "4.9", "4.10", "4.11", "6.1"] },
    { "id": 5, "tasks": ["6.2", "6.3", "6.4"] },
    { "id": 6, "tasks": ["8.1"] }
  ]
}
```
