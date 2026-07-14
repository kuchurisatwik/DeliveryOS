# Requirements Document

## Introduction

The DeliveryOS Security Pipeline is an orchestration system that runs on each Git push and produces a security-reviewed Pull Request annotated with a merge confidence score. The pipeline follows a strict philosophy: deterministic tools discover vulnerabilities, AI reasons about findings and proposes fixes, deterministic tools verify the fixes, and a governance layer decides whether the code is ready to merge. AI augments the deterministic scanners; it never replaces them.

The system is organized into four cooperating layers:

- **Layer 1 – Repository Intelligence**: narrows analysis to only the code affected by the current commit.
- **Layer 2 – Detection Layer**: runs specialized deterministic scanners in parallel to discover vulnerabilities.
- **Layer 3 – Intelligence Layer**: normalizes, deduplicates, enriches, scores, triages, repairs, and re-verifies findings.
- **Layer 4 – Governance Layer**: enforces organizational quality gates, computes merge confidence, and generates the Pull Request report.

### Scope of this iteration (confirmed with stakeholder)

- All four layers are in scope end-to-end.
- Primary language target is **Python**, with **Infrastructure-as-Code (IaC)**, dependencies, containers, and secrets covered by the relevant scanners.
- Git host is **GitHub**; the pipeline executes in **GitHub Actions**.
- AI repair is **propose-only**: verified patches are committed to the Pull Request branch and a human always makes the final merge decision. Merge confidence is advisory.
- The example Quality Gate policy (Critical findings = 0, Coverage ≥ 90%, no leaked secrets, no blocking IaC issues) ships as **configurable per-repository defaults**.

## Glossary

- **Pipeline**: The DeliveryOS Security Pipeline orchestration system that coordinates all four layers.
- **Repository_Intelligence**: The Layer 1 subsystem that understands what changed in the current commit and builds repository context.
- **Detection_Layer**: The Layer 2 subsystem that runs deterministic security scanners in parallel.
- **Intelligence_Layer**: The Layer 3 subsystem that normalizes, deduplicates, enriches, scores, triages, repairs, and re-verifies findings.
- **Governance_Layer**: The Layer 4 subsystem that enforces quality gates, computes merge confidence, and generates the Pull Request report.
- **Scanner**: Any one of the deterministic security tools: Bandit, Semgrep, CodeQL, Gitleaks, Checkov, Trivy.
- **Finding**: A single vulnerability or issue reported by a Scanner.
- **Normalized_Finding**: A Finding converted into the common schema used across the Intelligence_Layer.
- **Common_Schema**: The unified data structure used to represent findings regardless of originating Scanner.
- **Risk_Score**: A computed value equal to Severity × Reachability × Business_Criticality × Exploitability × Repository_Context.
- **AI_Triage**: The AI process that explains findings, prioritizes them, suggests fixes, and flags likely false positives.
- **AI_Repair**: The AI process that generates candidate secure patches for verified findings.
- **Verification**: The deterministic re-run of Scanners that confirms whether a candidate patch resolves the targeted Finding.
- **Quality_Gate**: The configurable policy that determines whether code satisfies organizational quality thresholds.
- **Merge_Confidence**: A computed score summarizing readiness to merge, derived from testing confidence, security confidence, coverage, remaining findings, and Quality_Gate status.
- **Pull_Request_Report**: The generated report attached to the Pull Request summarizing testing, security, fixed findings, remaining findings, and Merge_Confidence.
- **Repo_Config**: The per-repository configuration file that overrides default Quality_Gate thresholds and pipeline settings.
- **Commit_SHA**: The unique identifier of the Git commit that triggered the Pipeline.
- **Git_Diff**: The set of changes introduced by the triggering commit relative to the base.
- **Changed_Feature**: The set of files, functions, and classes affected by the current commit, together with related symbols.

## Requirements

### Requirement 1: Pipeline Trigger and Orchestration

**User Story:** As a developer, I want the Pipeline to run automatically when I push code, so that security review happens on every change without manual effort.

#### Acceptance Criteria

