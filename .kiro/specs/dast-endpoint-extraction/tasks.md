# Implementation Plan: DAST Endpoint Extraction

## Overview

This plan builds the endpoint-extraction feature as a new **pure** Python package under
`dast/endpoints/` (sibling to `dast/adapters/`), plus a small additive wiring change at
the service seam. It follows the design: extraction models, a `LanguageExtractor`
protocol with per-language extractors (Python / JavaScript-TypeScript / Go / Ruby), path
normalisation, deterministic dedup, reconciliation with the runtime spec, OpenAPI
synthesis/parse, the `EndpointExtractor` orchestrator, `DAST_`-prefixed config, and the
additive `ScanRequest.source_root` + `_assemble_scope` wiring.

Each step is test-driven and builds on the previous one. The pure leaf functions
(normalise, dedup, reconcile, synthesise/parse) are implemented and property-tested
first, the orchestrator wires them over a real (temp-dir) filesystem, and the final
steps wire the reconciled `spec_paths` into `DastScope` so the existing ZAP and
Schemathesis adapters seed themselves with **no adapter changes**. Nothing is left
orphaned: every module is imported and exercised by a later step and ultimately reached
from the service seam.

Implementation language: **Python** (matches the existing `dast/` and `app/security/`
packages; the design is written in Python, so no language selection is needed).
Property-based tests use **Hypothesis** (already in the repo), each running **≥ 100
examples** and tagged
`# Feature: dast-endpoint-extraction, Property {number}: {property_text}`.

## Tasks

- [x] 1. Add extraction configuration and the extraction data models
  - [x] 1.1 Add `DAST_EXTRACT_*` settings to `dast/config.py`
    - Add `DAST_EXTRACT_EXCLUDE_PATTERNS` (default
      `node_modules,vendor,.git,dist,build,__pycache__,.venv,venv,.tox,target`) and
      `DAST_EXTRACT_MAX_FILE_BYTES` (default `1048576`), both `DAST_`-prefixed, never
      `SECURITY_`-prefixed, with finite/positive/non-empty defaults so an absent setting
      still yields safe, bounded traversal
    - Expose the exclusion patterns as a parsed comma-separated collection
    - _Requirements: 1.10, 1.11, 9.1, 9.2, 9.5, 9.6_

  - [x] 1.2 Create the extraction models in `dast/endpoints/models.py` and package `__init__.py`
    - Define `ParameterKind` (PATH/QUERY), `EndpointParameter`, `ExtractedEndpoint`
      (with the `identity` property `(method, path)`), `EndpointInventory`,
      `ExtractionActivity`, `ExtractionResult`, and the `ExtractionError` exception, all
      as frozen dataclasses / enum matching the `dast/models.py` style
    - Enforce invariants by construction: `method` in {GET,POST,PUT,PATCH,DELETE};
      `parameters` never affects `identity`
    - _Requirements: 1.1, 3.1, 5.1, 11.1_

  - [ ]* 1.3 Write unit tests for config defaults and naming
    - Assert defaults load when unset (non-empty exclusion set covering dependency +
      VCS dirs; finite positive max-bytes); assert every extraction setting name begins
      with `DAST_` and none begins with `SECURITY_`
    - New file `tests/dast/test_extract_config.py`
    - _Requirements: 1.10, 1.11, 9.1, 9.2, 9.5, 9.6_

