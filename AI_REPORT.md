# AI Software Delivery Engineer: Architecture Review

**Repository:** kuchurisatwik/DeliveryOS
**Commit SHA:** c9cbb25d74f0556fbfcb123958feacd921f394bc
**Branch:** ai-sde/review-c9cbb25-20260727104448
**Timestamp:** 2026-07-27T10:46:13.443332Z

No AI analysis was generated.

---
## 🔒 Security Pipeline Report
**Commit:** [`c9cbb25d74`](https://github.com/kuchurisatwik/DeliveryOS/commit/c9cbb25d74f0556fbfcb123958feacd921f394bc)
**Repository:** `kuchurisatwik/DeliveryOS`
**Branch under review:** `main`
**Security Summary:** 0 finding(s) fixed; 658 finding(s) remaining; quality gate failed; incomplete scanner coverage: semgrep, codeql, gitleaks.
**Scanned scope:** whole repository (full audit mode).

**Findings by severity:** CRITICAL: 10, HIGH: 30, MEDIUM: 71, LOW: 547

### 🛠️ Remediation Guide — Key High/Critical Findings
The 22 highest-severity rule(s) below account for the key risk in this change. Each fix applies to all listed occurrences. CRITICAL rules include a concrete patch; HIGH rules include an illustrative before/after.

#### CRITICAL · aws-access-key-id — 6 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `-:28, -:29, -:88, -:89, security_samples/gitleaks_secrets.txt:7` (+1 more)
- **Why it matters:** Exposing AWS Access Key IDs can lead to unauthorized access to your AWS resources, potentially resulting in data breaches or financial loss.
- **How to fix:** Remove any hard-coded AWS Access Key IDs from code and use environment variables or AWS IAM roles to access AWS services securely.
- **Suggested patch:**
  ```diff
  --- app/frontend/routes.py
  +++ app/frontend/routes.py
  @@ -20,6 +20,8 @@
   import json
   import os
   import subprocess
   
  +import secrets
  +
   class ConfigUpdate:
       # Implementation details
   
   class ScanIn:
  @@ -50,7 +52,7 @@
       def add_repo(self, repo_data):
           # Existing code for adding repo
           if 'aws_access_key_id' in repo_data:
  -            return repo_data['aws_access_key_id']
  +            return secrets.token_hex(16)  # Replace with a dummy token
   
       # Other existing methods
  ```

#### CRITICAL · cve-2019-20477 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/multilang/requirements.txt:0`
- **Why it matters:** The vulnerability in PyYAML allows attackers to execute arbitrary commands through the insecure use of the FullLoader, posing a significant security risk.
- **How to fix:** Upgrade PyYAML to a secure version that does not use the FullLoader or switch to a safer parser like safe_load.
- **Suggested patch:**
  ```diff
  --- security_samples/multilang/requirements.txt
  +++ security_samples/multilang/requirements.txt
  @@ -1 +1 @@
  -PyYAML
  +PyYAML>=5.3.1
  ```

#### CRITICAL · cve-2020-14343 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/multilang/requirements.txt:0`
- **Why it matters:** This vulnerability reflects an incomplete fix in PyYAML, which can still lead to command execution vulnerabilities in certain scenarios.
- **How to fix:** Ensure that PyYAML is updated to the latest version to mitigate the identified vulnerability.
- **Suggested patch:**
  ```diff
  --- security_samples/multilang/requirements.txt
  +++ security_samples/multilang/requirements.txt
  @@ -1,1 +1,1 @@
  -PyYAML==5.3.1
  +PyYAML==5.4.1
  ```

#### CRITICAL · aws-0104 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:37`
- **Why it matters:** Allowing unrestricted egress from a security group can expose your system to unwanted internet exposure and potential data exfiltration.
- **How to fix:** Restrict the egress rules to specific IP addresses or CIDR ranges to minimize exposure.
- **Suggested patch:**
  ```diff
  --- security_samples/insecure_terraform.tf
  +++ security_samples/insecure_terraform.tf
  @@ -34,7 +34,7 @@
     }
     ingress {
       from_port   = 80
       to_port     = 80
       protocol    = "tcp"
  -    cidr_blocks  = ["0.0.0.0/0"]
  +    cidr_blocks  = ["<YOUR_RESTRICTED_IP_RANGE>"]
     }
     egress {
       from_port   = 0
       to_port     = 0
       protocol    = "-"
  -    cidr_blocks  = ["0.0.0.0/0"]
  +    cidr_blocks  = ["<YOUR_RESTRICTED_IP_RANGE>"]
     }
   }
  ```

#### CRITICAL · ds-0031 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/multilang/Dockerfile:9`
- **Why it matters:** Passing secrets through build arguments or environment variables can inadvertently expose sensitive information in logs or error messages.
- **How to fix:** Use Docker secrets or a secure vault service to manage sensitive information securely instead of passing them as environment variables.
- **Suggested patch:**
  ```diff
  --- security_samples/multilang/Dockerfile	2023-10-01 12:00:00.000000000 +0000
  +++ security_samples/multilang/Dockerfile	2023-10-01 12:00:00.000000000 +0000
  @@ -6,7 +6,7 @@
   ARG MY_SECRET_ARG
   
   RUN echo "Using secret: $MY_SECRET_ARG" > secret.txt
   RUN ./some_setup_script.sh --secret="${MY_SECRET_ARG}"
   
  -# Make sure to not expose secrets
  +# Make sure to use secure storage for secrets
   RUN rm secret.txt
  ```

#### HIGH · b602 — 3 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `./security_samples/bandit_samples.py:31, ./security_samples/multilang/vuln_app.py:23, ./security_samples/semgrep_samples.py:34`
- **Why it matters:** Using subprocess calls with shell=True can lead to command injection vulnerabilities if untrusted input is passed to the command.
- **How to fix:** Replace subprocess calls using shell=True with a list of arguments or use a safer alternative.
- **Example fix (illustrative):**
  ```diff
  - subprocess.call('ls -l', shell=True)
  + subprocess.call(['ls', '-l'])
  ```

#### HIGH · b605 — 3 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `./security_samples/bandit_samples.py:36, ./security_samples/codeql_taintflow.py:36, ./security_samples/semgrep_samples.py:39`
- **Why it matters:** Starting a process with the shell can expose the application to injection attacks when variables are included in the command.
- **How to fix:** Avoid using shell=True and pass arguments as a list to subprocess calls. Validate any user input used in these commands.
- **Example fix (illustrative):**
  ```diff
  - subprocess.run('echo ' + user_input, shell=True)
  + subprocess.run(['echo', user_input])
  ```

#### HIGH · b324 — 2 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `./security_samples/bandit_samples.py:51, ./security_samples/multilang/vuln_app.py:38`
- **Why it matters:** MD5 is considered a weak hash function and should not be used for security purposes as it is vulnerable to collisions.
- **How to fix:** Use a stronger hash function like SHA-256 for secure hashing in your application.
- **Example fix (illustrative):**
  ```diff
  - hashlib.md5(data).hexdigest()
  + hashlib.sha256(data).hexdigest()
  ```

#### HIGH · ds-0002 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/Dockerfile:0, security_samples/multilang/Dockerfile:0`
- **Why it matters:** Running containers as the root user can lead to privilege escalation on the host system.
- **How to fix:** Specify a non-root user in your Dockerfile to reduce security risks.
- **Example fix (illustrative):**
  ```diff
  - FROM python:3.9 
  - USER root
  + FROM python:3.9 
  + USER appuser
  ```

#### HIGH · aws-0086 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:14, security_samples/multilang/infra.tf:19`
- **Why it matters:** S3 buckets that allow public access can lead to data leaks and unauthorized access to sensitive information.
- **How to fix:** Ensure that the S3 bucket is configured to block public ACLs and review bucket policies regularly.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_s3_bucket" "example" { 
  -   acl = "public-read" 
  - }
  + resource "aws_s3_bucket" "example" { 
  +   acl = "private" 
  + }
  ```

#### HIGH · aws-0087 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:15, security_samples/multilang/infra.tf:19`
- **Why it matters:** Having an S3 bucket with public access policies can lead to unauthorized data exposure.
- **How to fix:** Ensure that S3 bucket policies explicitly block public access to prevent any potential data leaks.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_s3_bucket" "example" {
  -   bucket = "example-bucket"
  -   acl    = "public-read"
  - }
  + resource "aws_s3_bucket" "example" {
  +   bucket = "example-bucket"
  +   acl    = "private"
  +   block_public_acls = true
  +   ignore_public_acls = true
  + }
  ```

#### HIGH · aws-0091 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:16, security_samples/multilang/infra.tf:19`
- **Why it matters:** Ignoring public ACLs is essential to prevent unwanted public access to sensitive data stored in S3 buckets.
- **How to fix:** Configure your S3 buckets to ignore any public ACLs to ensure that even if they are set, they are not applied.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_s3_bucket" "example" {
  -   bucket = "example-bucket"
  -   acl    = "private"
  - }
  + resource "aws_s3_bucket" "example" {
  +   bucket = "example-bucket"
  +   acl    = "private"
  +   ignore_public_acls = true
  + }
  ```

#### HIGH · aws-0092 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:8, security_samples/multilang/infra.tf:21`
- **Why it matters:** S3 buckets that are publicly accessible through ACLs can lead to significant security risks and data leaks.
- **How to fix:** Adopt stricter ACL configurations or security policies to ensure your S3 buckets are not publicly accessible.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_s3_bucket" "example" {
  -   bucket = "example-bucket"
  -   acl    = "public-read"
  - }
  + resource "aws_s3_bucket" "example" {
  +   bucket = "example-bucket"
  +   acl    = "private"
  + }
  ```

#### HIGH · aws-0093 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:17, security_samples/multilang/infra.tf:19`
- **Why it matters:** Allowing public access to S3 buckets can enable unwanted access and potential data breaches.
- **How to fix:** Restrict access to S3 buckets based on least privilege to limit exposure to only necessary entities.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_s3_bucket_policy" "example" {
  -   bucket = aws_s3_bucket.example.bucket
  -   policy = jsonencode({
  -     Version = "2012-10-17"
  -     Statement = [
  -       {
  -         Effect = "Allow"
  -         Principal = "*"
  -         Action = "s3:GetObject"
  -         Resource = "${aws_s3_bucket.example.arn}/*"
  -       }
  -     ]
  -   })
  - }
  + resource "aws_s3_bucket_policy" "example" {
  +   bucket = aws_s3_bucket.example.bucket
  +   policy = jsonencode({
  +     Version = "2012-10-17"
  +     Statement = [
  +       {
  +         Effect = "Deny"
  +         Principal = "*"
  +         Action = "s3:GetObject"
  +         Resource = "${aws_s3_bucket.example.arn}/*"
  +         Condition = {"Bool":{"aws:SecureTransport":"false"}}
  +       }
  +     ]
  +   })
  + }
  ```

#### HIGH · aws-0107 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:29, security_samples/multilang/infra.tf:14`
- **Why it matters:** Security groups with unrestricted ingress for SSH or RDP expose services to brute-force attacks and unauthorized access.
- **How to fix:** Restrict ingress rules to specific trusted IP addresses or ranges to minimize risk of unauthorized access.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_security_group" "allow_ssh" {
  -   ingress {
  -     from_port   = 22
  -     to_port     = 22
  -     protocol    = "tcp"
  -     cidr_blocks = ["0.0.0.0/0"]
  -   }
  - }
  + resource "aws_security_group" "allow_ssh" {
  +   ingress {
  +     from_port   = 22
  +     to_port     = 22
  +     protocol    = "tcp"
  +     cidr_blocks = ["192.168.1.1/32"] // Replace with your IP
  +   }
  + }
  ```

#### HIGH · aws-0132 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:5, security_samples/multilang/infra.tf:19`
- **Why it matters:** Using Customer Managed Keys for S3 encryption ensures that you maintain control over the encryption keys, reducing the risk of unauthorized data access.
- **How to fix:** Update your S3 bucket configuration to use Customer Managed Keys for encryption by specifying the KMS key ID.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_s3_bucket" "my_bucket" {
  -   bucket = "my-secure-bucket"
  -   acl    = "private"
  - }
  + resource "aws_s3_bucket" "my_bucket" {
  +   bucket = "my-secure-bucket"
  +   acl    = "private"
  +   server_side_encryption_configuration {
  +     rule {
  +       apply_server_side_encryption_by_default {
  +         sse_algorithm = "aws:kms"
  +         kms_master_key_id = aws_kms_key.my_key.id
  +       }
  +     }
  +   }
  + }
  ```

#### HIGH · b501 — 1 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `./security_samples/semgrep_samples.py:44`
- **Why it matters:** Setting 'verify=False' in the requests library disables SSL certificate checks, making the application vulnerable to man-in-the-middle attacks.
- **How to fix:** Always set 'verify' to True or provide a valid certificate path to ensure SSL certificate verification.
- **Example fix (illustrative):**
  ```diff
  - response = requests.get('https://example.com', verify=False)
  + response = requests.get('https://example.com', verify=True)
  ```

#### HIGH · cve-2019-10906 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/multilang/requirements.txt:0`
- **Why it matters:** The vulnerability in python-jinja2 allows for code execution through str.format_map, which could lead to remote code execution if user input is not properly sanitized.
- **How to fix:** Upgrade to a version of Jinja2 where this vulnerability has been patched and avoid using str.format_map with untrusted user input.
- **Example fix (illustrative):**
  ```diff
  - output = template.format_map(user_input)
  + output = template.render(safe_user_input)
  ```

