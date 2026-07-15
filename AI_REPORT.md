# AI Software Delivery Engineer: Architecture Review

**Repository:** kuchurisatwik/DeliveryOS
**Commit SHA:** 30819b0132e7493ebeecbc05b3ed725558aa521c
**Branch:** ai-sde/review-30819b0-20260715142537
**Timestamp:** 2026-07-15T14:26:22.483465Z

No AI analysis was generated.

---
## 🔒 Security Pipeline Report
**Commit:** `30819b0132e7493ebeecbc05b3ed725558aa521c`
**Security Summary:** 0 finding(s) fixed; 108 finding(s) remaining; quality gate failed.
**Scanned scope:** 12 changed file(s).

**Findings by severity:** CRITICAL: 11, HIGH: 48, MEDIUM: 40, LOW: 9

### 🛰️ Scanner Coverage
6/6 scanner(s) completed. A ❌ scanner ran but its result could not be collected — treat its coverage as unknown, not clean.

| Scanner | Status | Findings | Detail |
|---|---|---|---|
| bandit | ✅ ran | 21 | completed |
| semgrep | ✅ ran | 8 | completed |
| codeql | ✅ ran | 2 | completed |
| gitleaks | ✅ ran | 2 | completed |
| checkov | ✅ ran | 0 | completed |
| trivy | ✅ ran | 75 | completed |

### Merge Confidence (advisory)
**Score:** 0.0 (advisory — human makes the final merge decision)

### Quality Gate
**Status:** failed

**Unsatisfied thresholds:**
- `max_critical_findings`: expected <= 0, actual 11
- `max_leaked_secrets`: expected <= 0, actual 2
- `min_coverage_percent`: expected >= 90.0, actual 0.0

### ✅ Fixed Findings (0)
None.

### ❗ Remaining Findings (108)
- **python.lang.security.audit.subprocess-shell-true.subprocess-shell-true** (HIGH, code) at `security_samples\bandit_samples.py:31` — scanners: semgrep — AI repair unavailable (LLM error); finding retained for review.
- **python.lang.security.audit.subprocess-shell-true.subprocess-shell-true** (HIGH, code) at `security_samples\semgrep_samples.py:34` — scanners: semgrep — AI repair unavailable (LLM error); finding retained for review.
- **python.requests.security.disabled-cert-validation.disabled-cert-validation** (HIGH, code) at `security_samples\semgrep_samples.py:44` — scanners: semgrep — AI repair unavailable (LLM error); finding retained for review.
- **py/clear-text-storage-sensitive-data** (HIGH, code) at `security_samples/bandit_samples.py:58` — scanners: codeql — AI repair unavailable (LLM error); finding retained for review.
- **py/weak-sensitive-data-hashing** (HIGH, code) at `security_samples/bandit_samples.py:51` — scanners: codeql — AI repair unavailable (LLM error); finding retained for review.
- **python.lang.security.audit.eval-detected.eval-detected** (MEDIUM, code) at `security_samples\bandit_samples.py:21` — scanners: semgrep — AI repair unavailable (LLM error); finding retained for review.
- **python.lang.security.audit.exec-detected.exec-detected** (MEDIUM, code) at `security_samples\bandit_samples.py:26` — scanners: semgrep — AI repair unavailable (LLM error); finding retained for review.
- **python.lang.security.deserialization.pickle.avoid-pickle** (MEDIUM, code) at `security_samples\bandit_samples.py:41` — scanners: semgrep — AI repair unavailable (LLM error); finding retained for review.
- **python.lang.security.insecure-hash-algorithms-md5.insecure-hash-algorithm-md5** (MEDIUM, code) at `security_samples\bandit_samples.py:51` — scanners: semgrep — AI repair unavailable (LLM error); finding retained for review.
- **python.lang.security.audit.md5-used-as-password.md5-used-as-password** (MEDIUM, code) at `security_samples\bandit_samples.py:51` — scanners: semgrep — AI repair unavailable (LLM error); finding retained for review.
- **cve-2019-14234** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2019-19844** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2020-7471** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2022-28346** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2022-28347** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2025-64459** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2019-20477** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2020-14343** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2020-1747** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **aws-0104** (CRITICAL, dependency) at `security_samples/insecure_terraform.tf:37` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **aws-access-key-id** (CRITICAL, dependency) at `security_samples/gitleaks_secrets.txt:7` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **b602** (HIGH, code) at `.\security_samples/bandit_samples.py:31` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b605** (HIGH, code) at `.\security_samples/bandit_samples.py:36` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b324** (HIGH, code) at `.\security_samples/bandit_samples.py:51` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b605** (HIGH, code) at `.\security_samples/codeql_taintflow.py:36` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b602** (HIGH, code) at `.\security_samples/semgrep_samples.py:34` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b605** (HIGH, code) at `.\security_samples/semgrep_samples.py:39` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b501** (HIGH, code) at `.\security_samples/semgrep_samples.py:44` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **generic-api-key** (HIGH, secret) at `security_samples/gitleaks_secrets.txt:13` — scanners: gitleaks — AI repair unavailable (LLM error); finding retained for review.
- **private-key** (HIGH, secret) at `security_samples/gitleaks_secrets.txt:17` — scanners: gitleaks — AI repair unavailable (LLM error); finding retained for review.
- **cve-2019-14232** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2019-14233** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2019-14235** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2019-19118** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2020-13254** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2020-24583** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2020-9402** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2021-31542** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2021-33571** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2021-45115** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2021-45116** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2022-23833** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2022-36359** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2025-57833** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2025-64458** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2018-1000656** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2019-1010083** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2023-30861** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2018-18074** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- **cve-2019-11324** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — AI repair unavailable (LLM error); finding retained for review.
- _…and 58 more (showing the 50 highest-risk findings; see the severity breakdown above for the full distribution)._

_The final merge decision is left to a human reviewer; this report is advisory and does not trigger a merge._
