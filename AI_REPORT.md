# AI Software Delivery Engineer: Architecture Review

**Repository:** kuchurisatwik/DeliveryOS
**Commit SHA:** c9cbb25d74f0556fbfcb123958feacd921f394bc
**Branch:** ai-sde/review-c9cbb25-20260727115152
**Timestamp:** 2026-07-27T11:53:17.311221Z

No AI analysis was generated.

---
## 🔒 Security Pipeline Report
**Commit:** [`c9cbb25d74`](https://github.com/kuchurisatwik/DeliveryOS/commit/c9cbb25d74f0556fbfcb123958feacd921f394bc)
**Repository:** `kuchurisatwik/DeliveryOS`
**Branch under review:** `main`
**Security Summary:** 0 finding(s) fixed; 658 finding(s) remaining; quality gate failed; incomplete scanner coverage: semgrep, codeql.
**Scanned scope:** whole repository (full audit mode).

**Findings by severity:** CRITICAL: 6, HIGH: 34, MEDIUM: 71, LOW: 547

### 🛠️ Remediation Guide — Key High/Critical Findings
The 24 highest-severity rule(s) below account for the key risk in this change. Each fix applies to all listed occurrences. CRITICAL rules include a concrete patch; HIGH rules include an illustrative before/after.

#### CRITICAL · aws-access-key-id — 2 occurrence(s) · P0
- **Scanners:** gitleaks, trivy
- **Where:** `security_samples/gitleaks_secrets.txt:7, security_samples/multilang/leaked_creds.env:7`
- **Why it matters:** Exposing AWS Access Key IDs can lead to unauthorized access to your AWS resources, allowing attackers to manipulate, steal, or destroy data.
- **How to fix:** Immediately rotate the exposed AWS Access Keys, remove them from the codebase, and use AWS IAM roles or Secrets Manager to manage credentials securely.
- **Suggested patch:**
  ```diff
  --- app/frontend/routes.py
  +++ app/frontend/routes.py
  @@ -1,5 +1,6 @@
   import os
   import json
  +from dotenv import load_dotenv
   
   # Load environment variables from .env file
  -load_dotenv()
  +load_dotenv()  # Load AWS Access Key ID and other secrets from .env
   
   class ConfigUpdate:
       # Class definition follows...
  ```

#### CRITICAL · cve-2019-20477 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/multilang/requirements.txt:0`
- **Why it matters:** PyYAML versions prior to 5.1 can lead to arbitrary code execution when loading untrusted YAML documents.
- **How to fix:** Upgrade PyYAML to version 5.1 or later to mitigate this vulnerability.
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
- **Why it matters:** This CVE indicates an incomplete fix for previous vulnerabilities in PyYAML, posing a risk of code execution from untrusted input.
- **How to fix:** Ensure PyYAML is updated to at least version 5.4.1 to address this issue.
- **Suggested patch:**
  ```diff
  --- security_samples/multilang/requirements.txt	2023-10-02 12:00:00.000000000 +0000
  +++ security_samples/multilang/requirements.txt	2023-10-02 12:00:00.000000000 +0000
  @@ -1 +1 @@
  -PyYAML==5.1.2
  +PyYAML>=5.4.1
  ```

#### CRITICAL · aws-0104 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:37`
- **Why it matters:** Allowing unrestricted egress on security groups can expose your infrastructure to data exfiltration and additional attacks from unauthorized IPs.
- **How to fix:** Restrict the egress rules to allow traffic only to necessary IP addresses or CIDR ranges.
- **Suggested patch:**
  ```diff
  --- security_samples/insecure_terraform.tf
  +++ security_samples/insecure_terraform.tf
  @@ -34,7 +34,7 @@
   resource "aws_security_group" "allow_all" {
     name        = "allow_all"
     description = "Allow all ingress"
   
  -  egress {
  +  egress {
       from_port   = 0
       to_port     = 0
       protocol    = "-1"
  -    cidr_blocks = ["0.0.0.0/0"]
  +    cidr_blocks = ["10.0.0.0/16"]
     }
   
     ingress {
       from_port   = 0
       to_port     = 0
       protocol    = "-1"
       cidr_blocks = ["0.0.0.0/0"]
     }
  ```

#### CRITICAL · ds-0031 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/multilang/Dockerfile:9`
- **Why it matters:** Passing secrets through build args or environment variables can expose sensitive information in build logs or stored images, increasing the risk of leaks.
- **How to fix:** Use Docker secrets or a secrets management tool to handle sensitive information securely, avoiding direct exposure through build args or env.
- **Suggested patch:**
  ```diff
  --- security_samples/multilang/Dockerfile
  +++ security_samples/multilang/Dockerfile
  @@ -6,7 +6,7 @@
   ARG NODE_ENV=production
   ARG BASE_IMAGE=node:14
   
   # Use a build secret for sensitive data
  -ARG SECRET_KEY
  +ARG SECRET_KEY_FILE
   
   RUN --mount=type=secret,id=secret_key,required=true \ 
       SECRET_KEY=$(cat /run/secrets/secret_key) \
  @@ -14,4 +14,4 @@
       && npm install --production
       && npm cache clean --force;
   
   # Application code
  -COPY . .
  +COPY . .
  ```

#### HIGH · b602 — 3 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `./security_samples/bandit_samples.py:31, ./security_samples/multilang/vuln_app.py:23, ./security_samples/semgrep_samples.py:34`
- **Why it matters:** Using subprocess with shell=True allows for shell injection vulnerabilities if untrusted input is included.
- **How to fix:** Avoid using shell=True in subprocess calls; instead, pass the command and arguments as a list.
- **Example fix (illustrative):**
  ```diff
  - subprocess.call('ls -l', shell=True)
  + subprocess.call(['ls', '-l'])
  ```

#### HIGH · b605 — 3 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `./security_samples/bandit_samples.py:36, ./security_samples/codeql_taintflow.py:36, ./security_samples/semgrep_samples.py:39`
- **Why it matters:** Starting a process via a shell increases the risk of command injection if user input is not properly sanitized.
- **How to fix:** Use list syntax for subprocess commands to prevent shell injection.
- **Example fix (illustrative):**
  ```diff
  - subprocess.run('echo $USER', shell=True)
  + subprocess.run(['echo', os.getenv('USER')])
  ```

#### HIGH · b324 — 2 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `./security_samples/bandit_samples.py:51, ./security_samples/multilang/vuln_app.py:38`
- **Why it matters:** MD5 is considered a weak hash function and should not be used for security-sensitive applications.
- **How to fix:** Replace MD5 with a stronger hash algorithm like SHA-256, and use the parameter usedforsecurity=False where applicable.
- **Example fix (illustrative):**
  ```diff
  - hashlib.md5(data).hexdigest()
  + hashlib.sha256(data).hexdigest()
  ```

#### HIGH · generic-api-key — 2 occurrence(s) · P1
- **Scanners:** gitleaks
- **Where:** `security_samples/gitleaks_secrets.txt:13, security_samples/multilang/leaked_creds.env:11`
- **Why it matters:** Exposing a generic API key can lead to unauthorized access and potential data breaches.
- **How to fix:** Store API keys securely using environment variables or secret management solutions, and rotate them regularly.
- **Example fix (illustrative):**
  ```diff
  - API_KEY = '12345abcdef'
  + API_KEY = os.getenv('MY_SECRET_API_KEY')
  ```

#### HIGH · private-key — 2 occurrence(s) · P1
- **Scanners:** gitleaks, trivy
- **Where:** `security_samples/gitleaks_secrets.txt:17, security_samples/gitleaks_secrets.txt:18`
- **Why it matters:** Leaking private keys can compromise the integrity and confidentiality of cryptographic operations.
- **How to fix:** Remove hardcoded private keys from the repository and use secure vaults for storage.
- **Example fix (illustrative):**
  ```diff
  - PRIVATE_KEY = '-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----'
  + PRIVATE_KEY = os.getenv('MY_PRIVATE_KEY')
  ```

#### HIGH · ds-0002 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/Dockerfile:0, security_samples/multilang/Dockerfile:0`
- **Why it matters:** Running containers as the root user can lead to privilege escalation and security vulnerabilities within the application. If an attacker compromises the container, they would have elevated permissions on the host system.
- **How to fix:** Ensure that Docker images specify a non-root user using the USER directive in the Dockerfile.
- **Example fix (illustrative):**
  ```diff
  - FROM ubuntu
  - USER root
  - RUN apt-get update && apt-get install -y somepackage
  + FROM ubuntu
  + USER appuser
  + RUN apt-get update && apt-get install -y somepackage
  ```

#### HIGH · aws-0086 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:14, security_samples/multilang/infra.tf:19`
- **Why it matters:** Public access to S3 buckets via public ACLs can lead to unauthorized access and data leakage. Bucket collections should enforce strict access controls.
- **How to fix:** Modify the S3 bucket policy to block public ACLs by setting the BlockPublicAcls option to true.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_s3_bucket" "example" {
  -   acl = "private"
  - }
  + resource "aws_s3_bucket" "example" {
  +   acl = "private"
  +   block_public_acls = true
  + }
  ```

#### HIGH · aws-0087 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:15, security_samples/multilang/infra.tf:19`
- **Why it matters:** Having public policies on S3 buckets can expose sensitive data to unauthorized users. Access policies should be restricted based on principle of least privilege.
- **How to fix:** Ensure that the S3 bucket policy does not allow public access by setting the BlockPublicPolicy option to true.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_s3_bucket_policy" "example" {
  -   bucket = aws_s3_bucket.example.id
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
  +   bucket = aws_s3_bucket.example.id
  +   policy = jsonencode({
  +     Version = "2012-10-17"
  +     Statement = [
  +       {
  +         Effect = "Allow"
  +         Principal = {"AWS" = "${aws_iam_user.example.arn}"
  +         Action = "s3:GetObject"
  +         Resource = "${aws_s3_bucket.example.arn}/*"
  +       }
  +     ]
  +   })
  +   block_public_policy = true
  + }
  ```

#### HIGH · aws-0091 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:16, security_samples/multilang/infra.tf:19`
- **Why it matters:** Allowing public ACLs can expose a bucket to unauthorized access, leading to potential data breaches. It is essential to block public access by modifying the S3 bucket's settings.
- **How to fix:** Set the BlockPublicAcls attribute to true in the S3 bucket resource.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_s3_bucket" "example" {
  -   acl = "private"
  - }
  + resource "aws_s3_bucket" "example" {
  +   acl = "private"
  +   block_public_acls = true
  + }
  ```

#### HIGH · aws-0092 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:8, security_samples/multilang/infra.tf:21`
- **Why it matters:** S3 buckets that are publicly accessible through ACLs pose significant security risks. Sensitive data may be exposed to unauthorized users if not properly configured.
- **How to fix:** Inspect S3 bucket configurations and ensure that all buckets are set to private or have restricted access policies.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_s3_bucket" "example" {
  -   acl = "public-read"
  - }
  + resource "aws_s3_bucket" "example" {
  +   acl = "private"
  + }
  ```

#### HIGH · aws-0093 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:17, security_samples/multilang/infra.tf:19`
- **Why it matters:** Public access to S3 buckets can lead to unauthorized data exposure and security breaches.
- **How to fix:** Update the S3 bucket policy to explicitly deny public access for all users and restrict access based on specific IAM roles or accounts.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_s3_bucket" "example" {
  -   acl = "public-read"
  - }
  + resource "aws_s3_bucket" "example" {
  +   acl = "private"
  +   block_public_acls = true
  +   ignore_public_acls = true
  + }
  ```

#### HIGH · aws-0107 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:29, security_samples/multilang/infra.tf:14`
- **Why it matters:** Allowing unrestricted ingress to SSH or RDP can enable unauthorized access and compromise server security.
- **How to fix:** Restrict ingress rules to specific IP addresses or ranges that require access to the servers running SSH or RDP.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_security_group" "example" {
  -   ingress {
  -     from_port   = 22
  -     to_port     = 22
  -     protocol    = "tcp"
  -     cidr_blocks = ["0.0.0.0/0"]
  -   }
  - }
  + resource "aws_security_group" "example" {
  +   ingress {
  +     from_port   = 22
  +     to_port     = 22
  +     protocol    = "tcp"
  +     cidr_blocks = ["192.168.1.0/24"]
  +   }
  + }
  ```

#### HIGH · aws-0132 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:5, security_samples/multilang/infra.tf:19`
- **Why it matters:** Using default S3 encryption keys may expose encrypted data to risks. Customer Managed Keys provide better control and auditing.
- **How to fix:** Modify the S3 bucket configuration to use AWS KMS with a Customer Managed Key for encryption of data at rest.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_s3_bucket" "example" {
  -   server_side_encryption_configuration {
  -     rule {
  -       apply_server_side_encryption_by_default {
  -         sse_algorithm = "AES256"
  -       }
  -     }
  -   }
  - }
  + resource "aws_s3_bucket" "example" {
  +   server_side_encryption_configuration {
  +     rule {
  +       apply_server_side_encryption_by_default {
  +         sse_algorithm = "aws:kms"
  +         kms_master_key_id = "arn:aws:kms:REGION:ACCOUNT_ID:key/KEY_ID"
  +       }
  +     }
  +   }
  + }
  ```

#### HIGH · b501 — 1 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `./security_samples/semgrep_samples.py:44`
- **Why it matters:** Disabling SSL certificate verification introduces a security vulnerability by making the application susceptible to man-in-the-middle attacks.
- **How to fix:** Always enable SSL verification by setting 'verify=True' in HTTP requests to ensure secure communication.
- **Example fix (illustrative):**
  ```diff
  - response = requests.get('https://example.com/api', verify=False)
  + response = requests.get('https://example.com/api', verify=True)
  ```

#### HIGH · hashicorp-tf-password — 1 occurrence(s) · P1
- **Scanners:** gitleaks
- **Where:** `security_samples/multilang/infra.tf:31`
- **Why it matters:** Exposed password fields in configuration files can lead to unauthorized access to infrastructure and sensitive data breaches.
- **How to fix:** Use a secure secrets management solution to store sensitive values instead of hardcoding them in Terraform configuration files.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_db_instance" "example" {
  -   password = "my-secure-password"
  - }
  + resource "aws_db_instance" "example" {
  +   password = var.db_password
  + }
  + 
  + variable "db_password" { }
  ```