#### HIGH · ds-0029 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/multilang/Dockerfile:6`
- **Why it matters:** Using 'apt-get' without the '--no-install-recommends' flag can lead to the installation of unnecessary packages, potentially increasing the attack surface of the application.
- **How to fix:** Always use '--no-install-recommends' with 'apt-get' to limit installed packages to only those explicitly specified.
- **Example fix (illustrative):**
  ```diff
  - RUN apt-get update && apt-get install -y mypackage
  + RUN apt-get update && apt-get install --no-install-recommends -y mypackage
  ```

#### HIGH · aws-0080 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/multilang/infra.tf:32`
- **Why it matters:** Not enabling RDS encryption at the DB Instance level exposes sensitive data, putting it at risk in the event of a data breach.
- **How to fix:** Ensure RDS instances are created with encryption enabled by specifying the 'storage_encrypted' attribute and providing a KMS key.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_db_instance" "mydb" {
  -   allocated_storage = 20
  -   instance_class = "db.t2.micro"
  -   engine = "mysql"
  - }
  + resource "aws_db_instance" "mydb" {
  +   allocated_storage = 20
  +   instance_class = "db.t2.micro"
  +   engine = "mysql"
  +   storage_encrypted = true
  +   kms_key_id = aws_kms_key.my_key.id
  + }
  ```

#### HIGH · aws-0180 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/multilang/infra.tf:33`
- **Why it matters:** Having an RDS instance publicly accessible exposes your database to the internet, increasing the risk of unauthorized access and data breaches.
- **How to fix:** Set the 'Publicly Accessible' option to 'false' in your RDS instance configuration to restrict access only to necessary IP addresses.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_db_instance" "example" { 
  -   allocated_storage = 20 
  -   engine = "mysql" 
  -   username = "foo" 
  -   password = "bar" 
  -   publicly_accessible = true 
  - }
  + resource "aws_db_instance" "example" { 
  +   allocated_storage = 20 
  +   engine = "mysql" 
  +   username = "foo" 
  +   password = "bar" 
  +   publicly_accessible = false 
  + }
  ```

#### HIGH · private-key — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/gitleaks_secrets.txt:18`
- **Why it matters:** Exposing asymmetric private keys can lead to unauthorized decryption of sensitive data and compromise of secure communications.
- **How to fix:** Remove the private key from version control and store it securely, using environment variables or a secure secrets management tool.
- **Example fix (illustrative):**
  ```diff
  - PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...
  - -----END RSA PRIVATE KEY-----"
  + # Store private key in a secure location, e.g., environment variable or secrets manager
  + PRIVATE_KEY=$(cat /path/to/secure/location/private_key.pem)
  ```

