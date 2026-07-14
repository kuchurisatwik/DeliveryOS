# DeliveryOS Security Pipeline — Layer Functionality Guide

> A layer-by-layer reference for the security pipeline: what each layer does, what it consumes, and what it produces.

---

## Overview

The Security Pipeline runs on each Git push (via the existing `github_webhook`) and produces a security-reviewed Pull Request annotated with an advisory merge-confidence score. It follows one strict philosophy:

- **Deterministic tools discover** vulnerabilities.
- **AI reasons** about findings and proposes fixes.
- **Deterministic tools verify** those fixes.
- **Governance decides** whether the code is ready to merge — and a human always makes the final call.

AI augments the deterministic scanners; it never replaces them, and no code is ever auto-merged.

The pipeline is built **inside the existing DeliveryOS codebase** (`app/`), reusing the webhook trigger, the sequential `WorkflowOrchestrator`, the `WorkflowContext` shared state, the SQLite/AST repository index, the `LLMService`, and the git/GitHub services. New security code lives under `app/security/`.

### End-to-end flow

```
Git push
   │  Commit_SHA, Git_Diff
   ▼
[ Config Resolution ]  ── ResolvedConfig, substitutions
   ▼
[ Layer 1: Repository Intelligence ]  ── RepoContext (Changed_Feature + graphs)
   ▼
[ Layer 2: Detection ]                ── DetectionResult (Findings + coverage)
   ▼
[ Layer 3: Intelligence ]             ── IntelligenceResult (fixed / remaining)
   ▼
[ Layer 4: Governance ]               ── Pull_Request_Report + advisory Merge_Confidence
   ▼
GitHub Pull Request (human decides merge)
```

Each layer is a `Stage` plugged into `WorkflowOrchestrator` and communicates through the shared `WorkflowContext`. The design deliberately separates a **deterministic pure core** (normalization, deduplication, scoring, verification decisions, quality gate, merge confidence) from the **impure shell** (scanner subprocesses, SonarQube, GitHub, AI calls), so the core is validated with property-based tests.

---

## Configuration Resolution (runs before Layer 2)

**Context.** Resolves per-repository configuration once, up front, layered on top of the global `app/config/settings.py`. Malformed values are rejected and replaced with documented defaults, and each substitution is recorded for the report.

| | |
|---|---|
| **Module** | `app/security/config/repo_config.py` (`ConfigResolver.resolve`), `app/security/pipeline.py` (`SecurityConfigResolutionStage`) |
| **Input** | Raw `Repo_Config` file contents (`str \| None`) — read from `.deliveryos/security.json` in the workspace when present |
| **Output** | An immutable `ResolvedConfig` (quality-gate thresholds, scanner rules, pipeline settings) + a list of `ConfigSubstitution` records |
| **Key rules** | Absent config → all defaults, no substitutions. Malformed field → default applied + exactly one substitution naming the field. Defaults: 0 critical findings, coverage ≥ 90%, 0 leaked secrets, 0 blocking IaC issues. |

---

## Layer 1 — Repository Intelligence

**Context.** Understands *what changed* in the current commit and builds the surrounding code context, so later layers analyze only the affected feature instead of the whole repository. This layer **extends** the existing DeliveryOS repository-intelligence stack (git diff collector, SQLite/AST indexer, feature planner, context retriever) with a traversable call graph, a dependency graph, and reachability signals.

| | |
|---|---|
| **Modules** | `app/services/repository/indexer.py`, `db.py`, `retriever.py`; existing intelligence stages in `app/workflows/intelligence_stages.py` |
| **Input** | `Git_Diff` (changed files/hunks) and `Commit_SHA` from the push event; the cloned workspace |
| **Output** | `RepoContext` containing the `Changed_Feature` (changed files, functions, classes), a symbol index, a **call graph**, a **dependency graph**, related symbols (callers / callees / imports), per-symbol **reachability** signals, and the list of unparseable files |

**What it does**
- Extracts the changed files/functions/classes as the `Changed_Feature`.
- Builds an AST per changed Python file; captures nested and method-level symbols (not just top-level).
- Persists a call graph (`calls` table) and a dependency graph (resolved import paths) in the SQLite index.
- Resolves symbols related to the change via graph traversal, plus reachability inputs (has callers, reachable from an entrypoint, caller count) that Layer 3 enrichment consumes.
- Records any file that fails to parse as `unparseable` and continues — a single bad file never aborts the layer.