#### HIGH · cve-2019-10906 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/multilang/requirements.txt:0`
- **Why it matters:** The use of str.format_map in Jinja2 can allow an attacker to escape the intended sandbox environment, potentially leading to code execution vulnerabilities.
- **How to fix:** Replace str.format_map with a safer alternative that does not allow sandbox escapes, such as using Jinja2's built-in mechanisms for variable substitution.
- **Example fix (illustrative):**
  ```diff
  - template = '{{ user_input }}'.format_map(user_data)
  + template = jinja2.Template('{{ user_input }}').render(user_data)
  ```

#### HIGH · ds-0029 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/multilang/Dockerfile:6`
- **Why it matters:** Using 'apt-get' without the '--no-install-recommends' option can lead to unnecessary packages being installed, increasing the attack surface of the container.
- **How to fix:** Modify the Dockerfile to include '--no-install-recommends' when using 'apt-get' to ensure only essential packages are installed.
- **Example fix (illustrative):**
  ```diff
  - RUN apt-get update && apt-get install -y package-name
  + RUN apt-get update && apt-get install --no-install-recommends -y package-name
  ```

#### HIGH · aws-0080 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/multilang/infra.tf:32`
- **Why it matters:** RDS encryption at the DB instance level is crucial for securing data at rest. Without it, sensitive information may be exposed if the database is compromised.
- **How to fix:** Ensure that RDS instances are configured with encryption enabled at the DB instance level during the provisioning process.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_db_instance" "example" { ... }
  + resource "aws_db_instance" "example" { storage_encrypted = true ... }
  ```

#### HIGH · aws-0180 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/multilang/infra.tf:33`
- **Why it matters:** Having RDS instances publicly accessible poses a serious security risk, as it can expose the database to unauthorized access from the internet.
- **How to fix:** Modify the DB instance configuration to ensure that 'publicly_accessible' is set to false, unless explicitly required.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_db_instance" "example" { publicly_accessible = true ... }
  + resource "aws_db_instance" "example" { publicly_accessible = false ... }
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
| MEDIUM | `ckv2_aws_61` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_145` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_20` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
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
5/7 scanner(s) completed. A ❌ scanner ran but its result could not be collected — treat its coverage as unknown, not clean.