### 📋 Other Findings — Standard Remediation (no AI)
64 lower-severity rule(s), each with standard guidance (deterministic, no LLM call):

| Severity | Rule | Count | How to fix |
|---|---|---|---|
| MEDIUM | `b608` | 4 | Possible SQL injection from string-built queries. Use parameterized queries / an ORM, never string concatenation. |
| MEDIUM | `b307` | 2 | Do not use `eval()`. Parse input explicitly (e.g. `ast.literal_eval` for literals) or dispatch on a whitelist. |
| MEDIUM | `b108` | 2 | Avoid predictable temp paths like /tmp/x. Use `tempfile.mkstemp()`/`NamedTemporaryFile`. |
| MEDIUM | `b113` | 2 | Set an explicit timeout on network requests to avoid indefinite hangs (e.g. `requests.get(..., timeout=10)`). |
| MEDIUM | `ckv_aws_24` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_23` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv2_aws_62` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv2_aws_5` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_21` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_145` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_20` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv2_aws_61` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_144` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv2_aws_6` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_18` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_docker_3` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_docker_2` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_secret_6` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `aws-0090` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `b102` | 1 | Do not use `exec()`. Refactor to call the intended function/logic directly. |
| MEDIUM | `b301` | 1 | Do not `pickle.loads()` untrusted data — it enables arbitrary code execution. Use JSON or a safe serializer. |
| MEDIUM | `b506` | 1 | Do not use `yaml.load()` without a safe loader. Use `yaml.safe_load()`. |
| MEDIUM | `ckv_aws_56` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_53` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_55` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_54` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_260` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_25` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_16` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_293` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_157` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_17` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_161` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_118` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_354` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_129` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_226` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv2_aws_60` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_docker_7` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_docker_1` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
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

