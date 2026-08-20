# Implementation Plan: DAST ZAP Integration (Phase 3)

## Overview

This plan integrates OWASP ZAP as a dynamic scanner into the existing standalone
DAST service. It follows the design: a `ZapClient` REST wrapper, a `ZapAdapter`
with a pure `parse()` and an impure `scan()`, profile-aware adapter selection in the
runner, and a pinned ZAP sidecar. Each step builds on the previous one and ends by
wiring ZAP into the runner and deployment so nothing is left orphaned.

The work reuses the existing `DastAdapter` protocol, `DastScope`, `ScanOutcome`,
`ToolActivity`, `ToolCoverage`, the shared `Finding`, and the normalize → dedupe →
baseline chain. The single new shared-model change is one optional `Finding.advisory`
field. All trust guarantees route through the existing `_run_one` / `_assess_activity`
logic in `dast/runner.py`.

Implementation language: **Python** (matches the existing `dast/` and
`app/security/` packages). Property-based tests use Hypothesis, already in the repo.

## Tasks

- [x] 1. Add ZAP configuration and the advisory finding field
  - [x] 1.1 Add `DAST_ZAP_*` settings to `dast/config.py`
    - Add `DAST_ZAP_HOST`, `DAST_ZAP_PORT`, `DAST_ZAP_API_KEY`, `DAST_ZAP_IMAGE`
      (pinned digest, never `latest`), `DAST_ZAP_LOGOUT_EXCLUDE`, `DAST_ZAP_RATE_LIMIT`,
      `DAST_ZAP_COVERAGE_TOLERANCE`, `DAST_ZAP_CANARY_PATH`, `DAST_ZAP_TIMEOUT`,
      `DAST_ZAP_TIMEOUT_THRESHOLD`, `DAST_ZAP_PROD_URL_PATTERN` with the documented
      defaults, all `DAST_`-prefixed
    - _Requirements: 1.1, 1.4, 4.1, 4.3, 6.4, 7.1, 10.1, 10.2, 11.1, 11.2, 12.1, 12.2, 12.3_

  - [x] 1.2 Add optional `advisory` field to the shared `Finding` model
    - Add `advisory: bool = False` to `Finding` in `app/security/models.py`,
      defaulting to `False` so nuclei and all SAST adapters are unaffected
    - _Requirements: 6.5_

  - [ ]* 1.3 Write unit tests for config defaults and the pinned image
    - Assert defaults load and that `DAST_ZAP_IMAGE` is a digest/version, never `latest`
    - New file `tests/dast/test_zap_config.py`
    - _Requirements: 11.1, 11.2, 12.1_

- [x] 2. Implement the ZapClient REST wrapper
  - [x] 2.1 Implement `ZapClient` in `dast/adapters/zap_client.py`
    - Synchronous `httpx` wrapper keyed by host/port/API key from config, exposing:
      `reachable()`, `new_session()`, `exclude_from_scan()`, `set_replacer_rule()`,
      `import_openapi()` / `spider()`, `passive_scan_wait()`, `active_scan()`,
      `alerts()`, request-evidence counters (`requests_made`, `request_errors`,
      `timeouts`), and `canary_detected()`
    - Wrap every transport failure as `ScannerError` (reuse
      `app.security.detection.adapters.base.ScannerError`)
    - _Requirements: 1.1, 1.3, 2.1, 2.2, 3.1, 4.1, 5.1, 7.1, 8.1, 9.3, 13.1, 13.2_

  - [x] 2.2 Implement an in-memory fake ZAP for tests
    - New helper `tests/dast/_zap_fakes.py` implementing the narrow `ZapClient`
      interface, recording session state, seeded endpoints, every outgoing request
      (URL + headers), and configurable canary/alert responses so property tests run
      with no network
    - _Requirements: (test infrastructure supporting Properties 5-10, 13)_

  - [ ]* 2.3 Write unit tests for ZapClient wiring and error handling
    - Reachable → proceeds; unreachable → raises before any scan command (Req 1.3);
      REST-only, no per-scan process start (Req 1.1, 1.2); failed session start and
      mid-scan disconnect wrap as `ScannerError` (Req 2.3, 13.2)
    - New file `tests/dast/test_zap_client.py`
    - _Requirements: 1.1, 1.2, 1.3, 2.3, 13.1, 13.2_