| Scanner | Status | Findings | Detail |
|---|---|---|---|
| bandit | ✅ ran | 563 | completed |
| semgrep | ❌ failed | — | empty output; tool produced no report: Traceback (most recent call last): |
| codeql | ❌ failed | — | all language analyses failed — javascript: database create exited 2: A fatal error occurred: Cannot create database at /data/workspace/.codeql-cache/codeql-db-javascript-c9cbb25d74f0 because /data/wo… |
| gitleaks | ✅ ran | 6 | completed |
| checkov | ✅ ran | 46 | completed |
| trivy | ✅ ran | 50 | completed |
| njsscan | ✅ ran | 0 | completed |

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

### ❗ Remaining Findings (658)
- **aws-access-key-id** (CRITICAL, secret) at `security_samples/gitleaks_secrets.txt:7` — scanners: gitleaks, trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Exposing AWS Access Key IDs can lead to unauthorized access to your AWS resources, allowing attackers to manipulate, steal, or destroy data._
  - **Suggested fix approach:** Immediately rotate the exposed AWS Access Keys, remove them from the codebase, and use AWS IAM roles or Secrets Manager to manage credentials securely.
  - **Suggested change:**
    ```diff
    --- app/frontend/routes.py
    +++ app/frontend/routes.py
    @@ -1,5 +1,6 @@
     import os
     import json
    +from dotenv import load_dotenv
     
     # Load environment variables from .env file
    -load_dotenv()
    +load_dotenv()  # Load AWS Access Key ID and other secrets from .env
     
     class ConfigUpdate:
         # Class definition follows...
    ```