_…and 14 more lower-severity rule(s)._

### 🛰️ Scanner Coverage
4/7 scanner(s) completed. A ❌ scanner ran but its result could not be collected — treat its coverage as unknown, not clean.

| Scanner | Status | Findings | Detail |
|---|---|---|---|
| bandit | ✅ ran | 563 | completed |
| semgrep | ❌ failed | — | empty output; tool produced no report: Traceback (most recent call last): |
| codeql | ❌ failed | — | all language analyses failed — javascript: tool not installed: 'codeql' not found on PATH; python: tool not installed: 'codeql' not found on PATH; ruby: tool not installed: 'codeql' not found on PATH |
| gitleaks | ❌ failed | — | empty output; tool produced no report: ○ |
| checkov | ✅ ran | 46 | completed |
| trivy | ✅ ran | 54 | completed |
| njsscan | ✅ ran | 0 | completed |

### Merge Confidence (advisory)
**Score:** 0.0 (advisory — human makes the final merge decision)

### Quality Gate
**Status:** failed

**Unsatisfied thresholds:**
- `max_critical_findings`: expected <= 0, actual 10
- `max_leaked_secrets`: expected <= 0, actual 7
- `max_blocking_iac_issues`: expected <= 0, actual 21
- `min_coverage_percent`: expected >= 90.0, actual 0.0

