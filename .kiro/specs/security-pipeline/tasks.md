# Implementation Plan: DeliveryOS Security Pipeline

## Overview

This plan implements the four-layer security pipeline **inside the existing DeliveryOS codebase** (`app/`) rather than as a greenfield project. DeliveryOS already provides the webhook trigger, a sequential `WorkflowOrchestrator` that runs `Stage` objects and stops on first failure, a `WorkflowContext` shared-state object, a Layer-1-equivalent repository intelligence stack (git diff, SQLite AST index, planner, retriever, prompter), a validation/repair loop, an LLM service with caching, a repair-agent pattern, merge-confidence scoring, and PR creation. This plan therefore **reuses and extends** those modules and only **builds net-new** the security-specific pieces: the six deterministic scanners, the security intelligence core (normalize/dedup/enrich/score/triage/repair/verify), the SonarQube quality gate, per-repo `Repo_Config`, and the security-augmented report and merge-confidence.

The project, its `venv` (`ai-delivery/venv`), `pytest`, and package layout **already exist** — there is no project-setup or dependency-scaffolding task. The only new test dependency is **Hypothesis** (for property tests), installed into the existing venv. New code lives under `app/security/` and new `Stage` subclasses plug into the existing `WorkflowOrchestrator`; extensions modify existing modules in place.

### Reuse vs. build map (each task cites the real module it touches)

```
Trigger        REUSE  app/github/routes.py (github_webhook, verify_signature)
Orchestration  REUSE  app/workflows/orchestrator.py + stages.py (Stage base)
Shared state   EXTEND app/workflows/context.py (WorkflowContext, EngineeringTask)
Layer 1        EXTEND app/services/repository/{indexer,retriever,db}.py  (+ call/dep graphs, unparseable)
Layer 2        NEW    app/security/detection/  (six scanner adapters + parallel runner stage)
Layer 3 core   NEW    app/security/intelligence/  (normalize/dedup/enrich/score — pure)
Layer 3 AI     REUSE  app/services/llm_service.py + app/agents/repair/agent.py pattern
Layer 3 verify REUSE  scanner re-run + app/services/validators.py approach
Layer 4 gate   NEW    app/security/governance/quality_gate.py (SonarQube)
Layer 4 conf   EXTEND app/workflows/iteration.py (calculate_merge_confidence + security dim)
Layer 4 report EXTEND app/workflows/stages.py (GenerateDummyReportStage) + reuse github_service.py
Config         NEW    app/security/config/repo_config.py ; EXTEND app/config/settings.py
```

The design's "pure core, impure shell" separation is preserved: the deterministic security core (normalize, deduplicate, enrich, risk-score, order, verify accept/reject, quality-gate, merge-confidence, config resolution, report assembly) is validated with **Hypothesis** property tests (one per design property, 100+ examples, tagged `# Feature: security-pipeline, Property {n}: {text}`) using the existing pytest setup; AI stages and I/O adapters (scanner subprocesses, SonarQube, GitHub) are covered with example/integration tests using in-memory fakes and mocks.

## Tasks

