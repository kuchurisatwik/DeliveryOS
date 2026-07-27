
---
## 🔒 Security Pipeline Report
**Commit:** [`LOCAL-FULL`](https://github.com/local/erp-main/commit/LOCAL-FULL-SCAN)
**Repository:** `local/erp-main`
**Branch under review:** `main`
**Security Summary:** 0 finding(s) fixed; 9 finding(s) remaining; quality gate failed; incomplete scanner coverage: codeql, trivy.
**Scanned scope:** whole repository (full audit mode).

**Findings by severity:** HIGH: 1, MEDIUM: 8

### 🛠️ Remediation Guide — Key High/Critical Findings
The 1 highest-severity rule(s) below account for the key risk in this change. Each fix applies to all listed occurrences. CRITICAL rules include a concrete patch; HIGH rules include an illustrative before/after.

#### HIGH · generic-api-key — 1 occurrence(s) · P1
- **Scanners:** gitleaks
- **Where:** `diigoo-erp/apps/web/src/modules/marketing/store.ts:15`
- **Why it matters:** Detected a Generic API Key, potentially exposing access to various services and sensitive operations. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

### 📋 Other Findings — Standard Remediation (no AI)
2 lower-severity rule(s), each with standard guidance (deterministic, no LLM call):

| Severity | Rule | Count | How to fix |
|---|---|---|---|
| MEDIUM | `ckv_docker_2` | 5 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_docker_3` | 3 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |

### 🛰️ Scanner Coverage
5/7 scanner(s) completed. A ❌ scanner ran but its result could not be collected — treat its coverage as unknown, not clean.

| Scanner | Status | Findings | Detail |
|---|---|---|---|
| bandit | ✅ ran | 0 | completed |
| semgrep | ✅ ran | 0 | completed |
| codeql | ❌ failed | — | all language analyses failed — javascript: exited 99: Running queries. |
| gitleaks | ✅ ran | 1 | completed |
| checkov | ✅ ran | 8 | completed |
| trivy | ❌ failed | — | exited 1: 2026-07-21T14:40:07+05:30	FATAL	Error	remote Maven repository returned 429 Too Many Requests for https://repo.maven.apache.org/maven2/org/springframework/boot/spring-boot-starter-parent/3.3… |
| njsscan | ✅ ran | 0 | completed |

### Merge Confidence (advisory)
**Score:** 0.0 (advisory — human makes the final merge decision)

### Quality Gate
**Status:** failed

**Unsatisfied thresholds:**
- `max_leaked_secrets`: expected <= 0, actual 1
- `min_coverage_percent`: expected >= 90.0, actual 0.0

### ✅ Fixed Findings (0)
None.

### ❗ Remaining Findings (9)
- **generic-api-key** (HIGH, secret) at `diigoo-erp/apps/web/src/modules/marketing/store.ts:15` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Detected a Generic API Key, potentially exposing access to various services and sensitive operations. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **ckv_docker_2** (MEDIUM, iac) at `/hrm-standalone\frontend\Dockerfile:1` — scanners: checkov — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Ensure that HEALTHCHECK instructions have been added to container images_
  - **Suggested fix approach:** Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled.
- **ckv_docker_3** (MEDIUM, iac) at `/hrm-standalone\frontend\Dockerfile:1` — scanners: checkov — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Ensure that a user for the container has been created_
  - **Suggested fix approach:** Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled.
- **ckv_docker_2** (MEDIUM, iac) at `/diigoo-erp\services\core\Dockerfile:1` — scanners: checkov — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Ensure that HEALTHCHECK instructions have been added to container images_
  - **Suggested fix approach:** Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled.
- **ckv_docker_3** (MEDIUM, iac) at `/diigoo-erp\services\core\Dockerfile:1` — scanners: checkov — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Ensure that a user for the container has been created_
  - **Suggested fix approach:** Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled.
- **ckv_docker_2** (MEDIUM, iac) at `/diigoo-erp\apps\web\Dockerfile:1` — scanners: checkov — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Ensure that HEALTHCHECK instructions have been added to container images_
  - **Suggested fix approach:** Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled.
- **ckv_docker_3** (MEDIUM, iac) at `/diigoo-erp\apps\web\Dockerfile:1` — scanners: checkov — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Ensure that a user for the container has been created_
  - **Suggested fix approach:** Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled.
- **ckv_docker_2** (MEDIUM, iac) at `/backend\Dockerfile:1` — scanners: checkov — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Ensure that HEALTHCHECK instructions have been added to container images_
  - **Suggested fix approach:** Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled.
- **ckv_docker_2** (MEDIUM, iac) at `/hrm-standalone\backend\Dockerfile:1` — scanners: checkov — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Ensure that HEALTHCHECK instructions have been added to container images_
  - **Suggested fix approach:** Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled.

_The final merge decision is left to a human reviewer; this report is advisory and does not trigger a merge._