### ✅ Fixed Findings (0)
None.

### ❗ Remaining Findings (658)
- **cve-2019-20477** (CRITICAL, dependency) at `security_samples/multilang/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _The vulnerability in PyYAML allows attackers to execute arbitrary commands through the insecure use of the FullLoader, posing a significant security risk._
  - **Suggested fix approach:** Upgrade PyYAML to a secure version that does not use the FullLoader or switch to a safer parser like safe_load.
  - **Suggested change:**
    ```diff
    --- security_samples/multilang/requirements.txt
    +++ security_samples/multilang/requirements.txt
    @@ -1 +1 @@
    -PyYAML
    +PyYAML>=5.3.1
    ```
- **cve-2020-14343** (CRITICAL, dependency) at `security_samples/multilang/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _This vulnerability reflects an incomplete fix in PyYAML, which can still lead to command execution vulnerabilities in certain scenarios._
  - **Suggested fix approach:** Ensure that PyYAML is updated to the latest version to mitigate the identified vulnerability.
  - **Suggested change:**
    ```diff
    --- security_samples/multilang/requirements.txt
    +++ security_samples/multilang/requirements.txt
    @@ -1,1 +1,1 @@
    -PyYAML==5.3.1
    +PyYAML==5.4.1
    ```
- **aws-0104** (CRITICAL, iac) at `security_samples/insecure_terraform.tf:37` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Allowing unrestricted egress from a security group can expose your system to unwanted internet exposure and potential data exfiltration._
  - **Suggested fix approach:** Restrict the egress rules to specific IP addresses or CIDR ranges to minimize exposure.
  - **Suggested change:**
    ```diff
    --- security_samples/insecure_terraform.tf
    +++ security_samples/insecure_terraform.tf
    @@ -34,7 +34,7 @@
       }
       ingress {
         from_port   = 80
         to_port     = 80
         protocol    = "tcp"
    -    cidr_blocks  = ["0.0.0.0/0"]
    +    cidr_blocks  = ["<YOUR_RESTRICTED_IP_RANGE>"]
       }
       egress {
         from_port   = 0
         to_port     = 0
         protocol    = "-"
    -    cidr_blocks  = ["0.0.0.0/0"]
    +    cidr_blocks  = ["<YOUR_RESTRICTED_IP_RANGE>"]
       }
     }
    ```
- **ds-0031** (CRITICAL, iac) at `security_samples/multilang/Dockerfile:9` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Passing secrets through build arguments or environment variables can inadvertently expose sensitive information in logs or error messages._
  - **Suggested fix approach:** Use Docker secrets or a secure vault service to manage sensitive information securely instead of passing them as environment variables.
  - **Suggested change:**
    ```diff
    --- security_samples/multilang/Dockerfile	2023-10-01 12:00:00.000000000 +0000
    +++ security_samples/multilang/Dockerfile	2023-10-01 12:00:00.000000000 +0000
    @@ -6,7 +6,7 @@
     ARG MY_SECRET_ARG
     
     RUN echo "Using secret: $MY_SECRET_ARG" > secret.txt
     RUN ./some_setup_script.sh --secret="${MY_SECRET_ARG}"
     
    -# Make sure to not expose secrets
    +# Make sure to use secure storage for secrets
     RUN rm secret.txt
    ```
- **aws-access-key-id** (CRITICAL, secret) at `-:28` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Exposing AWS Access Key IDs can lead to unauthorized access to your AWS resources, potentially resulting in data breaches or financial loss._
  - **Suggested fix approach:** Remove any hard-coded AWS Access Key IDs from code and use environment variables or AWS IAM roles to access AWS services securely.
  - **Suggested change:**
    ```diff
    --- app/frontend/routes.py
    +++ app/frontend/routes.py
    @@ -20,6 +20,8 @@
     import json
     import os
     import subprocess
     
    +import secrets
    +
     class ConfigUpdate:
         # Implementation details
     
     class ScanIn:
    @@ -50,7 +52,7 @@
         def add_repo(self, repo_data):
             # Existing code for adding repo
             if 'aws_access_key_id' in repo_data:
    -            return repo_data['aws_access_key_id']
    +            return secrets.token_hex(16)  # Replace with a dummy token
     
         # Other existing methods
    ```