- [x] 3. Implement the pure ZapAdapter.parse layer
  - [x] 3.1 Create `ZapAdapter` scaffold and pure `parse()` in `dast/adapters/zap_adapter.py`
    - Define `name`/`mutating` attributes and constructor (`active`, `client`,
      `settings`); implement `parse(alerts, *, spec_paths, scanner_name, advisory)`
      as a pure classmethod building shared `Finding` objects via `make_web_location`
      (severity map, stable `rule_id`, message), mirroring `NucleiAdapter.parse`;
      set `advisory` on every produced finding
    - _Requirements: 8.1, 8.2, 6.5_

  - [ ]* 3.2 Write property test: parse is pure and deterministic
    - **Property 1: parse() is pure and deterministic**
    - **Validates: Requirements 8.1**
    - New file `tests/dast/test_zap_prop01_parse_pure.py`

  - [ ]* 3.3 Write property test: parsed findings are fully populated
    - **Property 2: parsed findings are fully populated**
    - **Validates: Requirements 8.1**
    - New file `tests/dast/test_zap_prop02_findings_populated.py`

  - [ ]* 3.4 Write property test: URL templatisation yields stable identity
    - **Property 3: URL templatisation yields stable finding identity**
    - **Validates: Requirements 8.2**
    - New file `tests/dast/test_zap_prop03_templatise_identity.py`

  - [ ]* 3.5 Write property test: duplicate alerts collapse to one finding
    - **Property 4: duplicate alerts collapse to one finding**
    - **Validates: Requirements 8.3, 8.4**
    - New file `tests/dast/test_zap_prop04_dedupe.py`

  - [ ]* 3.6 Write property test: active findings advisory, passive not
    - **Property 14: active findings are advisory, passive findings are not**
    - **Validates: Requirements 6.5**
    - New file `tests/dast/test_zap_prop14_advisory.py`

  - [ ]* 3.7 Write unit test for parse against a saved ZAP alert fixture
    - Capture a real `core.alerts` payload as `tests/dast/fixtures/zap_alerts.json`
      and assert ZAP field names map correctly through `parse()`
    - New file `tests/dast/test_zap_adapter.py`
    - _Requirements: 8.1_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement the impure ZapAdapter.scan orchestration
  - [x] 5.1 Implement `ZapAdapter.scan()` in `dast/adapters/zap_adapter.py`
    - Orchestrate the sequence: reachability → fresh session → logout exclusion →
      auth replacer rule (skip when `auth_header` unset) → seed from OpenAPI spec
      (record seeded count into `units_executed`; raise `ScannerError` when
      `spec_paths` empty) → start-of-scan canary → passive scan (always) → active
      scan (active adapter only, refuse against production target) → collect alerts
      and request evidence → end-of-scan canary → under-seeding tolerance check →
      build `ScanOutcome` with `parse(..., advisory=active)`
    - Signal hard failures via `ScannerError`; return truthful `ToolActivity` for
      soft-evidence cases; apply the configured rate limit to the scan policy
    - _Requirements: 1.3, 2.1, 2.2, 3.1, 3.2, 3.3, 4.1, 4.2, 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 7.4, 7.5, 9.1, 9.2, 9.3, 10.1, 10.2, 12.2, 13.1, 13.2_

  - [x] 5.2 Export the ZAP adapters from `dast/adapters/__init__.py`
    - Add `ZapAdapter` (and any factory) to the package exports alongside `NucleiAdapter`
    - _Requirements: 9.1, 9.2_

  - [ ]* 5.3 Write property test: auth header injected on every outgoing request
    - **Property 5: the auth header is injected on every outgoing request**
    - **Validates: Requirements 3.1, 3.3, 5.4**
    - New file `tests/dast/test_zap_prop05_auth_everywhere.py`

  - [ ]* 5.4 Write property test: the logout URL is never requested
    - **Property 6: the logout URL is never requested**
    - **Validates: Requirements 4.1, 4.2**
    - New file `tests/dast/test_zap_prop06_logout_excluded.py`

  - [ ]* 5.5 Write property test: a fresh session carries no prior state
    - **Property 7: a fresh session carries no prior state**
    - **Validates: Requirements 2.1, 2.2**
    - New file `tests/dast/test_zap_prop07_fresh_session.py`

  - [ ]* 5.6 Write property test: seeding covers the spec and records its count
    - **Property 8: seeding covers the spec and records its count**
    - **Validates: Requirements 5.1, 5.2**
    - New file `tests/dast/test_zap_prop08_seeding_count.py`

  - [ ]* 5.7 Write property test: an under-seeded map is reported incomplete
    - **Property 9: an under-seeded map is reported incomplete**
    - **Validates: Requirements 10.1, 10.2**
    - New file `tests/dast/test_zap_prop09_underseeded.py`

  - [ ]* 5.8 Write property test: canary must fire at both boundaries
    - **Property 10: coverage is complete only when the canary fires at both boundaries**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**
    - New file `tests/dast/test_zap_prop10_canary_boundaries.py`

  - [ ]* 5.9 Write property test: active scanning never runs against production
    - **Property 13: active scanning never runs against a production target**
    - **Validates: Requirements 6.4**
    - New file `tests/dast/test_zap_prop13_no_active_prod.py`

  - [ ]* 5.10 Write unit tests for scan edge cases
    - Anonymous scan when `auth_header` unset → no replacer rule (Req 3.2); empty
      `spec_paths` → `incomplete` "not seeded" (Req 5.3); reachability precondition
      (Req 1.3); mid-scan disconnect → `incomplete` (Req 13.2); rate limit applied
      to the scan policy (Req 12.2)
    - New file `tests/dast/test_zap_scan.py`
    - _Requirements: 1.3, 3.2, 5.3, 12.2, 13.2_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Wire profile-aware ZAP selection into the runner
  - [x] 7.1 Make `default_adapters(profile)` profile-aware in `dast/runner.py`
    - Always append a passive `ZapAdapter(active=False)`; append an active
      `ZapAdapter(active=True)` only for the `deep` profile, so the runner tiers the
      passive adapter into the concurrent read-only tier and the active adapter into
      the serial mutating tier
    - _Requirements: 6.1, 6.2, 6.3, 9.1, 9.2, 10.4_

  - [ ]* 7.2 Write property test: active scanning never runs under fast profile
    - **Property 12: active scanning never runs under the fast profile**
    - **Validates: Requirements 6.1, 6.2**
    - New file `tests/dast/test_zap_prop12_no_active_fast.py`

  - [ ]* 7.3 Write property test: no request evidence means no clean result
    - **Property 11: no request evidence means no clean result**
    - **Validates: Requirements 9.3, 9.4, 9.5, 12.3**
    - New file `tests/dast/test_zap_prop11_request_evidence.py`

  - [ ]* 7.4 Write property test: one failing tool never aborts the scan
    - **Property 15: one failing tool never aborts the scan**
    - **Validates: Requirements 13.1, 13.2, 13.3**
    - New file `tests/dast/test_zap_prop15_isolation.py`

  - [ ]* 7.5 Write unit tests for profile selection and tier flags
    - `default_adapters("fast")` includes `zap-passive` and excludes `zap-active`
      (Req 10.4); passive declares `mutating=False`, active declares `mutating=True`
      (Req 9.1, 9.2)
    - New file `tests/dast/test_runner_zap.py`
    - _Requirements: 9.1, 9.2, 10.4_