---

## Layer 2 — Detection

**Context.** Runs specialized deterministic security scanners **in parallel**, scoped to the changed feature, and collects every finding into a common format. This is the largest net-new build. A single scanner failing does not abort the pipeline — its coverage is simply marked incomplete (fail-open).

| | |
|---|---|
| **Modules** | `app/security/detection/runner.py` (`DetectionStage`), `app/security/detection/adapters/` (six adapters) |
| **Input** | `RepoContext` (Layer 1) + `ResolvedConfig`; a single derived `ScanScope` (changed-feature paths + related symbols) shared by every scanner |
| **Output** | `DetectionResult` — the aggregated list of `Finding`s (each retaining originating scanner, location, and severity) + a per-scanner `ScannerCoverage` list (`complete` / `incomplete`) |

**Scanner coverage**

| Scanner | Focus |
|---|---|
| **Bandit** | Python security: `subprocess`/`os.system`, `eval`/`exec`, unsafe deserialization, weak crypto, hardcoded passwords, unsafe YAML |
| **Semgrep** | Pattern-based: SQLi, command injection, XSS, SSRF, path traversal, authn/authz flaws, company rules |
| **CodeQL** | Semantic / data-flow: multi-function SQLi, taint flow, authorization bypass, resource leaks |
| **Gitleaks** | Secrets: API keys, cloud credentials, SSH keys, tokens, DB passwords, `.env` leaks |
| **Checkov** | Infrastructure-as-Code: public cloud resources, weak IAM, open security groups, K8s/Terraform/CloudFormation risks |
| **Trivy** | Dependencies & containers: dependency CVEs, container/filesystem vulns, OS package vulns |

Each adapter runs its tool as a subprocess and parses the native SARIF/JSON output into the shared `Finding` type. Missing tools or timeouts surface as a handled `ScannerError` → incomplete coverage.

---

## Layer 3 — Intelligence

**Context.** Turns raw scanner findings into scored, triaged, repaired, and re-verified results. The deterministic stages (normalize → dedup → enrich → score) are pure functions; the AI stages (triage, repair) are bracketed by deterministic re-verification so AI never has the final say.

| | |
|---|---|
| **Modules** | `app/security/intelligence/` — `normalize.py`, `dedup.py`, `enrich.py`, `scoring.py`, `triage.py`, `repair.py`, `verify.py`, `stage.py` (`IntelligenceStage`) |
| **Input** | `DetectionResult.findings` (Layer 2) + `RepoContext` (Layer 1) + injected AI adapters (triage, repair) and a patched-scan callable |
| **Output** | `IntelligenceResult` — findings partitioned into **`fixed`** and **`remaining`**, each carrying its triage, optional candidate patch, and status |

**Stage-by-stage**

| Stage | Input → Output | Notes |
|---|---|---|
| **Normalize** | `Finding` → `Normalized_Finding` | Conforms to the Common Schema; preserves scanner/location/severity; records `defaults_applied` for any missing field |
| **Deduplicate** | findings → findings | Merges findings sharing `(rule_identity, canonical_location)`; unions the originating scanner set; keeps distinct vulns separate |
| **Enrich** | findings → enriched findings | Attaches reachability (call graph), business criticality, exposure (public/internal), and auth context |
| **Risk score & order** | enriched → scored, ordered | `Risk = Severity × Reachability × Business_Criticality × Exploitability × Repository_Context`; ordered descending; deterministic |
| **AI triage** | finding → finding + `AITriage` | Explanation, priority, suggested fix, likely-false-positive flag; retained even if flagged FP; never changes the risk score |
| **AI repair** | eligible finding → `CandidatePatch` \| none | Only for scanner-confirmed, non-false-positive findings; patch is a proposal only; no patch → `unresolved` with a reason |
| **Verification** | patch + baseline + patched scan → outcome | Re-runs the scanners; accepts and marks **fixed** iff the target is resolved **and** no new finding is introduced; otherwise rejects → `unresolved` |

---

## Layer 4 — Governance