- **aws-access-key-id** (CRITICAL, secret) at `-:29` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Exposing AWS Access Key IDs can lead to unauthorized access to your AWS resources, potentially resulting in data breaches or financial loss._
  - **Suggested fix approach:** Remove any hard-coded AWS Access Key IDs from code and use environment variables or AWS IAM roles to access AWS services securely.
- **aws-access-key-id** (CRITICAL, secret) at `-:88` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Exposing AWS Access Key IDs can lead to unauthorized access to your AWS resources, potentially resulting in data breaches or financial loss._
  - **Suggested fix approach:** Remove any hard-coded AWS Access Key IDs from code and use environment variables or AWS IAM roles to access AWS services securely.
- **aws-access-key-id** (CRITICAL, secret) at `-:89` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Exposing AWS Access Key IDs can lead to unauthorized access to your AWS resources, potentially resulting in data breaches or financial loss._
  - **Suggested fix approach:** Remove any hard-coded AWS Access Key IDs from code and use environment variables or AWS IAM roles to access AWS services securely.
- **aws-access-key-id** (CRITICAL, secret) at `security_samples/gitleaks_secrets.txt:7` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Exposing AWS Access Key IDs can lead to unauthorized access to your AWS resources, potentially resulting in data breaches or financial loss._
  - **Suggested fix approach:** Remove any hard-coded AWS Access Key IDs from code and use environment variables or AWS IAM roles to access AWS services securely.
- **aws-access-key-id** (CRITICAL, secret) at `security_samples/multilang/leaked_creds.env:7` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Exposing AWS Access Key IDs can lead to unauthorized access to your AWS resources, potentially resulting in data breaches or financial loss._
  - **Suggested fix approach:** Remove any hard-coded AWS Access Key IDs from code and use environment variables or AWS IAM roles to access AWS services securely.
- **b602** (HIGH, code) at `./security_samples/bandit_samples.py:31` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using subprocess calls with shell=True can lead to command injection vulnerabilities if untrusted input is passed to the command._
  - **Suggested fix approach:** Replace subprocess calls using shell=True with a list of arguments or use a safer alternative.
- **b605** (HIGH, code) at `./security_samples/bandit_samples.py:36` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Starting a process with the shell can expose the application to injection attacks when variables are included in the command._
  - **Suggested fix approach:** Avoid using shell=True and pass arguments as a list to subprocess calls. Validate any user input used in these commands.
- **b324** (HIGH, code) at `./security_samples/bandit_samples.py:51` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _MD5 is considered a weak hash function and should not be used for security purposes as it is vulnerable to collisions._
  - **Suggested fix approach:** Use a stronger hash function like SHA-256 for secure hashing in your application.
- **b605** (HIGH, code) at `./security_samples/codeql_taintflow.py:36` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Starting a process with the shell can expose the application to injection attacks when variables are included in the command._
  - **Suggested fix approach:** Avoid using shell=True and pass arguments as a list to subprocess calls. Validate any user input used in these commands.
- **b602** (HIGH, code) at `./security_samples/multilang/vuln_app.py:23` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using subprocess calls with shell=True can lead to command injection vulnerabilities if untrusted input is passed to the command._
  - **Suggested fix approach:** Replace subprocess calls using shell=True with a list of arguments or use a safer alternative.
- **b324** (HIGH, code) at `./security_samples/multilang/vuln_app.py:38` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _MD5 is considered a weak hash function and should not be used for security purposes as it is vulnerable to collisions._
  - **Suggested fix approach:** Use a stronger hash function like SHA-256 for secure hashing in your application.
- **b602** (HIGH, code) at `./security_samples/semgrep_samples.py:34` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using subprocess calls with shell=True can lead to command injection vulnerabilities if untrusted input is passed to the command._
  - **Suggested fix approach:** Replace subprocess calls using shell=True with a list of arguments or use a safer alternative.
- **b605** (HIGH, code) at `./security_samples/semgrep_samples.py:39` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Starting a process with the shell can expose the application to injection attacks when variables are included in the command._
  - **Suggested fix approach:** Avoid using shell=True and pass arguments as a list to subprocess calls. Validate any user input used in these commands.
- **b501** (HIGH, code) at `./security_samples/semgrep_samples.py:44` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Setting 'verify=False' in the requests library disables SSL certificate checks, making the application vulnerable to man-in-the-middle attacks._
  - **Suggested fix approach:** Always set 'verify' to True or provide a valid certificate path to ensure SSL certificate verification.