- [x] 2. Implement the extraction extension point and path normalisation
  - [x] 2.1 Define the `LanguageExtractor` protocol and `RawRoute` in `dast/endpoints/base.py`
    - Add the `@runtime_checkable` `LanguageExtractor` Protocol (`language`, `matches`,
      `discover`) and the frozen `RawRoute` dataclass (`methods`, `raw_path`, `line`,
      `query_parameters`), duck-typed like `DastAdapter`; document that `discover` is
      pure and must never execute/import/evaluate/invoke source
    - _Requirements: 2.1, 2.5, 1.5, 1.6, 1.7, 1.8_

  - [x] 2.2 Implement `normalize_route_path` in `dast/endpoints/normalize.py`
    - Return `(path_template, ordered path-parameter names)`; map `:name`, `<name>`,
      `<type:name>`, `{name}`, and bare `*` segments to the shared
      `dast.urls.PLACEHOLDER` (`{id}`); enforce single leading `/`, no scheme/host,
      collapse `//`, strip trailing `/` except root; return declared segment names
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 3.4_

  - [ ]* 2.3 Write property test for normalisation canonical form
    - **Property 7: Path normalisation produces one idempotent canonical form**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**
    - New file `tests/dast/test_extract_prop07_normalize_canonical.py`

  - [ ]* 2.4 Write property test for the identity fixed point
    - **Property 8: A normalised template is a fixed point of the scanner's identity function**
    - **Validates: Requirements 4.6**
    - New file `tests/dast/test_extract_prop08_identity_fixed_point.py`

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement the per-language extractors and the registry
  - [x] 4.1 Implement `PythonExtractor` in `dast/endpoints/languages/python.py`
    - `matches()` on `.py`; `discover()` uses `ast.parse` (no execution) to walk
      decorators for Flask/FastAPI `@app.route`/`@app.get`/`@router.post` etc., emitting
      `RawRoute`s with methods, native path, and 1-based line
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3, 1.5, 1.6, 1.7, 1.8_

  - [ ]* 4.2 Write unit tests for the Python extractor
    - Assert the exact `(method, path)` set from a Flask/FastAPI fixture (reuse/extend
      `security_samples/multilang/`); cover multi-method and no-method-defaults-GET
    - New file `tests/dast/test_extract_python.py`
    - _Requirements: 2.2, 3.1, 3.2, 3.3_

  - [x] 4.3 Implement `JavaScriptExtractor` in `dast/endpoints/languages/javascript.py`
    - `matches()` on `.js`/`.ts`; line/token regex scan for Express
      `app.get("/u/:id", ...)`, `router.post(...)`, `app.use("/mount", r)`, emitting
      `RawRoute`s with methods, native path, and 1-based line
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3, 1.5, 1.6, 1.7, 1.8_

  - [ ]* 4.4 Write unit tests for the JavaScript/TypeScript extractor
    - Assert the exact `(method, path)` set from an Express fixture
      (`security_samples/multilang/api.ts`), including base-path + method-path joining
    - New file `tests/dast/test_extract_javascript.py`
    - _Requirements: 2.2, 3.1, 3.2_

  - [x] 4.5 Implement `GoExtractor` in `dast/endpoints/languages/go.py`
    - `matches()` on `.go`; line/token regex scan for `net/http` `http.HandleFunc(...)`
      and `mux.HandleFunc(...)`, emitting `RawRoute`s (default GET when no method,
      Req 3.3) with 1-based line
    - _Requirements: 2.1, 2.2, 3.1, 3.3, 1.5, 1.6, 1.7, 1.8_

  - [ ]* 4.6 Write unit tests for the Go extractor
    - Assert the exact `(method, path)` set from a `net/http` fixture
      (`security_samples/multilang/handler.go`), including the GET default
    - New file `tests/dast/test_extract_go.py`
    - _Requirements: 2.2, 3.1, 3.3_

  - [x] 4.7 Implement `RubyExtractor` in `dast/endpoints/languages/ruby.py`
    - `matches()` on `.rb`; line/token regex scan for Sinatra `get "/u/:id" do` and
      Rails `get "/u/:id" => ...`, emitting `RawRoute`s with methods, native path, and
      1-based line
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3, 1.5, 1.6, 1.7, 1.8_

  - [ ]* 4.8 Write unit tests for the Ruby extractor
    - Assert the exact `(method, path)` set from a Sinatra/Rails fixture
      (`security_samples/multilang/service.rb`)
    - New file `tests/dast/test_extract_ruby.py`
    - _Requirements: 2.2, 3.1, 3.2_

  - [x] 4.9 Implement `default_language_extractors()` in `dast/endpoints/registry.py`
    - Return the ordered list `[PythonExtractor(), JavaScriptExtractor(), GoExtractor(),
      RubyExtractor()]`, resolved once (analogous to `default_adapters`); one extractor
      per language/framework
    - _Requirements: 2.1, 2.5_

  - [ ]* 4.10 Write unit tests for the registry
    - Assert one extractor per language; adding a new extractor leaves the existing ones
      unchanged and still functioning (Req 2.5)
    - New file `tests/dast/test_extract_registry.py`
    - _Requirements: 2.1, 2.5_