- **aws-access-key-id** (CRITICAL, secret) at `security_samples/multilang/leaked_creds.env:7` — scanners: gitleaks, trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Exposing AWS Access Key IDs can lead to unauthorized access to your AWS resources, allowing attackers to manipulate, steal, or destroy data._
  - **Suggested fix approach:** Immediately rotate the exposed AWS Access Keys, remove them from the codebase, and use AWS IAM roles or Secrets Manager to manage credentials securely.
- **cve-2019-20477** (CRITICAL, dependency) at `security_samples/multilang/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _PyYAML versions prior to 5.1 can lead to arbitrary code execution when loading untrusted YAML documents._
  - **Suggested fix approach:** Upgrade PyYAML to version 5.1 or later to mitigate this vulnerability.
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
  - _This CVE indicates an incomplete fix for previous vulnerabilities in PyYAML, posing a risk of code execution from untrusted input._
  - **Suggested fix approach:** Ensure PyYAML is updated to at least version 5.4.1 to address this issue.
  - **Suggested change:**
    ```diff
    --- security_samples/multilang/requirements.txt	2023-10-02 12:00:00.000000000 +0000
    +++ security_samples/multilang/requirements.txt	2023-10-02 12:00:00.000000000 +0000
    @@ -1 +1 @@
    -PyYAML==5.1.2
    +PyYAML>=5.4.1
    ```
- **aws-0104** (CRITICAL, iac) at `security_samples/insecure_terraform.tf:37` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Allowing unrestricted egress on security groups can expose your infrastructure to data exfiltration and additional attacks from unauthorized IPs._
  - **Suggested fix approach:** Restrict the egress rules to allow traffic only to necessary IP addresses or CIDR ranges.
  - **Suggested change:**
    ```diff
    --- security_samples/insecure_terraform.tf
    +++ security_samples/insecure_terraform.tf
    @@ -34,7 +34,7 @@
     resource "aws_security_group" "allow_all" {
       name        = "allow_all"
       description = "Allow all ingress"
     
    -  egress {
    +  egress {
         from_port   = 0
         to_port     = 0
         protocol    = "-1"
    -    cidr_blocks = ["0.0.0.0/0"]
    +    cidr_blocks = ["10.0.0.0/16"]
       }
     
       ingress {
         from_port   = 0
         to_port     = 0
         protocol    = "-1"
         cidr_blocks = ["0.0.0.0/0"]
       }
    ```
- **ds-0031** (CRITICAL, iac) at `security_samples/multilang/Dockerfile:9` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Passing secrets through build args or environment variables can expose sensitive information in build logs or stored images, increasing the risk of leaks._
  - **Suggested fix approach:** Use Docker secrets or a secrets management tool to handle sensitive information securely, avoiding direct exposure through build args or env.
  - **Suggested change:**
    ```diff
    --- security_samples/multilang/Dockerfile
    +++ security_samples/multilang/Dockerfile
    @@ -6,7 +6,7 @@
     ARG NODE_ENV=production
     ARG BASE_IMAGE=node:14
     
     # Use a build secret for sensitive data
    -ARG SECRET_KEY
    +ARG SECRET_KEY_FILE
     
     RUN --mount=type=secret,id=secret_key,required=true \ 
         SECRET_KEY=$(cat /run/secrets/secret_key) \
    @@ -14,4 +14,4 @@
         && npm install --production
         && npm cache clean --force;
     
     # Application code
    -COPY . .
    +COPY . .
    ```
- **b602** (HIGH, code) at `./security_samples/bandit_samples.py:31` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using subprocess with shell=True allows for shell injection vulnerabilities if untrusted input is included._
  - **Suggested fix approach:** Avoid using shell=True in subprocess calls; instead, pass the command and arguments as a list.
- **b605** (HIGH, code) at `./security_samples/bandit_samples.py:36` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Starting a process via a shell increases the risk of command injection if user input is not properly sanitized._
  - **Suggested fix approach:** Use list syntax for subprocess commands to prevent shell injection.
- **b324** (HIGH, code) at `./security_samples/bandit_samples.py:51` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _MD5 is considered a weak hash function and should not be used for security-sensitive applications._
  - **Suggested fix approach:** Replace MD5 with a stronger hash algorithm like SHA-256, and use the parameter usedforsecurity=False where applicable.
- **b605** (HIGH, code) at `./security_samples/codeql_taintflow.py:36` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Starting a process via a shell increases the risk of command injection if user input is not properly sanitized._
  - **Suggested fix approach:** Use list syntax for subprocess commands to prevent shell injection.
- **b602** (HIGH, code) at `./security_samples/multilang/vuln_app.py:23` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using subprocess with shell=True allows for shell injection vulnerabilities if untrusted input is included._
  - **Suggested fix approach:** Avoid using shell=True in subprocess calls; instead, pass the command and arguments as a list.
- **b324** (HIGH, code) at `./security_samples/multilang/vuln_app.py:38` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _MD5 is considered a weak hash function and should not be used for security-sensitive applications._
  - **Suggested fix approach:** Replace MD5 with a stronger hash algorithm like SHA-256, and use the parameter usedforsecurity=False where applicable.
- **b602** (HIGH, code) at `./security_samples/semgrep_samples.py:34` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using subprocess with shell=True allows for shell injection vulnerabilities if untrusted input is included._
  - **Suggested fix approach:** Avoid using shell=True in subprocess calls; instead, pass the command and arguments as a list.
- **b605** (HIGH, code) at `./security_samples/semgrep_samples.py:39` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Starting a process via a shell increases the risk of command injection if user input is not properly sanitized._
  - **Suggested fix approach:** Use list syntax for subprocess commands to prevent shell injection.
- **b501** (HIGH, code) at `./security_samples/semgrep_samples.py:44` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Disabling SSL certificate verification introduces a security vulnerability by making the application susceptible to man-in-the-middle attacks._
  - **Suggested fix approach:** Always enable SSL verification by setting 'verify=True' in HTTP requests to ensure secure communication.
- **generic-api-key** (HIGH, secret) at `security_samples/gitleaks_secrets.txt:13` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Exposing a generic API key can lead to unauthorized access and potential data breaches._
  - **Suggested fix approach:** Store API keys securely using environment variables or secret management solutions, and rotate them regularly.
- **private-key** (HIGH, secret) at `security_samples/gitleaks_secrets.txt:17` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Leaking private keys can compromise the integrity and confidentiality of cryptographic operations._
  - **Suggested fix approach:** Remove hardcoded private keys from the repository and use secure vaults for storage.
- **hashicorp-tf-password** (HIGH, secret) at `security_samples/multilang/infra.tf:31` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Exposed password fields in configuration files can lead to unauthorized access to infrastructure and sensitive data breaches._
  - **Suggested fix approach:** Use a secure secrets management solution to store sensitive values instead of hardcoding them in Terraform configuration files.
- **generic-api-key** (HIGH, secret) at `security_samples/multilang/leaked_creds.env:11` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Exposing a generic API key can lead to unauthorized access and potential data breaches._
  - **Suggested fix approach:** Store API keys securely using environment variables or secret management solutions, and rotate them regularly.
- **cve-2019-10906** (HIGH, dependency) at `security_samples/multilang/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _The use of str.format_map in Jinja2 can allow an attacker to escape the intended sandbox environment, potentially leading to code execution vulnerabilities._
  - **Suggested fix approach:** Replace str.format_map with a safer alternative that does not allow sandbox escapes, such as using Jinja2's built-in mechanisms for variable substitution.
- **ds-0002** (HIGH, iac) at `security_samples/Dockerfile:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Running containers as the root user can lead to privilege escalation and security vulnerabilities within the application. If an attacker compromises the container, they would have elevated permissions on the host system._
  - **Suggested fix approach:** Ensure that Docker images specify a non-root user using the USER directive in the Dockerfile.
- **aws-0086** (HIGH, iac) at `security_samples/insecure_terraform.tf:14` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Public access to S3 buckets via public ACLs can lead to unauthorized access and data leakage. Bucket collections should enforce strict access controls._
  - **Suggested fix approach:** Modify the S3 bucket policy to block public ACLs by setting the BlockPublicAcls option to true.
- **aws-0087** (HIGH, iac) at `security_samples/insecure_terraform.tf:15` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Having public policies on S3 buckets can expose sensitive data to unauthorized users. Access policies should be restricted based on principle of least privilege._
  - **Suggested fix approach:** Ensure that the S3 bucket policy does not allow public access by setting the BlockPublicPolicy option to true.
- **aws-0091** (HIGH, iac) at `security_samples/insecure_terraform.tf:16` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Allowing public ACLs can expose a bucket to unauthorized access, leading to potential data breaches. It is essential to block public access by modifying the S3 bucket's settings._
  - **Suggested fix approach:** Set the BlockPublicAcls attribute to true in the S3 bucket resource.
- **aws-0092** (HIGH, iac) at `security_samples/insecure_terraform.tf:8` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 buckets that are publicly accessible through ACLs pose significant security risks. Sensitive data may be exposed to unauthorized users if not properly configured._
  - **Suggested fix approach:** Inspect S3 bucket configurations and ensure that all buckets are set to private or have restricted access policies.
- **aws-0093** (HIGH, iac) at `security_samples/insecure_terraform.tf:17` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Public access to S3 buckets can lead to unauthorized data exposure and security breaches._
  - **Suggested fix approach:** Update the S3 bucket policy to explicitly deny public access for all users and restrict access based on specific IAM roles or accounts.
- **aws-0107** (HIGH, iac) at `security_samples/insecure_terraform.tf:29` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Allowing unrestricted ingress to SSH or RDP can enable unauthorized access and compromise server security._
  - **Suggested fix approach:** Restrict ingress rules to specific IP addresses or ranges that require access to the servers running SSH or RDP.
- **aws-0132** (HIGH, iac) at `security_samples/insecure_terraform.tf:5` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using default S3 encryption keys may expose encrypted data to risks. Customer Managed Keys provide better control and auditing._
  - **Suggested fix approach:** Modify the S3 bucket configuration to use AWS KMS with a Customer Managed Key for encryption of data at rest.
- **ds-0002** (HIGH, iac) at `security_samples/multilang/Dockerfile:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Running containers as the root user can lead to privilege escalation and security vulnerabilities within the application. If an attacker compromises the container, they would have elevated permissions on the host system._
  - **Suggested fix approach:** Ensure that Docker images specify a non-root user using the USER directive in the Dockerfile.
- **ds-0029** (HIGH, iac) at `security_samples/multilang/Dockerfile:6` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using 'apt-get' without the '--no-install-recommends' option can lead to unnecessary packages being installed, increasing the attack surface of the container._
  - **Suggested fix approach:** Modify the Dockerfile to include '--no-install-recommends' when using 'apt-get' to ensure only essential packages are installed.
- **aws-0080** (HIGH, iac) at `security_samples/multilang/infra.tf:32` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _RDS encryption at the DB instance level is crucial for securing data at rest. Without it, sensitive information may be exposed if the database is compromised._
  - **Suggested fix approach:** Ensure that RDS instances are configured with encryption enabled at the DB instance level during the provisioning process.
- **aws-0086** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Public access to S3 buckets via public ACLs can lead to unauthorized access and data leakage. Bucket collections should enforce strict access controls._
  - **Suggested fix approach:** Modify the S3 bucket policy to block public ACLs by setting the BlockPublicAcls option to true.
- **aws-0087** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Having public policies on S3 buckets can expose sensitive data to unauthorized users. Access policies should be restricted based on principle of least privilege._
  - **Suggested fix approach:** Ensure that the S3 bucket policy does not allow public access by setting the BlockPublicPolicy option to true.
- **aws-0091** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Allowing public ACLs can expose a bucket to unauthorized access, leading to potential data breaches. It is essential to block public access by modifying the S3 bucket's settings._
  - **Suggested fix approach:** Set the BlockPublicAcls attribute to true in the S3 bucket resource.
- **aws-0092** (HIGH, iac) at `security_samples/multilang/infra.tf:21` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 buckets that are publicly accessible through ACLs pose significant security risks. Sensitive data may be exposed to unauthorized users if not properly configured._
  - **Suggested fix approach:** Inspect S3 bucket configurations and ensure that all buckets are set to private or have restricted access policies.
- **aws-0093** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Public access to S3 buckets can lead to unauthorized data exposure and security breaches._
  - **Suggested fix approach:** Update the S3 bucket policy to explicitly deny public access for all users and restrict access based on specific IAM roles or accounts.
- **aws-0107** (HIGH, iac) at `security_samples/multilang/infra.tf:14` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Allowing unrestricted ingress to SSH or RDP can enable unauthorized access and compromise server security._
  - **Suggested fix approach:** Restrict ingress rules to specific IP addresses or ranges that require access to the servers running SSH or RDP.
- **aws-0132** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using default S3 encryption keys may expose encrypted data to risks. Customer Managed Keys provide better control and auditing._
  - **Suggested fix approach:** Modify the S3 bucket configuration to use AWS KMS with a Customer Managed Key for encryption of data at rest.
- **aws-0180** (HIGH, iac) at `security_samples/multilang/infra.tf:33` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Having RDS instances publicly accessible poses a serious security risk, as it can expose the database to unauthorized access from the internet._
  - **Suggested fix approach:** Modify the DB instance configuration to ensure that 'publicly_accessible' is set to false, unless explicitly required.
- **private-key** (HIGH, secret) at `security_samples/gitleaks_secrets.txt:18` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Leaking private keys can compromise the integrity and confidentiality of cryptographic operations._
  - **Suggested fix approach:** Remove hardcoded private keys from the repository and use secure vaults for storage.
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