- **cve-2019-10906** (HIGH, dependency) at `security_samples/multilang/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _The vulnerability in python-jinja2 allows for code execution through str.format_map, which could lead to remote code execution if user input is not properly sanitized._
  - **Suggested fix approach:** Upgrade to a version of Jinja2 where this vulnerability has been patched and avoid using str.format_map with untrusted user input.
- **ds-0002** (HIGH, iac) at `security_samples/Dockerfile:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Running containers as the root user can lead to privilege escalation on the host system._
  - **Suggested fix approach:** Specify a non-root user in your Dockerfile to reduce security risks.
- **aws-0086** (HIGH, iac) at `security_samples/insecure_terraform.tf:14` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 buckets that allow public access can lead to data leaks and unauthorized access to sensitive information._
  - **Suggested fix approach:** Ensure that the S3 bucket is configured to block public ACLs and review bucket policies regularly.
- **aws-0087** (HIGH, iac) at `security_samples/insecure_terraform.tf:15` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Having an S3 bucket with public access policies can lead to unauthorized data exposure._
  - **Suggested fix approach:** Ensure that S3 bucket policies explicitly block public access to prevent any potential data leaks.
- **aws-0091** (HIGH, iac) at `security_samples/insecure_terraform.tf:16` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Ignoring public ACLs is essential to prevent unwanted public access to sensitive data stored in S3 buckets._
  - **Suggested fix approach:** Configure your S3 buckets to ignore any public ACLs to ensure that even if they are set, they are not applied.
- **aws-0092** (HIGH, iac) at `security_samples/insecure_terraform.tf:8` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 buckets that are publicly accessible through ACLs can lead to significant security risks and data leaks._
  - **Suggested fix approach:** Adopt stricter ACL configurations or security policies to ensure your S3 buckets are not publicly accessible.
- **aws-0093** (HIGH, iac) at `security_samples/insecure_terraform.tf:17` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Allowing public access to S3 buckets can enable unwanted access and potential data breaches._
  - **Suggested fix approach:** Restrict access to S3 buckets based on least privilege to limit exposure to only necessary entities.
- **aws-0107** (HIGH, iac) at `security_samples/insecure_terraform.tf:29` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Security groups with unrestricted ingress for SSH or RDP expose services to brute-force attacks and unauthorized access._
  - **Suggested fix approach:** Restrict ingress rules to specific trusted IP addresses or ranges to minimize risk of unauthorized access.
- **aws-0132** (HIGH, iac) at `security_samples/insecure_terraform.tf:5` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using Customer Managed Keys for S3 encryption ensures that you maintain control over the encryption keys, reducing the risk of unauthorized data access._
  - **Suggested fix approach:** Update your S3 bucket configuration to use Customer Managed Keys for encryption by specifying the KMS key ID.