- [x] 1. Shared security models, config, and Hypothesis test setup
  - [x] 1.1 Add security data models and adapter protocols
    - Create `app/security/models.py` with the immutable dataclasses/enums from the design Data Models that are net-new: `ScanScope`, `Finding`, `Severity`, `Location`, `FindingStatus`, `Normalized_Finding`, `Exposure`, `AuthContext`, `RiskScoreInputs`, `Priority`, `AITriage`, `CandidatePatch`, `VerificationOutcome`, `QualityGateThresholds`, `GateStatus`, `UnsatisfiedThreshold`, `Quality_Gate`, `SonarMetrics`, `MergeConfidenceInputs`, `ScannerCoverage`, `ConfigSubstitution`, `DetectionResult`, `IntelligenceResult`, and the security-report fields
    - Reuse existing schemas where they overlap (`app/schemas/repository.py` for repo context, `app/schemas/quality.py` for validation results) instead of redefining them
    - Create `app/security/protocols.py` defining the injectable adapter Protocols: `ScannerAdapter`, `AITriageAdapter`, `AIRepairAdapter`, `SonarClient`, `GitHubReporter`
    - _Requirements: 3.5, 5.1_

  - [x] 1.2 Add Hypothesis to the existing venv and create shared strategies
    - Install `hypothesis` into the existing `ai-delivery/venv` (add to the project's existing requirements file); do not create a new project or venv
    - Create `tests/security/strategies.py` with reusable generators for `Finding`, `Normalized_Finding`, `Location`, `Severity`, `RiskScoreInputs`, `QualityGateThresholds`, `SonarMetrics`, `MergeConfidenceInputs`, well-formed/malformed `Repo_Config`, and finding sets with controlled duplicate groups and baseline/post-patch relationships
    - Exercise edge cases: empty inputs, missing fields, non-ASCII strings, boundary numerics, mixed parseable/unparseable file sets
    - _Requirements: 5.1, 6.1, 8.1_

  - [x] 1.3 Implement per-repo Repo_Config resolution
    - Create `app/security/config/repo_config.py` with `ConfigResolver.resolve(raw) -> (ResolvedConfig, list[ConfigSubstitution])`; layer it on top of the existing global `app/config/settings.py` so env/global settings remain the base and `Repo_Config` overrides per repository
    - Load `Repo_Config` when present; apply documented defaults when absent; on a malformed value reject it, apply the default, and emit one `ConfigSubstitution` naming the field
    - Produce a single immutable `ResolvedConfig` (thresholds, scanner rules, pipeline settings) consumed by all layers
    - _Requirements: 1.5, 12.2, 12.3, 15.1, 15.2, 15.3_

  - [x]* 1.4 Write property test for configuration resolution
    - **Property 17: Configuration resolution** — each resolved threshold/scanner-rule/pipeline setting equals the provided value where well-formed and the documented default everywhere else
    - **Validates: Requirements 12.2, 12.3, 15.1, 15.3**

  - [x]* 1.5 Write property test for configuration substitution
    - **Property 18: Configuration substitution** — each malformed field resolves to its default and produces exactly one `ConfigSubstitution`; well-formed fields produce none
    - **Validates: Requirements 15.2**

- [x] 2. Extend Layer 1 Repository Intelligence for reachability
  - [x] 2.1 Extend the indexer/DB to build call and dependency graphs
    - Current state to account for: `indexer.py` only extracts **top-level** `tree.body` classes/functions (no methods/nested defs), the `dependencies` table stores coarse **module-level imports duplicated per symbol** with an empty `import_path`, there is **no call graph**, and `SyntaxError` files are silently skipped (only logged)
    - Deepen the AST walk in `app/services/repository/indexer.py` to capture nested/method symbols and function-call edges (caller→callee); add a new `calls` table (and refine `dependencies` to record resolved `import_path`) in `app/services/repository/db.py` so both a **call graph** and **dependency graph** are persisted and traversable — this is net-new graph construction, not a cosmetic extension of the existing tables
    - Record files that fail AST parsing as unparseable (add an `unparseable` flag/column on `files` or a dedicated table) and continue indexing the rest, replacing the current silent `SyntaxError` skip
    - _Requirements: 2.2, 2.3, 2.6_

  - [x] 2.2 Extend the retriever and RepositoryContext for related symbols and reachability inputs
    - Current state to account for: `retriever.py` does name-based dependency matching only (joining `dependencies.target_symbol_name` to `symbols.name`) and `RepositoryContext` (`app/schemas/repository.py`) has only `target_symbols`/`dependencies`/`related_tests` — no graph or reachability fields
    - Extend `ContextRetrievalEngine` to traverse the new call/dependency graphs (callers, callees, imported modules) for symbols related to the `Changed_Feature`, and add reachability-input fields to `RepositoryContext` (or a new security context model) that Layer 3 enrichment consumes
    - Map the existing `context.changed_files` / `context.structured_diff` (from `AnalyzeFilesStage` / `GitDiffCollectorStage`) into the `Changed_Feature` shape (files, functions, classes, related symbols) used by the security layers
    - _Requirements: 2.1, 2.4, 2.5_

  - [x]* 2.3 Write property test for change coverage
    - **Property 2: Change coverage** — every changed path appears in `Changed_Feature.files` and every changed function/class appears in `functions`/`classes`
    - **Validates: Requirements 2.1**

  - [x]* 2.4 Write property test for unparseable-file handling
    - **Property 3: Unparseable-file handling** — the recorded unparseable set equals exactly the unparseable subset and every parseable file is still analyzed
    - **Validates: Requirements 2.6**

  - [x]* 2.5 Write example tests for call/dependency graph construction
    - Verify the extended indexer produces expected call-graph/dependency-graph nodes and edges and related-symbol resolution over representative Python modules in a fixture repo
    - _Requirements: 2.2, 2.4, 2.5_

- [x] 3. Checkpoint — Layer 1 extension verified
  - Run the existing pytest suite plus the new Layer 1 tests via the existing venv; ensure all tests pass, ask the user if questions arise.

- [x] 4. Build Layer 2 Detection scanners and parallel runner stage
  - [x] 4.1 Implement the parallel scanner runner as a new Stage
    - Create `app/security/detection/runner.py` with `DetectionStage(Stage)` (subclassing the existing base in `app/workflows/stages.py`) that derives one `ScanScope` from the extended `RepoContext` and shares it with every adapter, then runs the six `ScannerAdapter`s concurrently (`concurrent.futures`) and aggregates every `Finding` as a multiset union
    - Isolate per-scanner failures: on failure/timeout record a `ScannerCoverage` entry with `status = "incomplete"` and a reason, retain other scanners' findings, and continue — mirroring the fail-open behavior the orchestrator already relies on
    - Write the `DetectionResult` into `WorkflowContext` (extend `app/workflows/context.py` with a `detection_result` field)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x]* 4.2 Write property test for scanner scoping
    - **Property 4: Scanner scoping** — the `ScanScope` passed to every adapter equals the scope derived from the `RepoContext`
    - **Validates: Requirements 3.2**

  - [x]* 4.3 Write property test for finding aggregation and provenance
    - **Property 5: Finding aggregation and provenance** — aggregated output equals the multiset union of per-scanner lists and each `Finding` retains scanner, location, and severity
    - **Validates: Requirements 3.3, 3.5**

  - [x]* 4.4 Write property test for scanner-failure containment
    - **Property 6: Scanner-failure containment** — findings from non-failing scanners are retained and coverage is `incomplete` iff the scanner failed
    - **Validates: Requirements 3.4**

  - [x] 4.5 Implement the six scanner adapters
    - Create `app/security/detection/adapters/` with `bandit_adapter.py`, `semgrep_adapter.py`, `codeql_adapter.py`, `gitleaks_adapter.py`, `checkov_adapter.py`, `trivy_adapter.py`, each implementing `ScannerAdapter`, invoking its tool as a subprocess, and parsing native SARIF/JSON output into the shared `Finding` type with correct provenance (scanner, location, severity)
    - Follow the existing subprocess-service conventions used by `app/services/validators.py` / `app/services/test_executor.py` for running external commands
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x]* 4.6 Write integration tests for scanner adapters
    - Use 1–3 known-vulnerable fixtures per scanner to confirm each adapter parses native output and surfaces representative findings, using the existing pytest setup
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 5. Build Layer 3 deterministic intelligence core (pure functions)
  - [x] 5.1 Implement normalization
    - Create `app/security/intelligence/normalize.py` with `normalize(finding) -> Normalized_Finding` conforming to `Common_Schema`, preserving scanner/location/severity and assigning documented defaults for missing required fields while recording them in `defaults_applied`
    - _Requirements: 5.1, 5.2, 5.3_

  - [x]* 5.2 Write property test for normalization conformance and preservation
    - **Property 7: Normalization conformance and preservation** — output conforms to `Common_Schema`, preserves scanner/location/severity, and `defaults_applied` equals exactly the missing-field set
    - **Validates: Requirements 5.1, 5.2, 5.3**

  - [x] 5.3 Implement deduplication
    - Add `deduplicate(findings) -> findings` in `app/security/intelligence/dedup.py` collapsing groups sharing `(rule_identity, canonical_location)` into one finding whose `scanners` set is the union; preserve distinct vulnerabilities
    - _Requirements: 6.1, 6.2, 6.3_

  - [x]* 5.4 Write property test for deduplication
    - **Property 8: Deduplication** — one output per distinct `(rule_identity, canonical_location)` group with a merged scanner set; distinct vulnerabilities preserved
    - **Validates: Requirements 6.1, 6.2, 6.3**

  - [x] 5.5 Implement context enrichment
    - Add `enrich(...)` in `app/security/intelligence/enrich.py` attaching `reachability` (from the Layer 1 call graph via the extended retriever), `business_criticality` (from repo context), `exposure` ∈ {public, internal}, and `auth_context` to each `Normalized_Finding`
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x]* 5.6 Write property test for enrichment completeness
    - **Property 9: Enrichment completeness** — every enriched finding has populated `reachability`, `business_criticality`, `auth_context`, and `exposure` in `{public, internal}`
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4**

  - [x] 5.7 Implement risk scoring and ordering
    - Add `compute_risk_score` and ordering in `app/security/intelligence/scoring.py` as the product `Severity × Reachability × Business_Criticality × Exploitability × Repository_Context`; order findings by `Risk_Score` descending
    - _Requirements: 8.1, 8.2, 8.3_

  - [x]* 5.8 Write property test for risk-score determinism
    - **Property 10: Risk-score determinism** — returns the specified product and identical inputs yield identical scores (pure)
    - **Validates: Requirements 8.1, 8.2**

  - [x]* 5.9 Write property test for risk ordering
    - **Property 11: Risk ordering** — output is a permutation of the input, monotonically non-increasing in `Risk_Score`
    - **Validates: Requirements 8.3**