- [x] 5. Implement deterministic deduplication
  - [x] 5.1 Implement `deduplicate` in `dast/endpoints/dedup.py`
    - Collapse endpoints sharing `(method, path_template)`: retained source location is
      the minimum by `(repo-relative path, line)`; parameters are the union keyed by
      name; output sorted by `(path_template, method)`
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ]* 5.2 Write property test for deterministic order-independent dedup
    - **Property 9: Deduplication is deterministic and order-independent**
    - **Validates: Requirements 5.1, 5.2, 5.3**
    - New file `tests/dast/test_extract_prop09_dedup.py`

- [x] 6. Implement the EndpointExtractor orchestrator
  - [x] 6.1 Implement `EndpointExtractor.extract` in `dast/endpoints/extractor.py`
    - Root check (raise `ExtractionError` on missing/non-dir, Req 10.2); bounded
      `os.walk` with in-place `dirnames[:]` exclusion pruning (Req 9.3, 9.4); resolved
      path-confinement skip (Req 1.3, 1.4); size bound before read (Req 9.7); dispatch
      to the union of matching extractors (Req 2.2-2.4); read/parse resilience skip
      (Req 10.1); route → endpoints per supported method with GET default and unsupported
      verbs dropped (Req 3.1-3.5); call `deduplicate`; build `ExtractionActivity`
      (files_read, endpoints_found, languages) and return `ExtractionResult`; no network
      I/O; deterministic across runs; wire in `default_language_extractors()` and
      `dast_settings`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.9, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 9.3, 9.4, 9.7, 10.1, 10.2, 10.3, 10.4, 11.1_

  - [ ]* 6.2 Write property test for deterministic extraction
    - **Property 1: Extraction is deterministic**
    - **Validates: Requirements 1.1, 1.9**
    - New file `tests/dast/test_extract_prop01_deterministic.py`

  - [ ]* 6.3 Write property test for root-confined traversal
    - **Property 2: Traversal never reads outside the repository root**
    - **Validates: Requirements 1.3, 1.4**
    - New file `tests/dast/test_extract_prop02_confinement.py`

  - [ ]* 6.4 Write property test for no code execution
    - **Property 3: Extraction never executes target code**
    - **Validates: Requirements 1.5, 1.6, 1.7, 1.8**
    - New file `tests/dast/test_extract_prop03_no_execution.py`

  - [ ]* 6.5 Write property test for union dispatch
    - **Property 4: File dispatch is the union of matching Language_Extractors**
    - **Validates: Requirements 2.2, 2.3, 2.4**
    - New file `tests/dast/test_extract_prop04_dispatch_union.py`

  - [ ]* 6.6 Write property test for complete per-method recording
    - **Property 5: Every discovered route is recorded completely and per supported method**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.5**
    - New file `tests/dast/test_extract_prop05_route_recording.py`

  - [ ]* 6.7 Write property test for named path parameters
    - **Property 6: Dynamic path segments become named path parameters**
    - **Validates: Requirements 3.4**
    - New file `tests/dast/test_extract_prop06_path_params.py`

  - [ ]* 6.8 Write property test for bounded traversal
    - **Property 16: Traversal is bounded by exclusions and file size**
    - **Validates: Requirements 9.3, 9.4, 9.7**
    - New file `tests/dast/test_extract_prop16_bounded_traversal.py`

  - [ ]* 6.9 Write property test for degradation resilience
    - **Property 17: One broken file never discards the rest**
    - **Validates: Requirements 10.1, 10.3, 10.4**
    - New file `tests/dast/test_extract_prop17_degradation.py`

  - [ ]* 6.10 Write property test for honest activity counts
    - **Property 18: Extraction activity reports honest counts**
    - **Validates: Requirements 11.1**
    - New file `tests/dast/test_extract_prop18_activity_counts.py`

  - [ ]* 6.11 Write unit tests for orchestrator edge cases
    - Bad root (missing path and file-as-root) each raise `ExtractionError` naming the
      path with no inventory (Req 10.2); extraction completes with sockets disabled
      (no network I/O, Req 1.2); a repo with no routes returns an empty inventory
      (Req 10.3)
    - New file `tests/dast/test_extractor.py`
    - _Requirements: 1.2, 10.2, 10.3_

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement reconciliation with the runtime spec
  - [x] 8.1 Implement `reconcile` in `dast/endpoints/reconcile.py`
    - Union spec templates with inventory templates; distinct identities once; on clash
      keep the OpenAPI_Spec template and drop the inventory one (canonicalise `{...}`
      segments to `{id}` only for comparison, preserve retained text); handle
      empty-spec / empty-inventory / both-empty; order spec templates first then
      inventory-only templates
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 8.2 Write property test for reconciliation
    - **Property 10: Reconciliation is the identity-distinct union that retains spec templates**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**
    - New file `tests/dast/test_extract_prop10_reconcile.py`

