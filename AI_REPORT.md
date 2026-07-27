# AI Software Delivery Engineer: Architecture Review

**Repository:** kuchurisatwik/DeliveryOS
**Commit SHA:** a5415f36cadb33f948b39660d9096f8b1b3d4ed7
**Branch:** ai-sde/review-a5415f3-20260727121356
**Timestamp:** 2026-07-27T12:17:19.359689Z

No AI analysis was generated.

---
## 🔒 Security Pipeline Report
**Commit:** [`a5415f36ca`](https://github.com/kuchurisatwik/DeliveryOS/commit/a5415f36cadb33f948b39660d9096f8b1b3d4ed7)
**Repository:** `kuchurisatwik/DeliveryOS`
**Branch under review:** `feat/security-pipeline`
**Security Summary:** 0 finding(s) fixed; 662 finding(s) remaining; quality gate failed.
**Scanned scope:** whole repository (full audit mode).

**Findings by severity:** CRITICAL: 9, HIGH: 49, MEDIUM: 79, LOW: 525

### 🛠️ Remediation Guide — Key High/Critical Findings
The 40 highest-severity rule(s) below account for the key risk in this change. Each fix applies to all listed occurrences. CRITICAL rules include a concrete patch; HIGH rules include an illustrative before/after.

#### CRITICAL · aws-access-key-id — 2 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/gitleaks_secrets.txt:7, security_samples/multilang/leaked_creds.env:7`
- **Why it matters:** AWS Access Key ID (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### CRITICAL · py/command-line-injection — 1 occurrence(s) · P0
- **Scanners:** codeql, semgrep
- **Where:** `security_samples/multilang/vuln_app.py:23`
- **Why it matters:** This command line depends on a [user-provided value](1). (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### CRITICAL · js/command-line-injection — 1 occurrence(s) · P0
- **Scanners:** codeql, semgrep
- **Where:** `security_samples/multilang/server.js:21`
- **Why it matters:** This command line depends on a [user-provided value](1). (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### CRITICAL · js/code-injection — 1 occurrence(s) · P0
- **Scanners:** codeql, semgrep
- **Where:** `security_samples/multilang/server.js:26`
- **Why it matters:** This code execution depends on a [user-provided value](1). (AI unavailable — manual review recommended)
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

#### HIGH · b602 — 3 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `.\security_samples\bandit_samples.py:31, .\security_samples\multilang\vuln_app.py:23, .\security_samples\semgrep_samples.py:34`
- **Why it matters:** subprocess call with shell=True identified, security issue. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · b605 — 3 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `.\security_samples\bandit_samples.py:36, .\security_samples\codeql_taintflow.py:36, .\security_samples\semgrep_samples.py:39`
- **Why it matters:** Starting a process with a shell, possible injection detected, security issue. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · b324 — 2 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `.\security_samples\bandit_samples.py:51, .\security_samples\multilang\vuln_app.py:38`
- **Why it matters:** Use of weak MD5 hash for security. Consider usedforsecurity=False (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · python.lang.security.audit.subprocess-shell-true.subprocess-shell-true — 2 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\bandit_samples.py:31, security_samples\semgrep_samples.py:34`
- **Why it matters:** Found 'subprocess' function 'call' with 'shell=True'. This is dangerous because this call will spawn the command using a shell process. Doing so propagates current shell settings and variables, which makes it much easier for a malicious actor to execute commands. Use 'shell=False' instead. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · js/missing-rate-limiting — 2 occurrence(s) · P1
- **Scanners:** codeql
- **Where:** `security_samples/multilang/server.js:10, security_samples/multilang/server.js:19`
- **Why it matters:** This route handler performs [a database access](1), but is not rate-limited. (AI unavailable — manual review recommended)
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

#### HIGH · python.flask.security.injection.tainted-sql-string.tainted-sql-string — 1 occurrence(s) · P1
- **Scanners:** codeql, semgrep
- **Where:** `security_samples\multilang\vuln_app.py:32`
- **Why it matters:** Detected user input used to manually construct a SQL string. This is usually bad practice because manual construction could accidentally result in a SQL injection. An attacker could use a SQL injection to steal or modify contents of the database. Instead, use a parameterized query which is available by default in most database engines. Alternatively, consider using an object-relational mapper (ORM) such as SQLAlchemy which will protect your queries. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · b501 — 1 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `.\security_samples\semgrep_samples.py:44`
- **Why it matters:** Call to requests with verify=False disabling SSL certificate checks, security issue. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · py/weak-sensitive-data-hashing — 1 occurrence(s) · P1
- **Scanners:** codeql, semgrep
- **Where:** `security_samples/bandit_samples.py:51`
- **Why it matters:** [Sensitive data (password)](1) is used in a hashing algorithm (MD5) that is insecure for password hashing, since it is not a computationally expensive hash function. (AI unavailable — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · javascript.lang.security.detect-child-process.detect-child-process — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\api.ts:8`
- **Why it matters:** Detected calls to child_process from a function argument `req`. This could lead to a command injection if the input is user controllable. Try to avoid calls to child_process, and if it is needed ensure user input is correctly sanitized or sandboxed.  (AI unavailable — manual review recommended)
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
- **Why it matters:** Executing non-constant commands. This can lead to command injection. You should use `escapeshellarg()` when using command. (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · python.requests.security.disabled-cert-validation.disabled-cert-validation — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\semgrep_samples.py:44`
- **Why it matters:** Certificate verification has been explicitly disabled. This permits insecure connections to insecure servers. Re-enable certification validation. (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · js/sql-injection — 1 occurrence(s) · P1
- **Scanners:** codeql
- **Where:** `security_samples/multilang/server.js:14`
- **Why it matters:** This query string depends on a [user-provided value](1). (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · py/clear-text-storage-sensitive-data — 1 occurrence(s) · P1
- **Scanners:** codeql
- **Where:** `security_samples/bandit_samples.py:58`
- **Why it matters:** This expression stores [sensitive data (password)](1) as clear text. (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · py/request-without-cert-validation — 1 occurrence(s) · P1
- **Scanners:** codeql
- **Where:** `security_samples/semgrep_samples.py:44`
- **Why it matters:** This request may run without certificate validation because [it is disabled](1). (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · hashicorp-tf-password — 1 occurrence(s) · P1
- **Scanners:** gitleaks
- **Where:** `security_samples/multilang/infra.tf:31`
- **Why it matters:** Identified a HashiCorp Terraform password field, risking unauthorized infrastructure configuration and security breaches. (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · cve-2019-10906 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/multilang/requirements.txt:0`
- **Why it matters:** python-jinja2: str.format_map allows sandbox escape (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · ds-0029 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/multilang/Dockerfile:6`
- **Why it matters:** 'apt-get' missing '--no-install-recommends' (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0080 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/multilang/infra.tf:32`
- **Why it matters:** RDS encryption has not been enabled at a DB Instance level. (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0180 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/multilang/infra.tf:33`
- **Why it matters:** RDS Publicly Accessible (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

### 📋 Other Findings — Standard Remediation (no AI)
71 lower-severity rule(s), each with standard guidance (deterministic, no LLM call):

| Severity | Rule | Count | How to fix |
|---|---|---|---|
| MEDIUM | `b608` | 4 | Possible SQL injection from string-built queries. Use parameterized queries / an ORM, never string concatenation. |
| MEDIUM | `python.lang.security.audit.eval-detected.eval-detected` | 2 | Remove `eval()`. Use explicit parsing or a whitelist dispatch instead. |
| MEDIUM | `b307` | 2 | Do not use `eval()`. Parse input explicitly (e.g. `ast.literal_eval` for literals) or dispatch on a whitelist. |
| MEDIUM | `b108` | 2 | Avoid predictable temp paths like /tmp/x. Use `tempfile.mkstemp()`/`NamedTemporaryFile`. |
| MEDIUM | `b113` | 2 | Set an explicit timeout on network requests to avoid indefinite hangs (e.g. `requests.get(..., timeout=10)`). |
| MEDIUM | `ckv_aws_23` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_24` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv2_aws_62` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv2_aws_5` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_144` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_21` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_18` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv2_aws_61` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv2_aws_6` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_20` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_145` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_docker_2` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_docker_3` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_secret_6` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `aws-0090` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `python.lang.security.insecure-hash-algorithms-md5.insecure-hash-algorithm-md5` | 1 | Replace the weak hash (MD5/SHA1) with SHA-256+ (bcrypt/Argon2 for passwords). |
| MEDIUM | `b102` | 1 | Do not use `exec()`. Refactor to call the intended function/logic directly. |
| MEDIUM | `b301` | 1 | Do not `pickle.loads()` untrusted data — it enables arbitrary code execution. Use JSON or a safe serializer. |
| MEDIUM | `b506` | 1 | Do not use `yaml.load()` without a safe loader. Use `yaml.safe_load()`. |
| MEDIUM | `python.lang.security.audit.exec-detected.exec-detected` | 1 | Remove `exec()`. Call the intended logic directly. |
| MEDIUM | `python.lang.security.deserialization.pickle.avoid-pickle` | 1 | Do not deserialize untrusted data with pickle. Use JSON or a schema-validated format. |
| MEDIUM | `go.lang.security.audit.net.use-tls.use-tls` | 1 | Review against secure-coding guidance for this rule and apply the standard fix (validate input, avoid dangerous APIs). |
| MEDIUM | `javascript.express.security.audit.xss.direct-response-write.direct-response-write` | 1 | Review against secure-coding guidance for this rule and apply the standard fix (validate input, avoid dangerous APIs). |
| MEDIUM | `ruby.lang.security.dangerous-exec.dangerous-exec` | 1 | Review against secure-coding guidance for this rule and apply the standard fix (validate input, avoid dangerous APIs). |
| MEDIUM | `ckv_aws_53` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_54` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_55` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_56` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_382` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_25` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_260` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_129` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_226` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_16` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_118` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_161` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_293` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_157` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_17` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv2_aws_60` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_docker_7` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_docker_1` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `cve-2020-28493` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2024-22195` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2024-34064` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |

_…and 21 more lower-severity rule(s)._

### 🛰️ Scanner Coverage
7/7 scanner(s) completed. A ❌ scanner ran but its result could not be collected — treat its coverage as unknown, not clean.

| Scanner | Status | Findings | Detail |
|---|---|---|---|
| bandit | ✅ ran | 540 | completed |
| semgrep | ✅ ran | 26 | completed |
| codeql | ✅ ran | 10 | completed |
| gitleaks | ✅ ran | 4 | completed |
| checkov | ✅ ran | 46 | completed |
| trivy | ✅ ran | 50 | completed |
| njsscan | ✅ ran | 0 | completed |

### Merge Confidence (advisory)
**Score:** 0.0 (advisory — human makes the final merge decision)

### Quality Gate
**Status:** failed

**Unsatisfied thresholds:**
- `max_critical_findings`: expected <= 0, actual 9
- `max_leaked_secrets`: expected <= 0, actual 7
- `max_blocking_iac_issues`: expected <= 0, actual 21
- `min_coverage_percent`: expected >= 90.0, actual 0.0

### ✅ Fixed Findings (0)
None.

### ❗ Remaining Findings (662)
- **py/command-line-injection** (CRITICAL, code) at `security_samples/multilang/vuln_app.py:23` — scanners: codeql, semgrep — Advisory — see remediation guide.
  - **AI triage:** P0
  - _This command line depends on a [user-provided value](1). (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **python.flask.security.injection.tainted-sql-string.tainted-sql-string** (HIGH, code) at `security_samples\multilang\vuln_app.py:32` — scanners: codeql, semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Detected user input used to manually construct a SQL string. This is usually bad practice because manual construction could accidentally result in a SQL injection. An attacker could use a SQL injection to steal or modify contents of the database. Instead, use a parameterized query which is available by default in most database engines. Alternatively, consider using an object-relational mapper (ORM) such as SQLAlchemy which will protect your queries. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **python.lang.security.insecure-hash-algorithms-md5.insecure-hash-algorithm-md5** (MEDIUM, code) at `security_samples\multilang\vuln_app.py:38` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Detected MD5 hash algorithm which is considered insecure. MD5 is not collision resistant and is therefore not suitable as a cryptographic signature. Use SHA256 or SHA3 instead._
  - **Suggested fix approach:** Replace the weak hash (MD5/SHA1) with SHA-256+ (bcrypt/Argon2 for passwords).
- **python.lang.security.audit.eval-detected.eval-detected** (MEDIUM, code) at `security_samples\multilang\vuln_app.py:43` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Detected the use of eval(). eval() can be dangerous if used to evaluate dynamic content. If this content can be input from outside the program, this may be a code injection vulnerability. Ensure evaluated content is not definable by external sources._
  - **Suggested fix approach:** Remove `eval()`. Use explicit parsing or a whitelist dispatch instead.
- **js/command-line-injection** (CRITICAL, code) at `security_samples/multilang/server.js:21` — scanners: codeql, semgrep — Advisory — see remediation guide.
  - **AI triage:** P0
  - _This command line depends on a [user-provided value](1). (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **js/code-injection** (CRITICAL, code) at `security_samples/multilang/server.js:26` — scanners: codeql, semgrep — Advisory — see remediation guide.
  - **AI triage:** P0
  - _This code execution depends on a [user-provided value](1). (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
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
- **b602** (HIGH, code) at `.\security_samples\bandit_samples.py:31` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _subprocess call with shell=True identified, security issue. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **b605** (HIGH, code) at `.\security_samples\bandit_samples.py:36` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Starting a process with a shell, possible injection detected, security issue. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **b324** (HIGH, code) at `.\security_samples\bandit_samples.py:51` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Use of weak MD5 hash for security. Consider usedforsecurity=False (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **b605** (HIGH, code) at `.\security_samples\codeql_taintflow.py:36` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Starting a process with a shell, possible injection detected, security issue. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **b602** (HIGH, code) at `.\security_samples\multilang\vuln_app.py:23` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _subprocess call with shell=True identified, security issue. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **b324** (HIGH, code) at `.\security_samples\multilang\vuln_app.py:38` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Use of weak MD5 hash for security. Consider usedforsecurity=False (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **b602** (HIGH, code) at `.\security_samples\semgrep_samples.py:34` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _subprocess call with shell=True identified, security issue. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **b605** (HIGH, code) at `.\security_samples\semgrep_samples.py:39` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Starting a process with a shell, possible injection detected, security issue. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **b501** (HIGH, code) at `.\security_samples\semgrep_samples.py:44` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Call to requests with verify=False disabling SSL certificate checks, security issue. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **python.lang.security.audit.subprocess-shell-true.subprocess-shell-true** (HIGH, code) at `security_samples\bandit_samples.py:31` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Found 'subprocess' function 'call' with 'shell=True'. This is dangerous because this call will spawn the command using a shell process. Doing so propagates current shell settings and variables, which makes it much easier for a malicious actor to execute commands. Use 'shell=False' instead. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **py/weak-sensitive-data-hashing** (HIGH, code) at `security_samples/bandit_samples.py:51` — scanners: codeql, semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _[Sensitive data (password)](1) is used in a hashing algorithm (MD5) that is insecure for password hashing, since it is not a computationally expensive hash function. (AI unavailable — manual review recommended)_
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
  - _Executing non-constant commands. This can lead to command injection. You should use `escapeshellarg()` when using command. (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **python.lang.security.audit.subprocess-shell-true.subprocess-shell-true** (HIGH, code) at `security_samples\semgrep_samples.py:34` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Found 'subprocess' function 'call' with 'shell=True'. This is dangerous because this call will spawn the command using a shell process. Doing so propagates current shell settings and variables, which makes it much easier for a malicious actor to execute commands. Use 'shell=False' instead. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **python.requests.security.disabled-cert-validation.disabled-cert-validation** (HIGH, code) at `security_samples\semgrep_samples.py:44` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Certificate verification has been explicitly disabled. This permits insecure connections to insecure servers. Re-enable certification validation. (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **js/sql-injection** (HIGH, code) at `security_samples/multilang/server.js:14` — scanners: codeql — Advisory — see remediation guide.
  - **AI triage:** P1
  - _This query string depends on a [user-provided value](1). (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **js/missing-rate-limiting** (HIGH, code) at `security_samples/multilang/server.js:10` — scanners: codeql — Advisory — see remediation guide.
  - **AI triage:** P1
  - _This route handler performs [a database access](1), but is not rate-limited. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **js/missing-rate-limiting** (HIGH, code) at `security_samples/multilang/server.js:19` — scanners: codeql — Advisory — see remediation guide.
  - **AI triage:** P1
  - _This route handler performs [a database access](1), but is not rate-limited. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **py/clear-text-storage-sensitive-data** (HIGH, code) at `security_samples/bandit_samples.py:58` — scanners: codeql — Advisory — see remediation guide.
  - **AI triage:** P1
  - _This expression stores [sensitive data (password)](1) as clear text. (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **py/request-without-cert-validation** (HIGH, code) at `security_samples/semgrep_samples.py:44` — scanners: codeql — Advisory — see remediation guide.
  - **AI triage:** P1
  - _This request may run without certificate validation because [it is disabled](1). (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **generic-api-key** (HIGH, secret) at `security_samples/multilang/leaked_creds.env:11` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Detected a Generic API Key, potentially exposing access to various services and sensitive operations. (AI unavailable — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **hashicorp-tf-password** (HIGH, secret) at `security_samples/multilang/infra.tf:31` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Identified a HashiCorp Terraform password field, risking unauthorized infrastructure configuration and security breaches. (beyond AI call budget — manual review recommended)_
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
  - _python-jinja2: str.format_map allows sandbox escape (beyond AI call budget — manual review recommended)_
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
  - _'apt-get' missing '--no-install-recommends' (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- _…and 612 more (showing the 50 highest-risk findings; see the severity breakdown above for the full distribution)._

_The final merge decision is left to a human reviewer; this report is advisory and does not trigger a merge._