- [x] 6. Checkpoint — Detection + intelligence core verified
  - Run the property and integration tests for Layers 2 and 3 core via the existing venv; ensure all tests pass, ask the user if questions arise.

- [x] 7. Build Layer 3 AI triage, repair, and deterministic verification
  - [x] 7.1 Implement AI triage attachment reusing LLMService
    - Create `app/security/intelligence/triage.py` with an `AITriageAdapter` implementation that calls the existing `app/services/llm_service.py` (`LLMService.generate_structured_json`, prompt-hash caching) to produce explanation/priority/suggested fix; add a triage prompt under `app/prompts/`
    - Label likely false positives while retaining the finding; attach triage without altering `Risk_Score`
    - _Requirements: 9.1, 9.2, 9.3_

  - [x]* 7.2 Write property test for triage retention and non-mutation
    - **Property 12: Triage retention and non-mutation** — all findings retained, false-positive label matches the triage flag, and `Risk_Score` is unchanged (AI adapter mocked)
    - **Validates: Requirements 9.2, 9.3**

  - [x]* 7.3 Write example test for AI triage content shape
    - With a mocked `AITriageAdapter`, assert the attached triage object shape (explanation, priority, suggested fix); content values are not asserted (non-deterministic)
    - _Requirements: 9.1_

  - [x] 7.4 Implement AI repair selection reusing the RepairAgent pattern
    - Create `app/security/intelligence/repair.py` with an `AIRepairAdapter` implementation following the existing `app/agents/repair/agent.py` pattern (structured failure summary + previous-attempts history + full-file rewrite); reuse `LLMService` and add a security-repair prompt under `app/prompts/`
    - For each scanner-confirmed finding not labeled a likely false positive, produce a `CandidatePatch` associated by `target_finding_id`; treat patches as proposals only
    - When no patch is produced, mark the finding `unresolved` with a recorded `unresolved_reason`
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [x]* 7.5 Write property test for repair selection and association
    - **Property 13: Repair selection and association** — repair attempted exactly for scanner-confirmed, non-false-positive findings; each patch's `target_finding_id` references a present finding
    - **Validates: Requirements 10.1, 10.2**

  - [x]* 7.6 Write property test for repair-unresolved handling
    - **Property 14: Repair-unresolved handling** — a finding with no patch is marked `unresolved` with a recorded reason
    - **Validates: Requirements 10.4**

  - [x] 7.7 Implement deterministic verification reusing the scanner re-run
    - Create `app/security/intelligence/verify.py` with `Verifier.verify` that re-runs the Layer 2 scanners against the patched scope (reusing the `DetectionStage` adapters, mirroring the validate-after-repair approach in `app/workflows/quality_stages.py`) and accepts (marking `fixed`) iff the targeted finding is resolved AND no finding absent from the baseline is introduced; otherwise reject and mark `unresolved`
    - Assemble `IntelligenceResult` partitioning findings into `fixed` and `remaining`; wire the whole Layer 3 flow as an `IntelligenceStage(Stage)` and store the result on `WorkflowContext`
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [x]* 7.8 Write property test for verification decision
    - **Property 15: Verification decision** — accept/`fixed` iff target resolved AND no new finding introduced; otherwise reject/`unresolved`
    - **Validates: Requirements 11.2, 11.3, 11.4**

  - [x]* 7.9 Write integration test for verification scanner re-run
    - Assert the verifier invokes the scanners against the patched scope (adapters mocked or run against a fixture)
    - _Requirements: 11.1_