**Context.** Enforces the organizational quality gate, computes an advisory merge-confidence score, and assembles the Pull Request report. Reuses the existing report/commit/PR stages and merge-confidence controller. The final merge decision always stays with a human.

| | |
|---|---|
| **Modules** | `app/security/governance/quality_gate.py`, `sonar_client.py`, `merge_confidence.py`, `report.py`; `app/security/pipeline.py` (`GovernanceStage`); extended `app/workflows/iteration.py` and `app/workflows/stages.py` |
| **Input** | `IntelligenceResult` (Layer 3) + `SonarMetrics` (fetched via `SonarClient`) + `ResolvedConfig` thresholds + config substitutions + scanner coverage |
| **Output** | A complete `Pull_Request_Report` and an advisory `Merge_Confidence`, attached to the GitHub PR |

**Sub-functions**

| Function | Input → Output | Notes |
|---|---|---|
| **Quality Gate** | `(SonarMetrics, findings, thresholds)` → `Quality_Gate` | `passed` iff every threshold satisfied; otherwise `failed` listing exactly the unsatisfied thresholds. Pure. |
| **Merge Confidence** | `MergeConfidenceInputs` → `Merge_Confidence` | Weighted: testing 40, security 30, coverage 15, gate 15, minus a per-remaining-finding penalty. Deterministic and advisory — never triggers a merge. |
| **PR Report** | governance outputs → `Pull_Request_Report` | Testing + security summaries, fixed/remaining findings, merge confidence, quality-gate status (+ unsatisfied thresholds when failed), incomplete scanners, config substitutions. Rendered into `AI_REPORT.md` and posted to the PR. |

**Merge Confidence weighting**

| Dimension | Weight |
|---|---|
| Testing confidence (build + test-pass) | 40 |
| Security confidence (findings resolved / verified) | 30 |
| Coverage | 15 |
| Quality Gate passed | 15 |
| Remaining findings | −2 each (capped at −20) |

---

## Orchestration & error containment

| | |
|---|---|
| **Modules** | `app/workflows/orchestrator.py`, `app/security/pipeline.py` (`build_security_stages`, `run_security_pipeline_with_containment`, `ensure_security_inputs`), `app/github/routes.py` |
| **Input** | GitHub push event → `Commit_SHA`, `Git_Diff`, optional `Repo_Config` |
| **Output** | One `Pull_Request_Report` produced by chaining Config → Layer 1 → 2 → 3 → 4 in strict order |

**Guarantees**
- **Missing input** (`Commit_SHA` or `Git_Diff`) → halt with a diagnostic naming the missing input.
- **Config resolves before Detection.**
- **Layer-failure containment** — an unrecoverable error in any layer stops subsequent layers and still produces a report whose `failed_layer` names exactly the failing layer; the quality gate never reports "passed" for an incomplete run.
- **No automatic merge** — verified patches are committed to the PR branch only; merge is always a human action.

---

## Data model quick reference

| Model | Meaning |
|---|---|
| `ResolvedConfig` / `ConfigSubstitution` | Per-repo config after resolution + record of any defaulted fields |
| `RepoContext` / `ChangedFeature` | Layer 1 output: what changed + surrounding graph context |
| `Finding` | A single raw vulnerability from a scanner |
| `Normalized_Finding` | A finding in the common schema, enriched and scored through Layer 3 |
| `DetectionResult` | Aggregated findings + per-scanner coverage |
| `AITriage` / `CandidatePatch` / `VerificationOutcome` | AI assessment, proposed fix, and the deterministic accept/reject result |
| `IntelligenceResult` | Findings partitioned into fixed / remaining |
| `SonarMetrics` / `Quality_Gate` | Governance inputs and gate decision |
| `Merge_Confidence` | Advisory readiness score (0–100) |
| `Pull_Request_Report` | The final report attached to the PR |

---

## Testing model

- **Pure core** (normalization, dedup, enrichment, scoring, verification decision, quality gate, merge confidence, config resolution, report assembly) → validated with **Hypothesis property-based tests** (21 correctness properties, 100+ examples each).
- **AI stages and I/O boundaries** (scanners, SonarQube, GitHub, LLM) → validated with example/integration tests using in-memory fakes and mocks.
- Full suite: **97 tests passing**, no regressions to the pre-existing DeliveryOS tests.
