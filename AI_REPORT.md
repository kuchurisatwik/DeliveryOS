# AI Software Delivery Engineer: Architecture Review

**Repository:** kuchurisatwik/DeliveryOS
**Commit SHA:** b5b6ced0447237188b47d99873e33475c42e2168
**Branch:** ai-sde/review-b5b6ced-20260727152307
**Timestamp:** 2026-07-27T15:23:26.523227Z

No AI analysis was generated.

---
## 🔒 Security Pipeline Report
**Commit:** [`b5b6ced044`](https://github.com/kuchurisatwik/DeliveryOS/commit/b5b6ced0447237188b47d99873e33475c42e2168)
**Repository:** `kuchurisatwik/DeliveryOS`
**Branch under review:** `main`
**Security Summary:** 0 finding(s) fixed; 74 finding(s) remaining; quality gate failed; incomplete scanner coverage: bandit, codeql, checkov, njsscan.
**Scanned scope:** whole repository (full audit mode).

**Findings by severity:** CRITICAL: 6, HIGH: 37, MEDIUM: 21, LOW: 10

### 🛠️ Remediation Guide — Key High/Critical Findings
The 30 highest-severity rule(s) below account for the key risk in this change. Each fix applies to all listed occurrences. CRITICAL rules include a concrete patch; HIGH rules include an illustrative before/after.

#### CRITICAL · aws-access-key-id — 2 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/gitleaks_secrets.txt:7, security_samples/multilang/leaked_creds.env:7`
- **Why it matters:** AWS Access Key ID (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### CRITICAL · cve-2019-20477 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/multilang/requirements.txt:0`
- **Why it matters:** PyYAML: command execution through python/object/apply constructor in FullLoader (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### CRITICAL · cve-2020-14343 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/multilang/requirements.txt:0`
- **Why it matters:** PyYAML: incomplete fix for CVE-2020-1747 (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### CRITICAL · aws-0104 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:37`
- **Why it matters:** A security group rule should not allow unrestricted egress to any IP address. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### CRITICAL · ds-0031 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/multilang/Dockerfile:9`
- **Why it matters:** Secrets passed via `build-args` or envs or copied secret files (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · python.lang.security.audit.subprocess-shell-true.subprocess-shell-true — 2 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\bandit_samples.py:31, security_samples\semgrep_samples.py:34`
- **Why it matters:** Found 'subprocess' function 'call' with 'shell=True'. This is dangerous because this call will spawn the command using a shell process. Doing so propagates current shell settings and variables, which makes it much easier for a malicious actor to execute commands. Use 'shell=False' instead. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · javascript.lang.security.detect-child-process.detect-child-process — 2 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\api.ts:8, security_samples\multilang\server.js:21`
- **Why it matters:** Detected calls to child_process from a function argument `req`. This could lead to a command injection if the input is user controllable. Try to avoid calls to child_process, and if it is needed ensure user input is correctly sanitized or sandboxed.  (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · generic-api-key — 2 occurrence(s) · P1
- **Scanners:** gitleaks
- **Where:** `security_samples/multilang/leaked_creds.env:11, security_samples/gitleaks_secrets.txt:13`
- **Why it matters:** Detected a Generic API Key, potentially exposing access to various services and sensitive operations. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · private-key — 2 occurrence(s) · P1
- **Scanners:** gitleaks, trivy
- **Where:** `security_samples/gitleaks_secrets.txt:17, security_samples/gitleaks_secrets.txt:18`
- **Why it matters:** Identified a Private Key, which may compromise cryptographic security and sensitive data encryption. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · ds-0002 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/Dockerfile:0, security_samples/multilang/Dockerfile:0`
- **Why it matters:** Image user should not be 'root' (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0086 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:14, security_samples/multilang/infra.tf:19`
- **Why it matters:** S3 Access block should block public ACL (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0087 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:15, security_samples/multilang/infra.tf:19`
- **Why it matters:** S3 Access block should block public policy (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0091 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:16, security_samples/multilang/infra.tf:19`
- **Why it matters:** S3 Access Block should Ignore Public ACL (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0092 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:8, security_samples/multilang/infra.tf:21`
- **Why it matters:** S3 Buckets not publicly accessible through ACL. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0093 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:17, security_samples/multilang/infra.tf:19`
- **Why it matters:** S3 Access block should restrict public bucket to limit access (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0107 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:29, security_samples/multilang/infra.tf:14`
- **Why it matters:** Security groups should not allow unrestricted ingress to SSH or RDP from any IP address. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0132 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:5, security_samples/multilang/infra.tf:19`
- **Why it matters:** S3 encryption should use Customer Managed Keys (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · go.lang.security.injection.tainted-sql-string.tainted-sql-string — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\handler.go:16`
- **Why it matters:** User data flows into this manually-constructed SQL string. User data can be safely inserted into SQL strings using prepared statements or an object-relational mapper (ORM). Manually-constructed SQL strings is a possible indicator of SQL injection, which could let an attacker steal or manipulate data from the database. Instead, use prepared statements (`db.Query("SELECT * FROM t WHERE id = ?", id)`) or a safe library. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · php.lang.security.injection.tainted-sql-string.tainted-sql-string — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\index.php:7`
- **Why it matters:** User data flows into this manually-constructed SQL string. User data can be safely inserted into SQL strings using prepared statements or an object-relational mapper (ORM). Manually-constructed SQL strings is a possible indicator of SQL injection, which could let an attacker steal or manipulate data from the database. Instead, use prepared statements (`$mysqli->prepare("INSERT INTO test(id, label) VALUES (?, ?)");`) or a safe library. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · php.lang.security.injection.echoed-request.echoed-request — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\index.php:11`
- **Why it matters:** `Echo`ing user input risks cross-site scripting vulnerability. You should use `htmlentities()` when showing data to users. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · php.lang.security.tainted-exec.tainted-exec — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\index.php:11`
- **Why it matters:** Executing non-constant commands. This can lead to command injection. You should use `escapeshellarg()` when using command. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · javascript.lang.security.audit.code-string-concat.code-string-concat — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\server.js:26`
- **Why it matters:** Found data from an Express or Next web request flowing to `eval`. If this data is user-controllable this can lead to execution of arbitrary system commands in the context of your application process. Avoid `eval` whenever possible. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · python.flask.security.injection.subprocess-injection.subprocess-injection — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\vuln_app.py:23`
- **Why it matters:** Detected user input entering a `subprocess` call unsafely. This could result in a command injection vulnerability. An attacker could use this vulnerability to execute arbitrary commands on the host, which allows them to download malware, scan sensitive data, or run any command they wish on the server. Do not let users choose the command to run. In general, prefer to use Python API versions of system commands. If you must use subprocess, use a dictionary to allowlist a set of commands. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · python.flask.security.injection.tainted-sql-string.tainted-sql-string — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\vuln_app.py:32`
- **Why it matters:** Detected user input used to manually construct a SQL string. This is usually bad practice because manual construction could accidentally result in a SQL injection. An attacker could use a SQL injection to steal or modify contents of the database. Instead, use a parameterized query which is available by default in most database engines. Alternatively, consider using an object-relational mapper (ORM) such as SQLAlchemy which will protect your queries. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · python.requests.security.disabled-cert-validation.disabled-cert-validation — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\semgrep_samples.py:44`
- **Why it matters:** Certificate verification has been explicitly disabled. This permits insecure connections to insecure servers. Re-enable certification validation. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · hashicorp-tf-password — 1 occurrence(s) · P1
- **Scanners:** gitleaks
- **Where:** `security_samples/multilang/infra.tf:31`
- **Why it matters:** Identified a HashiCorp Terraform password field, risking unauthorized infrastructure configuration and security breaches. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · cve-2019-10906 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/multilang/requirements.txt:0`
- **Why it matters:** python-jinja2: str.format_map allows sandbox escape (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · ds-0029 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/multilang/Dockerfile:6`
- **Why it matters:** 'apt-get' missing '--no-install-recommends' (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0080 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/multilang/infra.tf:32`
- **Why it matters:** RDS encryption has not been enabled at a DB Instance level. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0180 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/multilang/infra.tf:33`
- **Why it matters:** RDS Publicly Accessible (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

### 📋 Other Findings — Standard Remediation (no AI)
24 lower-severity rule(s), each with standard guidance (deterministic, no LLM call):

| Severity | Rule | Count | How to fix |
|---|---|---|---|
| MEDIUM | `python.lang.security.audit.eval-detected.eval-detected` | 2 | Remove `eval()`. Use explicit parsing or a whitelist dispatch instead. |
| MEDIUM | `python.lang.security.insecure-hash-algorithms-md5.insecure-hash-algorithm-md5` | 2 | Replace the weak hash (MD5/SHA1) with SHA-256+ (bcrypt/Argon2 for passwords). |
| MEDIUM | `aws-0090` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `python.lang.security.audit.exec-detected.exec-detected` | 1 | Remove `exec()`. Call the intended logic directly. |
| MEDIUM | `python.lang.security.deserialization.pickle.avoid-pickle` | 1 | Do not deserialize untrusted data with pickle. Use JSON or a schema-validated format. |
| MEDIUM | `go.lang.security.audit.net.use-tls.use-tls` | 1 | Review against secure-coding guidance for this rule and apply the standard fix (validate input, avoid dangerous APIs). |
| MEDIUM | `javascript.express.security.audit.xss.direct-response-write.direct-response-write` | 1 | Review against secure-coding guidance for this rule and apply the standard fix (validate input, avoid dangerous APIs). |
| MEDIUM | `ruby.lang.security.dangerous-exec.dangerous-exec` | 1 | Review against secure-coding guidance for this rule and apply the standard fix (validate input, avoid dangerous APIs). |
| MEDIUM | `cve-2020-28493` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2024-22195` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2024-34064` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2024-56326` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2025-27516` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `ds-0001` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ds-0004` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `aws-0077` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `aws-0176` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `aws-0177` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| LOW | `aws-0124` | 3 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| LOW | `ds-0026` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| LOW | `aws-0089` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| LOW | `aws-0094` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| LOW | `aws-0099` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| LOW | `aws-0133` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |

### 🛰️ Scanner Coverage
3/7 scanner(s) completed. A ❌ scanner ran but its result could not be collected — treat its coverage as unknown, not clean.

| Scanner | Status | Findings | Detail |
|---|---|---|---|
| bandit | ❌ failed | — | tool not installed: 'bandit' not found on PATH |
| semgrep | ✅ ran | 26 | completed |
| codeql | ❌ failed | — | all language analyses failed — javascript: tool not installed: 'codeql' not found on PATH; python: tool not installed: 'codeql' not found on PATH; ruby: tool not installed: 'codeql' not found on PATH |
| gitleaks | ✅ ran | 4 | completed |
| checkov | ❌ failed | — | tool not installed: 'checkov' not found on PATH |
| trivy | ✅ ran | 50 | completed |
| njsscan | ❌ failed | — | tool not installed: 'njsscan' not found on PATH |

### Merge Confidence (advisory)
**Score:** 0.0 (advisory — human makes the final merge decision)

### Quality Gate
**Status:** failed

**Unsatisfied thresholds:**
- `max_critical_findings`: expected <= 0, actual 6
- `max_leaked_secrets`: expected <= 0, actual 7
- `max_blocking_iac_issues`: expected <= 0, actual 21
- `min_coverage_percent`: expected >= 90.0, actual 0.0

### ✅ Fixed Findings (0)
None.

### ❗ Remaining Findings (74)
- **cve-2019-20477** (CRITICAL, dependency) at `security_samples/multilang/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _PyYAML: command execution through python/object/apply constructor in FullLoader (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **cve-2020-14343** (CRITICAL, dependency) at `security_samples/multilang/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _PyYAML: incomplete fix for CVE-2020-1747 (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0104** (CRITICAL, iac) at `security_samples/insecure_terraform.tf:37` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _A security group rule should not allow unrestricted egress to any IP address. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **ds-0031** (CRITICAL, iac) at `security_samples/multilang/Dockerfile:9` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Secrets passed via `build-args` or envs or copied secret files (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-access-key-id** (CRITICAL, secret) at `security_samples/gitleaks_secrets.txt:7` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _AWS Access Key ID (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-access-key-id** (CRITICAL, secret) at `security_samples/multilang/leaked_creds.env:7` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _AWS Access Key ID (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **python.lang.security.audit.subprocess-shell-true.subprocess-shell-true** (HIGH, code) at `security_samples\bandit_samples.py:31` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Found 'subprocess' function 'call' with 'shell=True'. This is dangerous because this call will spawn the command using a shell process. Doing so propagates current shell settings and variables, which makes it much easier for a malicious actor to execute commands. Use 'shell=False' instead. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **javascript.lang.security.detect-child-process.detect-child-process** (HIGH, code) at `security_samples\multilang\api.ts:8` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Detected calls to child_process from a function argument `req`. This could lead to a command injection if the input is user controllable. Try to avoid calls to child_process, and if it is needed ensure user input is correctly sanitized or sandboxed.  (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **go.lang.security.injection.tainted-sql-string.tainted-sql-string** (HIGH, code) at `security_samples\multilang\handler.go:16` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _User data flows into this manually-constructed SQL string. User data can be safely inserted into SQL strings using prepared statements or an object-relational mapper (ORM). Manually-constructed SQL strings is a possible indicator of SQL injection, which could let an attacker steal or manipulate data from the database. Instead, use prepared statements (`db.Query("SELECT * FROM t WHERE id = ?", id)`) or a safe library. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **php.lang.security.injection.tainted-sql-string.tainted-sql-string** (HIGH, code) at `security_samples\multilang\index.php:7` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _User data flows into this manually-constructed SQL string. User data can be safely inserted into SQL strings using prepared statements or an object-relational mapper (ORM). Manually-constructed SQL strings is a possible indicator of SQL injection, which could let an attacker steal or manipulate data from the database. Instead, use prepared statements (`$mysqli->prepare("INSERT INTO test(id, label) VALUES (?, ?)");`) or a safe library. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **php.lang.security.injection.echoed-request.echoed-request** (HIGH, code) at `security_samples\multilang\index.php:11` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _`Echo`ing user input risks cross-site scripting vulnerability. You should use `htmlentities()` when showing data to users. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **php.lang.security.tainted-exec.tainted-exec** (HIGH, code) at `security_samples\multilang\index.php:11` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Executing non-constant commands. This can lead to command injection. You should use `escapeshellarg()` when using command. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **javascript.lang.security.detect-child-process.detect-child-process** (HIGH, code) at `security_samples\multilang\server.js:21` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Detected calls to child_process from a function argument `req`. This could lead to a command injection if the input is user controllable. Try to avoid calls to child_process, and if it is needed ensure user input is correctly sanitized or sandboxed.  (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **javascript.lang.security.audit.code-string-concat.code-string-concat** (HIGH, code) at `security_samples\multilang\server.js:26` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Found data from an Express or Next web request flowing to `eval`. If this data is user-controllable this can lead to execution of arbitrary system commands in the context of your application process. Avoid `eval` whenever possible. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **python.flask.security.injection.subprocess-injection.subprocess-injection** (HIGH, code) at `security_samples\multilang\vuln_app.py:23` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Detected user input entering a `subprocess` call unsafely. This could result in a command injection vulnerability. An attacker could use this vulnerability to execute arbitrary commands on the host, which allows them to download malware, scan sensitive data, or run any command they wish on the server. Do not let users choose the command to run. In general, prefer to use Python API versions of system commands. If you must use subprocess, use a dictionary to allowlist a set of commands. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **python.flask.security.injection.tainted-sql-string.tainted-sql-string** (HIGH, code) at `security_samples\multilang\vuln_app.py:32` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Detected user input used to manually construct a SQL string. This is usually bad practice because manual construction could accidentally result in a SQL injection. An attacker could use a SQL injection to steal or modify contents of the database. Instead, use a parameterized query which is available by default in most database engines. Alternatively, consider using an object-relational mapper (ORM) such as SQLAlchemy which will protect your queries. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **python.lang.security.audit.subprocess-shell-true.subprocess-shell-true** (HIGH, code) at `security_samples\semgrep_samples.py:34` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Found 'subprocess' function 'call' with 'shell=True'. This is dangerous because this call will spawn the command using a shell process. Doing so propagates current shell settings and variables, which makes it much easier for a malicious actor to execute commands. Use 'shell=False' instead. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **python.requests.security.disabled-cert-validation.disabled-cert-validation** (HIGH, code) at `security_samples\semgrep_samples.py:44` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Certificate verification has been explicitly disabled. This permits insecure connections to insecure servers. Re-enable certification validation. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **generic-api-key** (HIGH, secret) at `security_samples/multilang/leaked_creds.env:11` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Detected a Generic API Key, potentially exposing access to various services and sensitive operations. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **hashicorp-tf-password** (HIGH, secret) at `security_samples/multilang/infra.tf:31` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Identified a HashiCorp Terraform password field, risking unauthorized infrastructure configuration and security breaches. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **generic-api-key** (HIGH, secret) at `security_samples/gitleaks_secrets.txt:13` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Detected a Generic API Key, potentially exposing access to various services and sensitive operations. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **private-key** (HIGH, secret) at `security_samples/gitleaks_secrets.txt:17` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Identified a Private Key, which may compromise cryptographic security and sensitive data encryption. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **cve-2019-10906** (HIGH, dependency) at `security_samples/multilang/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _python-jinja2: str.format_map allows sandbox escape (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **ds-0002** (HIGH, iac) at `security_samples/Dockerfile:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Image user should not be 'root' (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0086** (HIGH, iac) at `security_samples/insecure_terraform.tf:14` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 Access block should block public ACL (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0087** (HIGH, iac) at `security_samples/insecure_terraform.tf:15` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 Access block should block public policy (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0091** (HIGH, iac) at `security_samples/insecure_terraform.tf:16` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 Access Block should Ignore Public ACL (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0092** (HIGH, iac) at `security_samples/insecure_terraform.tf:8` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 Buckets not publicly accessible through ACL. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0093** (HIGH, iac) at `security_samples/insecure_terraform.tf:17` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 Access block should restrict public bucket to limit access (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0107** (HIGH, iac) at `security_samples/insecure_terraform.tf:29` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Security groups should not allow unrestricted ingress to SSH or RDP from any IP address. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0132** (HIGH, iac) at `security_samples/insecure_terraform.tf:5` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 encryption should use Customer Managed Keys (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **ds-0002** (HIGH, iac) at `security_samples/multilang/Dockerfile:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Image user should not be 'root' (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **ds-0029** (HIGH, iac) at `security_samples/multilang/Dockerfile:6` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _'apt-get' missing '--no-install-recommends' (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0080** (HIGH, iac) at `security_samples/multilang/infra.tf:32` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _RDS encryption has not been enabled at a DB Instance level. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0086** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 Access block should block public ACL (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0087** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 Access block should block public policy (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0091** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 Access Block should Ignore Public ACL (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0092** (HIGH, iac) at `security_samples/multilang/infra.tf:21` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 Buckets not publicly accessible through ACL. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0093** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 Access block should restrict public bucket to limit access (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0107** (HIGH, iac) at `security_samples/multilang/infra.tf:14` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Security groups should not allow unrestricted ingress to SSH or RDP from any IP address. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0132** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 encryption should use Customer Managed Keys (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0180** (HIGH, iac) at `security_samples/multilang/infra.tf:33` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _RDS Publicly Accessible (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **private-key** (HIGH, secret) at `security_samples/gitleaks_secrets.txt:18` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Identified a Private Key, which may compromise cryptographic security and sensitive data encryption. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **python.lang.security.audit.eval-detected.eval-detected** (MEDIUM, code) at `security_samples\bandit_samples.py:21` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Detected the use of eval(). eval() can be dangerous if used to evaluate dynamic content. If this content can be input from outside the program, this may be a code injection vulnerability. Ensure evaluated content is not definable by external sources._
  - **Suggested fix approach:** Remove `eval()`. Use explicit parsing or a whitelist dispatch instead.
- **python.lang.security.audit.exec-detected.exec-detected** (MEDIUM, code) at `security_samples\bandit_samples.py:26` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Detected the use of exec(). exec() can be dangerous if used to evaluate dynamic content. If this content can be input from outside the program, this may be a code injection vulnerability. Ensure evaluated content is not definable by external sources._
  - **Suggested fix approach:** Remove `exec()`. Call the intended logic directly.
- **python.lang.security.deserialization.pickle.avoid-pickle** (MEDIUM, code) at `security_samples\bandit_samples.py:41` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Avoid using `pickle`, which is known to lead to code execution vulnerabilities. When unpickling, the serialized data could be manipulated to run arbitrary code. Instead, consider serializing the relevant data as JSON or a similar text-based serialization format._
  - **Suggested fix approach:** Do not deserialize untrusted data with pickle. Use JSON or a schema-validated format.
- **python.lang.security.insecure-hash-algorithms-md5.insecure-hash-algorithm-md5** (MEDIUM, code) at `security_samples\bandit_samples.py:51` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Detected MD5 hash algorithm which is considered insecure. MD5 is not collision resistant and is therefore not suitable as a cryptographic signature. Use SHA256 or SHA3 instead._
  - **Suggested fix approach:** Replace the weak hash (MD5/SHA1) with SHA-256+ (bcrypt/Argon2 for passwords).
- **go.lang.security.audit.net.use-tls.use-tls** (MEDIUM, code) at `security_samples\multilang\handler.go:26` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Found an HTTP server without TLS. Use 'http.ListenAndServeTLS' instead. See https://golang.org/pkg/net/http/#ListenAndServeTLS for more information._
  - **Suggested fix approach:** Review against secure-coding guidance for this rule and apply the standard fix (validate input, avoid dangerous APIs).
- **javascript.express.security.audit.xss.direct-response-write.direct-response-write** (MEDIUM, code) at `security_samples\multilang\server.js:26` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Detected directly writing to a Response object from user-defined input. This bypasses any HTML escaping and may expose your application to a Cross-Site-scripting (XSS) vulnerability. Instead, use 'resp.render()' to render safely escaped HTML._
  - **Suggested fix approach:** Review against secure-coding guidance for this rule and apply the standard fix (validate input, avoid dangerous APIs).
- **ruby.lang.security.dangerous-exec.dangerous-exec** (MEDIUM, code) at `security_samples\multilang\service.rb:13` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Detected non-static command inside system. Audit the input to 'system'. If unverified user data can reach this call site, this is a code injection vulnerability. A malicious actor can inject a malicious script to execute arbitrary code._
  - **Suggested fix approach:** Review against secure-coding guidance for this rule and apply the standard fix (validate input, avoid dangerous APIs).
- _…and 24 more (showing the 50 highest-risk findings; see the severity breakdown above for the full distribution)._

_The final merge decision is left to a human reviewer; this report is advisory and does not trigger a merge._