- [x] 8. Checkpoint — full Layer 3 verified
  - Run the Layer 3 property, example, and integration tests via the existing venv; ensure all tests pass, ask the user if questions arise.

- [x] 9. Build Layer 4 Governance (quality gate, merge confidence, report)
  - [x] 9.1 Implement the SonarQube Quality Gate
    - Create `app/security/governance/quality_gate.py` with a pure `evaluate_quality_gate(metrics, findings, thresholds) -> Quality_Gate`: status `passed` iff every threshold satisfied; when `failed`, record exactly the violated thresholds in `unsatisfied`
    - Create a `SonarClient` adapter that fetches SonarQube metrics into `SonarMetrics` (maintainability, code smells, technical debt, security hotspots, coverage)
    - _Requirements: 12.1, 12.4, 12.5_

  - [x]* 9.2 Write property test for quality-gate decision
    - **Property 16: Quality-gate decision** — `passed` iff all thresholds satisfied; `unsatisfied` equals exactly the violated set (empty iff passed)
    - **Validates: Requirements 12.4, 12.5**

  - [x] 9.3 Extend merge-confidence with a security dimension
    - Extend `IterationController.calculate_merge_confidence()` in `app/workflows/iteration.py` (currently 30 build + 50 test-pass + 20 coverage) into a pure `compute_merge_confidence(inputs) -> Merge_Confidence` that also incorporates security confidence, remaining findings, and Quality_Gate status; mark the result advisory
    - _Requirements: 13.1, 13.2, 13.3_

  - [x]* 9.4 Write property test for merge-confidence determinism
    - **Property 19: Merge-confidence determinism** — returns a defined advisory score; identical inputs yield identical values (pure)
    - **Validates: Requirements 13.1, 13.2**

  - [x] 9.5 Extend the PR report with security sections
    - Extend `GenerateDummyReportStage` in `app/workflows/stages.py` (which writes `AI_REPORT.md`) to assemble the security `Pull_Request_Report` fields: testing/security summaries, fixed/remaining findings, merge confidence, quality-gate status (+ unsatisfied thresholds when failed), incomplete scanners, and config substitutions; keep the merge decision with a human
    - Reuse the existing `CommitStage`/`PushBranchStage`/`CreatePullRequestStage` and `app/services/github_service.py` (`open_pull_request`) to attach the report and commit verified patches to the PR branch — never invoking merge
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

  - [x]* 9.6 Write property test for report completeness
    - **Property 21: Report completeness** — report contains summaries, merge confidence, and fixed/remaining lists matching source partitions; `quality_gate` matches with unsatisfied thresholds present exactly when failed; `incomplete_scanners` equals the incomplete set
    - **Validates: Requirements 14.2, 14.3, 14.4**

  - [x]* 9.7 Write integration tests for SonarQube and GitHub reporting
    - Mock the SonarQube API to assert metric retrieval/mapping; mock `GitHubService.open_pull_request` to assert the report is attached for `Commit_SHA`, patches are committed to the PR branch, and no merge call is ever made
    - _Requirements: 12.1, 14.1_

