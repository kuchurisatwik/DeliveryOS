# AI Software Delivery Engineer: Architecture Review

**Repository:** kuchurisatwik/DeliveryOS
**Commit SHA:** 2f8d2386d74db87a3f7a7adf79808666742c01a1
**Branch:** ai-sde/review-2f8d238-20260715105802
**Timestamp:** 2026-07-15T10:59:07.879044Z

No AI analysis was generated.

---
## 🔒 Security Pipeline Report
**Commit:** `2f8d2386d74db87a3f7a7adf79808666742c01a1`
**Security Summary:** 0 finding(s) fixed; 403 finding(s) remaining; quality gate failed.
**Scanned scope:** 81 changed file(s).

**Findings by severity:** MEDIUM: 1, LOW: 402

### 🛰️ Scanner Coverage
6/6 scanner(s) completed. A ❌ scanner ran but its result could not be collected — treat its coverage as unknown, not clean.

| Scanner | Status | Findings | Detail |
|---|---|---|---|
| bandit | ✅ ran | 403 | completed |
| semgrep | ✅ ran | 0 | completed |
| codeql | ✅ ran | 0 | completed |
| gitleaks | ✅ ran | 0 | completed |
| checkov | ✅ ran | 0 | completed |
| trivy | ✅ ran | 0 | completed |

### Merge Confidence (advisory)
**Score:** 0.0 (advisory — human makes the final merge decision)

### Quality Gate
**Status:** failed

**Unsatisfied thresholds:**
- `min_coverage_percent`: expected >= 90.0, actual 0.0

> ℹ️ The gate failed only on coverage. In security-only runs without SonarQube configured, coverage reports as 0 and this threshold cannot pass — this is a configuration artifact, not a security finding.

### ✅ Fixed Findings (0)
None.

### ❗ Remaining Findings (403)
- **b108** (MEDIUM, code) at `.\tests/security/test_property_20_no_automatic_merge.py:74` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b404** (LOW, code) at `.\app/security/detection/adapters/base.py:33` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b603** (LOW, code) at `.\app/security/detection/adapters/base.py:94` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:304` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:305` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:307` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:315` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:316` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:317` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:318` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:319` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:320` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:324` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:326` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:330` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:331` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:332` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:336` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:337` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:343` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:344` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:346` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:347` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:349` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:350` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:351` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:353` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:358` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:361` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:362` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:373` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:375` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:377` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_end_to_end_pipeline.py:379` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b106** (LOW, code) at `.\tests/security/test_governance_integration.py:117` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_governance_integration.py:123` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_governance_integration.py:125` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_governance_integration.py:126` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_governance_integration.py:127` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_governance_integration.py:128` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_governance_integration.py:129` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_governance_integration.py:132` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_governance_integration.py:133` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_governance_integration.py:134` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_governance_integration.py:137` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b106** (LOW, code) at `.\tests/security/test_governance_integration.py:164` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_governance_integration.py:168` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_governance_integration.py:169` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b101** (LOW, code) at `.\tests/security/test_governance_integration.py:170` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- **b106** (LOW, code) at `.\tests/security/test_governance_integration.py:178` — scanners: bandit — AI repair unavailable (LLM error); finding retained for review.
- _…and 353 more (showing the 50 highest-risk findings; see the severity breakdown above for the full distribution)._

_The final merge decision is left to a human reviewer; this report is advisory and does not trigger a merge._