- **ds-0002** (HIGH, iac) at `security_samples/multilang/Dockerfile:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Running containers as the root user can lead to privilege escalation on the host system._
  - **Suggested fix approach:** Specify a non-root user in your Dockerfile to reduce security risks.
- **ds-0029** (HIGH, iac) at `security_samples/multilang/Dockerfile:6` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using 'apt-get' without the '--no-install-recommends' flag can lead to the installation of unnecessary packages, potentially increasing the attack surface of the application._
  - **Suggested fix approach:** Always use '--no-install-recommends' with 'apt-get' to limit installed packages to only those explicitly specified.
- **aws-0080** (HIGH, iac) at `security_samples/multilang/infra.tf:32` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Not enabling RDS encryption at the DB Instance level exposes sensitive data, putting it at risk in the event of a data breach._
  - **Suggested fix approach:** Ensure RDS instances are created with encryption enabled by specifying the 'storage_encrypted' attribute and providing a KMS key.
- **aws-0086** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 buckets that allow public access can lead to data leaks and unauthorized access to sensitive information._
  - **Suggested fix approach:** Ensure that the S3 bucket is configured to block public ACLs and review bucket policies regularly.
- **aws-0087** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Having an S3 bucket with public access policies can lead to unauthorized data exposure._
  - **Suggested fix approach:** Ensure that S3 bucket policies explicitly block public access to prevent any potential data leaks.
- **aws-0091** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Ignoring public ACLs is essential to prevent unwanted public access to sensitive data stored in S3 buckets._
  - **Suggested fix approach:** Configure your S3 buckets to ignore any public ACLs to ensure that even if they are set, they are not applied.
- **aws-0092** (HIGH, iac) at `security_samples/multilang/infra.tf:21` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 buckets that are publicly accessible through ACLs can lead to significant security risks and data leaks._
  - **Suggested fix approach:** Adopt stricter ACL configurations or security policies to ensure your S3 buckets are not publicly accessible.
- **aws-0093** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Allowing public access to S3 buckets can enable unwanted access and potential data breaches._
  - **Suggested fix approach:** Restrict access to S3 buckets based on least privilege to limit exposure to only necessary entities.
- **aws-0107** (HIGH, iac) at `security_samples/multilang/infra.tf:14` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Security groups with unrestricted ingress for SSH or RDP expose services to brute-force attacks and unauthorized access._
  - **Suggested fix approach:** Restrict ingress rules to specific trusted IP addresses or ranges to minimize risk of unauthorized access.
- **aws-0132** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using Customer Managed Keys for S3 encryption ensures that you maintain control over the encryption keys, reducing the risk of unauthorized data access._
  - **Suggested fix approach:** Update your S3 bucket configuration to use Customer Managed Keys for encryption by specifying the KMS key ID.
- **aws-0180** (HIGH, iac) at `security_samples/multilang/infra.tf:33` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Having an RDS instance publicly accessible exposes your database to the internet, increasing the risk of unauthorized access and data breaches._
  - **Suggested fix approach:** Set the 'Publicly Accessible' option to 'false' in your RDS instance configuration to restrict access only to necessary IP addresses.
- **private-key** (HIGH, secret) at `security_samples/gitleaks_secrets.txt:18` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Exposing asymmetric private keys can lead to unauthorized decryption of sensitive data and compromise of secure communications._
  - **Suggested fix approach:** Remove the private key from version control and store it securely, using environment variables or a secure secrets management tool.
- **b307** (MEDIUM, code) at `./security_samples/bandit_samples.py:21` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Use of possibly insecure function - consider using safer ast.literal_eval._
  - **Suggested fix approach:** Do not use `eval()`. Parse input explicitly (e.g. `ast.literal_eval` for literals) or dispatch on a whitelist.
- **b102** (MEDIUM, code) at `./security_samples/bandit_samples.py:26` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Use of exec detected._
  - **Suggested fix approach:** Do not use `exec()`. Refactor to call the intended function/logic directly.
- **b301** (MEDIUM, code) at `./security_samples/bandit_samples.py:41` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Pickle and modules that wrap it can be unsafe when used to deserialize untrusted data, possible security issue._
  - **Suggested fix approach:** Do not `pickle.loads()` untrusted data — it enables arbitrary code execution. Use JSON or a safe serializer.
- **b506** (MEDIUM, code) at `./security_samples/bandit_samples.py:46` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Use of unsafe yaml load. Allows instantiation of arbitrary objects. Consider yaml.safe_load()._
  - **Suggested fix approach:** Do not use `yaml.load()` without a safe loader. Use `yaml.safe_load()`.
- **b108** (MEDIUM, code) at `./security_samples/bandit_samples.py:56` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Probable insecure usage of temp file/directory._
  - **Suggested fix approach:** Avoid predictable temp paths like /tmp/x. Use `tempfile.mkstemp()`/`NamedTemporaryFile`.
- **b608** (MEDIUM, code) at `./security_samples/codeql_taintflow.py:27` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Possible SQL injection vector through string-based query construction._
  - **Suggested fix approach:** Possible SQL injection from string-built queries. Use parameterized queries / an ORM, never string concatenation.
- **b608** (MEDIUM, code) at `./security_samples/multilang/vuln_app.py:32` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Possible SQL injection vector through string-based query construction._
  - **Suggested fix approach:** Possible SQL injection from string-built queries. Use parameterized queries / an ORM, never string concatenation.
- **b307** (MEDIUM, code) at `./security_samples/multilang/vuln_app.py:43` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Use of possibly insecure function - consider using safer ast.literal_eval._
  - **Suggested fix approach:** Do not use `eval()`. Parse input explicitly (e.g. `ast.literal_eval` for literals) or dispatch on a whitelist.
- **b608** (MEDIUM, code) at `./security_samples/semgrep_samples.py:19` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Possible SQL injection vector through string-based query construction._
  - **Suggested fix approach:** Possible SQL injection from string-built queries. Use parameterized queries / an ORM, never string concatenation.
- **b608** (MEDIUM, code) at `./security_samples/semgrep_samples.py:28` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Possible SQL injection vector through string-based query construction._
  - **Suggested fix approach:** Possible SQL injection from string-built queries. Use parameterized queries / an ORM, never string concatenation.
- _…and 608 more (showing the 50 highest-risk findings; see the severity breakdown above for the full distribution)._

_The final merge decision is left to a human reviewer; this report is advisory and does not trigger a merge._