- [x] 10. Wire security layers into the existing orchestrator
  - [x] 10.1 Register the new stages and sequence the four layers
    - Register the new `DetectionStage` and `IntelligenceStage` (and the Layer 4 report extension) with the existing `WorkflowOrchestrator.run_pipeline()` in `app/workflows/orchestrator.py`, inserting them after the existing Layer-1 intelligence stages so execution runs Layer 1 → 2 → 3 → 4 in strict order (reusing the orchestrator's stop-on-first-failure behavior)
    - Resolve `Repo_Config` before the Detection stage; reuse the existing `github_webhook` trigger in `app/github/routes.py` (which already ignores `ai-sde/` branches) as the pipeline entry point, deriving `Commit_SHA`/`Git_Diff` from the push event and halting with a diagnostic error naming any missing input
    - _Requirements: 1.1, 1.2, 1.3, 1.5_

  - [x] 10.2 Implement layer-failure containment in the orchestrator
    - Ensure an unrecoverable error in any security layer stops subsequent layers and still produces a `Pull_Request_Report` with `failed_layer` set to the failing layer (build on the orchestrator's existing error tracking)
    - _Requirements: 1.4_

  - [x]* 10.3 Write property test for layer-failure containment
    - **Property 1: Layer-failure containment** — subsequent layers are never invoked and the report's `failed_layer` names exactly the failing layer
    - **Validates: Requirements 1.4**

  - [x]* 10.4 Write property test for no automatic merge
    - **Property 20: No automatic merge** — for any run and any `Merge_Confidence` (incl. maximum), no merge action is invoked; patches are committed to the PR branch only
    - **Validates: Requirements 10.3, 13.3, 14.5**

  - [x]* 10.5 Write example tests for orchestration ordering and missing inputs
    - With mocked stages, assert the strict Layer 1 → 2 → 3 → 4 order and that config resolution precedes detection; cover each present/absent combination of `Commit_SHA`/`Git_Diff`
    - _Requirements: 1.2, 1.3, 1.5_

- [x] 11. Final checkpoint — end-to-end security pipeline
  - [x]* 11.1 Write an end-to-end integration test through the existing orchestrator
    - Drive a representative push event through `github_webhook` → orchestrator → Layer 1 (extended) → 2 → 3 → 4, with fakes for the scanner/AI/SonarQube/GitHub adapters, asserting a complete `Pull_Request_Report` is produced and attached to the PR without any merge call
    - _Requirements: 1.1, 1.2, 14.1_
  - [x] 11.2 Run the full suite and confirm alignment
    - Run the complete pytest suite (existing DeliveryOS tests + new security tests) via `ai-delivery/venv`; ensure all tests pass, ask the user if questions arise.

## Notes

- **Regrounded on the existing system**: every task extends a named existing module (`app/services/repository/*`, `app/workflows/*`, `app/services/*`, `app/agents/repair/*`, `app/services/github_service.py`) or adds a clearly-scoped net-new module under `app/security/`. There is no project-setup/dependency-scaffolding task because the DeliveryOS project, its `venv`, and `pytest` already exist; the only new test dependency is Hypothesis.
- **Reuse highlights**: webhook trigger (`app/github/routes.py`), sequential stage orchestration (`app/workflows/orchestrator.py` + `stages.py`), Layer-1 intelligence stack (`app/services/repository/*`), LLM service + caching (`app/services/llm_service.py`), repair-agent pattern (`app/agents/repair/agent.py`), merge-confidence (`app/workflows/iteration.py`), and PR creation (`app/services/github_service.py`).
- **Net-new highlights**: six scanner adapters + parallel runner stage, the deterministic security intelligence core, SonarQube quality gate, per-repo `Repo_Config`, and the security-augmented report/merge-confidence.
- Tasks marked with `*` are optional test tasks and can be skipped for a faster MVP. All 21 correctness properties are implemented as single Hypothesis property tests (100+ examples each) for the deterministic core, tagged `# Feature: security-pipeline, Property {number}: {property_text}`; AI stages and I/O boundaries use example/integration tests with in-memory fakes and mocks on the existing pytest setup.
- Each task references specific requirement clauses for traceability; property test tasks additionally cite their design property number.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["1.4", "1.5", "2.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4", "2.5"] },
    { "id": 4, "tasks": ["3"] },
    { "id": 5, "tasks": ["4.1", "4.5"] },
    { "id": 6, "tasks": ["4.2", "4.3", "4.4", "4.6"] },
    { "id": 7, "tasks": ["5.1", "5.3", "5.5", "5.7"] },
    { "id": 8, "tasks": ["5.2", "5.4", "5.6", "5.8", "5.9"] },
    { "id": 9, "tasks": ["6"] },
    { "id": 10, "tasks": ["7.1", "7.4", "7.7"] },
    { "id": 11, "tasks": ["7.2", "7.3", "7.5", "7.6", "7.8", "7.9"] },
    { "id": 12, "tasks": ["8"] },
    { "id": 13, "tasks": ["9.1", "9.3", "9.5"] },
    { "id": 14, "tasks": ["9.2", "9.4", "9.6", "9.7"] },
    { "id": 15, "tasks": ["10.1", "10.2"] },
    { "id": 16, "tasks": ["10.3", "10.4", "10.5"] },
    { "id": 17, "tasks": ["11.1", "11.2"] }
  ]
}
```