1. WHEN a Git push to a GitHub repository occurs, THE Pipeline SHALL start execution using the associated Commit_SHA and Git_Diff.
2. THE Pipeline SHALL execute the four layers in order: Repository_Intelligence, then Detection_Layer, then Intelligence_Layer, then Governance_Layer.
3. IF a required input (Commit_SHA or Git_Diff) is unavailable, THEN THE Pipeline SHALL halt execution and record a diagnostic error identifying the missing input.
4. IF any layer terminates with an unrecoverable error, THEN THE Pipeline SHALL stop subsequent layers and produce a Pull_Request_Report that states which layer failed.
5. WHERE a Repo_Config file is present in the repository, THE Pipeline SHALL load configuration values from the Repo_Config before executing the Detection_Layer.

### Requirement 2: Repository Intelligence – Change Understanding

**User Story:** As a developer, I want the Pipeline to analyze only the code affected by my commit, so that analysis is fast and focused on the current feature.

#### Acceptance Criteria

1. WHEN the Repository_Intelligence receives a Git_Diff, THE Repository_Intelligence SHALL identify the changed files, functions, and classes as the Changed_Feature.
2. THE Repository_Intelligence SHALL construct an Abstract Syntax Tree for each changed Python file.
3. THE Repository_Intelligence SHALL produce a symbol index, a call graph, and a dependency graph for the Changed_Feature.
4. THE Repository_Intelligence SHALL identify symbols related to the Changed_Feature through the call graph and dependency graph.
5. THE Repository_Intelligence SHALL output the Changed_Feature and its related repository context for use by later layers.
6. IF a changed file cannot be parsed into an Abstract Syntax Tree, THEN THE Repository_Intelligence SHALL record the file as unparseable and continue processing the remaining changed files.

### Requirement 3: Detection Layer – Parallel Deterministic Scanning

**User Story:** As a security engineer, I want multiple specialized scanners to run in parallel on the changed code, so that different vulnerability classes are detected quickly and deterministically.

#### Acceptance Criteria

1. WHEN the Repository_Intelligence output is available, THE Detection_Layer SHALL run Bandit, Semgrep, CodeQL, Gitleaks, Checkov, and Trivy in parallel.
2. THE Detection_Layer SHALL scope each Scanner to the Changed_Feature and its related repository context.
3. WHEN all Scanners complete, THE Detection_Layer SHALL collect every Finding produced by each Scanner.
4. IF an individual Scanner fails to complete, THEN THE Detection_Layer SHALL record the Scanner failure, continue collecting Findings from the remaining Scanners, and mark the failed Scanner's coverage as incomplete in the Pull_Request_Report.
5. THE Detection_Layer SHALL record, for each Finding, the originating Scanner, the affected location, and the Scanner-assigned severity.

### Requirement 4: Detection Layer – Scanner Coverage

**User Story:** As a security engineer, I want each scanner to cover its designated vulnerability classes, so that the pipeline provides comprehensive detection across code, secrets, IaC, and dependencies.

#### Acceptance Criteria

1. THE Detection_Layer SHALL use Bandit to detect Python security issues including unsafe subprocess use, os.system use, eval and exec use, unsafe deserialization, weak cryptography, hardcoded passwords, and unsafe YAML loading.
2. THE Detection_Layer SHALL use Semgrep to detect pattern-based issues including SQL injection, command injection, cross-site scripting, server-side request forgery, path traversal, authentication and authorization flaws, and configured company-specific rules.
3. THE Detection_Layer SHALL use CodeQL to detect semantic and data-flow issues including multi-function SQL injection, taint flow, authorization bypass, and resource leaks.
4. THE Detection_Layer SHALL use Gitleaks to detect secrets including API keys, cloud credentials, SSH keys, tokens, database passwords, and .env file leaks.
5. THE Detection_Layer SHALL use Checkov to detect Infrastructure-as-Code issues including publicly exposed cloud resources, weak IAM configuration, open security groups, Kubernetes misconfiguration, and Terraform and CloudFormation risks.
6. THE Detection_Layer SHALL use Trivy to detect dependency and container issues including dependency CVEs, container and filesystem vulnerabilities, Kubernetes configuration issues, and operating system package vulnerabilities.