- [x] 8. Wire the pinned ZAP sidecar into deployment
  - [x] 8.1 Add the pinned ZAP sidecar service and DAST env wiring
    - Add a `zap` service to `docker-compose` pinned by digest (never `latest`) in
      daemon mode, and set `DAST_ZAP_HOST`/`DAST_ZAP_PORT`/`DAST_ZAP_API_KEY`/
      `DAST_ZAP_CANARY_PATH` on the DAST service so it reaches the warm daemon over
      the compose network
    - _Requirements: 1.1, 1.2, 11.1, 11.2_

- [ ] 9. Integration and final validation
  - [ ]* 9.1 Write integration tests against a real pinned ZAP sidecar
    - Deep scan against a build with the canary route reports the canary XSS
      (Req 10.3); importing a real OpenAPI spec discovers an endpoint count within
      tolerance (Req 5.1, 10.1); a fast-profile scan produces a `zap-passive`
      coverage entry with real `requests_made` (Req 10.4)
    - New file `tests/dast/test_zap_integration.py`
    - _Requirements: 5.1, 10.1, 10.3, 10.4_

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test tasks and can be skipped for a faster MVP.
- Each task references specific requirements (granular clauses) for traceability.
- Property tests validate the 15 universal correctness properties from the design;
  each property is its own sub-task placed close to the code it checks.
- Unit and integration tests cover examples, edge cases, and the ZAP/network I/O
  boundary that property tests deliberately fake out.
- Every property test file should be tagged with a comment in the form
  `# Feature: dast-zap, Property {number}: {property_text}` and run ≥100 examples.
- The only shared-model change is `Finding.advisory`; all other trust guarantees
  route through the existing runner (`_run_one` / `_assess_activity`).

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1", "3.1", "8.1"] },
    { "id": 2, "tasks": ["2.2", "5.1"] },
    { "id": 3, "tasks": ["2.3", "3.2", "3.3", "3.4", "3.5", "3.6", "3.7", "5.2", "5.3", "5.4", "5.5", "5.6", "5.7", "5.8", "5.9", "5.10"] },
    { "id": 4, "tasks": ["7.1"] },
    { "id": 5, "tasks": ["7.2", "7.3", "7.4", "7.5"] },
    { "id": 6, "tasks": ["9.1"] }
  ]
}
```