- [ ] 9. Implement OpenAPI synthesis and parsing
  - [x] 9.1 Implement synthesis/parse in `dast/endpoints/synthesize.py`
    - `synthesize_openapi(inventory)` → minimal OpenAPI 3.0 dict (one path entry per
      template, one operation per method, each `{id}` a required `string` path param,
      query params optional; empty inventory → valid doc with empty `paths`);
      `synthesize_openapi_bytes(inventory)` serialises with sorted keys and fixed
      separators for byte-identical output; `parse_openapi(document)` reads identities
      back (supported methods only, tolerates missing/empty `paths`)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 9.2 Write property test for schema structure
    - **Property 12: The synthesised schema has one operation per endpoint with `{id}` as a required path parameter**
    - **Validates: Requirements 8.1, 8.5**
    - New file `tests/dast/test_extract_prop12_schema_structure.py`

  - [ ]* 9.3 Write property test for schema loadability
    - **Property 13: The synthesised schema is always loadable**
    - **Validates: Requirements 8.2, 8.4**
    - New file `tests/dast/test_extract_prop13_schema_loadable.py`

  - [ ]* 9.4 Write property test for the synthesise→parse round-trip
    - **Property 14: Synthesise then parse preserves endpoint identities (round-trip)**
    - **Validates: Requirements 8.3**
    - New file `tests/dast/test_extract_prop14_roundtrip.py`

  - [ ]* 9.5 Write property test for byte-deterministic synthesis
    - **Property 15: Schema synthesis is byte-deterministic**
    - **Validates: Requirements 8.6**
    - New file `tests/dast/test_extract_prop15_byte_deterministic.py`