### Requirement 5: Intelligence Layer – Normalization

**User Story:** As a security engineer, I want all findings converted into one common schema, so that findings from different scanners can be processed uniformly.

#### Acceptance Criteria

1. WHEN the Detection_Layer produces Findings, THE Intelligence_Layer SHALL convert each Finding into a Normalized_Finding that conforms to the Common_Schema.
2. THE Intelligence_Layer SHALL preserve the originating Scanner, affected location, and severity of each Finding within its Normalized_Finding.
3. IF a Finding is missing a field required by the Common_Schema, THEN THE Intelligence_Layer SHALL assign a defined default value for the missing field and record that a default was applied.

### Requirement 6: Intelligence Layer – Deduplication

**User Story:** As a security engineer, I want findings that describe the same vulnerability to be merged, so that I review each real issue only once.

#### Acceptance Criteria

1. WHEN multiple Normalized_Findings describe the same vulnerability at the same location, THE Intelligence_Layer SHALL merge them into a single Normalized_Finding.
2. WHEN the Intelligence_Layer merges Normalized_Findings, THE Intelligence_Layer SHALL retain the set of originating Scanners on the merged Normalized_Finding.
3. THE Intelligence_Layer SHALL preserve every distinct vulnerability as a separate Normalized_Finding after deduplication.

### Requirement 7: Intelligence Layer – Context Enrichment

**User Story:** As a security engineer, I want findings enriched with contextual signals, so that risk scoring reflects real-world exposure and impact.

#### Acceptance Criteria

1. THE Intelligence_Layer SHALL enrich each Normalized_Finding with reachability derived from the call graph.
2. THE Intelligence_Layer SHALL enrich each Normalized_Finding with business criticality derived from the Repository_Intelligence context.
3. THE Intelligence_Layer SHALL enrich each Normalized_Finding with an exposure classification of public or internal.
4. THE Intelligence_Layer SHALL enrich each Normalized_Finding with an authentication context.

### Requirement 8: Intelligence Layer – Risk Scoring

**User Story:** As a security engineer, I want a deterministic risk score for each finding, so that findings can be prioritized consistently.

#### Acceptance Criteria

1. THE Intelligence_Layer SHALL compute a Risk_Score for each enriched Normalized_Finding as Severity × Reachability × Business_Criticality × Exploitability × Repository_Context.
2. WHEN two enriched Normalized_Findings have identical scoring inputs, THE Intelligence_Layer SHALL assign them identical Risk_Scores.
3. THE Intelligence_Layer SHALL order Normalized_Findings by Risk_Score in descending order for downstream processing.

### Requirement 9: Intelligence Layer – AI Triage

**User Story:** As a developer, I want AI to explain and prioritize findings and flag likely false positives, so that I can focus on the issues that matter.

#### Acceptance Criteria

1. WHEN a Normalized_Finding is available for triage, THE Intelligence_Layer SHALL produce an AI_Triage that explains the Finding, states a priority, and suggests a secure fix approach.
2. WHERE AI_Triage identifies a Normalized_Finding as a likely false positive, THE Intelligence_Layer SHALL label the Normalized_Finding as a likely false positive and retain the Finding for human review.
3. THE Intelligence_Layer SHALL attach the AI_Triage result to the corresponding Normalized_Finding without altering the deterministic Risk_Score.

### Requirement 10: Intelligence Layer – AI Repair

**User Story:** As a developer, I want AI to generate candidate patches for verified findings, so that fixes are proposed automatically for my review.

#### Acceptance Criteria

1. WHEN a Normalized_Finding is confirmed by a Scanner and is not labeled a likely false positive, THE Intelligence_Layer SHALL generate a candidate patch through AI_Repair.
2. THE Intelligence_Layer SHALL associate each candidate patch with the Normalized_Finding it targets.
3. THE Intelligence_Layer SHALL treat every candidate patch as a proposal and SHALL NOT merge the candidate patch without human approval.
4. IF AI_Repair cannot produce a candidate patch for a Normalized_Finding, THEN THE Intelligence_Layer SHALL mark the Normalized_Finding as unresolved and record the reason.

### Requirement 11: Intelligence Layer – Deterministic Verification

**User Story:** As a security engineer, I want every AI-proposed fix re-verified by the scanners, so that only genuinely resolved issues are accepted.

#### Acceptance Criteria

1. WHEN a candidate patch is generated, THE Intelligence_Layer SHALL re-run the Scanners against the patched code as Verification.
2. WHERE Verification confirms that the targeted Normalized_Finding is resolved, THE Intelligence_Layer SHALL accept the candidate patch and mark the Normalized_Finding as fixed.
3. IF Verification does not confirm resolution of the targeted Normalized_Finding, THEN THE Intelligence_Layer SHALL reject the candidate patch and mark the Normalized_Finding as unresolved.
4. IF an accepted candidate patch introduces a new Normalized_Finding, THEN THE Intelligence_Layer SHALL reject the candidate patch and mark the original Normalized_Finding as unresolved.

### Requirement 12: Governance Layer – Quality Gate

**User Story:** As an engineering manager, I want organizational quality thresholds enforced, so that only code meeting our standards is recommended for merge.

#### Acceptance Criteria

1. THE Governance_Layer SHALL evaluate the code against a Quality_Gate using SonarQube metrics for maintainability, code smells, technical debt, security hotspots, and coverage.
2. WHERE a Repo_Config defines Quality_Gate thresholds, THE Governance_Layer SHALL apply the Repo_Config thresholds instead of the default thresholds.
3. WHERE a Repo_Config does not define Quality_Gate thresholds, THE Governance_Layer SHALL apply the default thresholds of zero critical findings, coverage of at least 90 percent, zero leaked secrets, and zero blocking Infrastructure-as-Code issues.
4. WHEN every Quality_Gate threshold is satisfied, THE Governance_Layer SHALL record the Quality_Gate status as passed.
5. IF any Quality_Gate threshold is not satisfied, THEN THE Governance_Layer SHALL record the Quality_Gate status as failed and record each unsatisfied threshold.

### Requirement 13: Governance Layer – Merge Confidence

**User Story:** As a reviewer, I want a merge confidence score, so that I can quickly gauge how ready a change is to merge.

#### Acceptance Criteria

1. THE Governance_Layer SHALL compute a Merge_Confidence from testing confidence, security confidence, coverage, remaining findings, and Quality_Gate status.
2. WHEN inputs to the Merge_Confidence computation are identical, THE Governance_Layer SHALL produce an identical Merge_Confidence value.
3. THE Governance_Layer SHALL record the Merge_Confidence as advisory and SHALL NOT trigger an automatic merge based on the Merge_Confidence.

### Requirement 14: Governance Layer – Pull Request Report

**User Story:** As a reviewer, I want a generated report attached to the Pull Request, so that I have a complete summary to make the merge decision.

#### Acceptance Criteria

1. WHEN the Governance_Layer completes evaluation, THE Governance_Layer SHALL generate a Pull_Request_Report on the GitHub Pull Request for the Commit_SHA.
2. THE Pull_Request_Report SHALL include a testing summary, a security summary, the list of fixed Normalized_Findings, the list of remaining Normalized_Findings, and the Merge_Confidence.
3. THE Pull_Request_Report SHALL include the Quality_Gate status and each unsatisfied threshold when the Quality_Gate status is failed.
4. THE Pull_Request_Report SHALL identify any Scanner whose coverage was marked incomplete.
5. THE Governance_Layer SHALL leave the final merge decision to a human reviewer.

### Requirement 15: Configuration Management

**User Story:** As a repository owner, I want to configure the pipeline per repository, so that thresholds and scanner behavior match my project's needs.

#### Acceptance Criteria

1. WHERE a Repo_Config file is present, THE Pipeline SHALL apply the configured Quality_Gate thresholds, scanner rule settings, and pipeline settings from the Repo_Config.
2. IF a Repo_Config value is malformed, THEN THE Pipeline SHALL reject the malformed value, apply the corresponding default value, and record the substitution in the Pull_Request_Report.
3. WHERE no Repo_Config file is present, THE Pipeline SHALL apply the default configuration values.