- [x] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Wire extraction into the service seam (additive only)
  - [x] 11.1 Add optional `source_root` to `ScanRequest` in `dast/models.py`
    - Add `source_root: Optional[str] = None` (the checked-out repo to extract endpoints
      from); no other model changes
    - _Requirements: 1.1_

  - [x] 11.2 Assemble the reconciled scope in `dast/service.py`
    - In scope assembly, run `EndpointExtractor().extract(source_root)` when
      `source_root` is set (else empty inventory/activity); `reconcile(preflight
      spec_paths, inventory paths)` and place the result on `DastScope.spec_paths`
      verbatim (Req 7.1-7.4); record `preflight["extraction"]` (activity) and
      `preflight["spec_seed"]` (`seed_count`, `seeded`) (Req 11.4, 11.5); on empty
      spec, write `synthesize_openapi_bytes` to a temp file and point
      `DAST_SCHEMATHESIS_SCHEMA_FILE` at it; empty inventory AND empty spec → unseeded,
      never clean (Req 11.2, 11.3)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 11.2, 11.3, 11.4, 11.5_

  - [ ]* 11.3 Write property test for `spec_paths` equalling the reconciled set
    - **Property 11: DastScope.spec_paths equals the reconciled set exactly**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    - New file `tests/dast/test_extract_prop11_spec_paths.py`

  - [ ]* 11.4 Write property test for the unseeded-never-clean rule
    - **Property 19: An unseeded scan surface is never clean**
    - **Validates: Requirements 11.2, 11.3, 11.4, 11.5**
    - New file `tests/dast/test_extract_prop19_unseeded.py`

  - [ ]* 11.5 Write unit tests for the seam wiring
    - With a provided `source_root`, assembled `DastScope.spec_paths` equals the
      reconciled set and the preflight record carries the `extraction` and `spec_seed`
      blocks; when the target has no spec, a synthesised schema file is produced and
      pointed at by `DAST_SCHEMATHESIS_SCHEMA_FILE`
    - New file `tests/dast/test_extract_seam.py`
    - _Requirements: 7.1, 8.1, 11.4, 11.5_

- [ ] 12. Integration and final validation
  - [ ]* 12.1 Write end-to-end seam integration tests
    - A small fixture repo → `EndpointExtractor.extract` → `reconcile` →
      `DastScope.spec_paths`, asserting ZAP would seed exactly those paths and
      Schemathesis would load the synthesised schema; 1-3 representative repos, not
      run 100×
    - New file `tests/dast/test_extract_integration.py`
    - _Requirements: 7.1, 8.2, 11.4_

- [x] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test tasks and can be skipped for a faster MVP.
- Each task references specific requirements (granular clauses) for traceability.
- Property tests validate the 19 universal correctness properties from the design; each
  property is its own sub-task placed close to the code it checks.
- Every property test file is tagged with a comment in the form
  `# Feature: dast-endpoint-extraction, Property {number}: {property_text}` and runs
  ≥ 100 examples (Hypothesis).
- Traversal-based properties (2, 3, 16, 17, 18) build generated directory trees under a
  Hypothesis-managed temp directory — no network, no live target.
- Unit and integration tests cover per-language fixtures, config naming/defaults, the
  bad-root error, and the service-seam wiring that the pure property tests deliberately
  do not exercise.
- The only existing-code changes are additive: `dast/config.py` (two `DAST_` settings),
  `ScanRequest.source_root` in `dast/models.py`, and `_assemble_scope` in
  `dast/service.py`. No adapter changes — the reconciled templates flow through the
  existing `DastScope.spec_paths` contract.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1", "2.2", "5.1", "8.1", "9.1"] },
    { "id": 2, "tasks": ["2.3", "2.4", "5.2", "8.2", "9.2", "9.3", "9.4", "9.5", "4.1", "4.3", "4.5", "4.7"] },
    { "id": 3, "tasks": ["4.2", "4.4", "4.6", "4.8", "4.9"] },
    { "id": 4, "tasks": ["4.10", "6.1"] },
    { "id": 5, "tasks": ["6.2", "6.3", "6.4", "6.5", "6.6", "6.7", "6.8", "6.9", "6.10", "6.11"] },
    { "id": 6, "tasks": ["11.1", "11.2"] },
    { "id": 7, "tasks": ["11.3", "11.4", "11.5"] },
    { "id": 8, "tasks": ["12.1"] }
  ]
}
```
