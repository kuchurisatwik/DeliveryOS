# AI Software Delivery Engineer: Architecture Review

**Repository:** kuchurisatwik/DeliveryOS
**Commit SHA:** dd02866ade42f8991884a79b682df1fd7a1d2ed8
**Branch:** ai-sde/review-dd02866-20260720142032
**Timestamp:** 2026-07-20T14:24:20.742912Z

No AI analysis was generated.

---
## 🔒 Security Pipeline Report
**Commit:** [`dd02866ade`](https://github.com/kuchurisatwik/DeliveryOS/commit/dd02866ade42f8991884a79b682df1fd7a1d2ed8)
**Repository:** `kuchurisatwik/DeliveryOS`
**Branch under review:** `feat/security-pipeline`
**Security Summary:** 0 finding(s) fixed; 132 finding(s) remaining; quality gate failed.
**Scanned scope:** 10 changed file(s).

**Findings by severity:** CRITICAL: 10, HIGH: 42, MEDIUM: 67, LOW: 13

### 🛠️ Remediation Guide — Key High/Critical Findings
The 39 highest-severity rule(s) below account for the key risk in this change. Each fix applies to all listed occurrences. CRITICAL rules include a concrete patch; HIGH rules include an illustrative before/after.

#### CRITICAL · aws-access-key-id — 2 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/gitleaks_secrets.txt:7, security_samples/multilang/leaked_creds.env:7`
- **Why it matters:** Exposing AWS Access Key IDs can grant unauthorized access to your AWS resources, leading to potential data breaches and security vulnerabilities.
- **How to fix:** Remove hardcoded AWS Access Key IDs from the repository and use environment variables or AWS IAM roles for access management.
- **Suggested patch:**
  ```diff
  --- security_samples/gitleaks_secrets.txt
  +++ security_samples/gitleaks_secrets.txt
  @@ -6,7 +6,7 @@
   internal
   1234567890abcdef1234567890abcdef
   -AWS_ACCESS_KEY_ID: AKIAIOSFODNN7EXAMPLE
   +AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
  ```

#### CRITICAL · py/command-line-injection — 1 occurrence(s) · P0
- **Scanners:** codeql
- **Where:** `security_samples/multilang/vuln_app.py:23`
- **Why it matters:** Command-line injection vulnerabilities allow attackers to execute arbitrary commands on the host machine, potentially compromising the system.
- **How to fix:** Always validate and sanitize user inputs before using them in command-line executions. Prefer using safer API methods or libraries.
- **Suggested patch:**
  ```diff
  --- security_samples/multilang/vuln_app.py
  +++ security_samples/multilang/vuln_app.py
  @@ -1,5 +1,5 @@
   def dangerous(expr: str):
  -    # Bandit B307 / Semgrep: eval on untrusted input
  -    return eval(expr)
  +    # Avoid using eval on untrusted input
  +    return safe_eval(expr)
   
  -def safe_eval(expr: str):
  +def safe_eval(expr: str):
       # Implement a safe evaluation of expressions here
       pass
  ```

#### CRITICAL · js/command-line-injection — 1 occurrence(s) · P0
- **Scanners:** codeql
- **Where:** `security_samples/multilang/server.js:21`
- **Why it matters:** Command-line injection vulnerabilities can lead to severe exploitation where an attacker gains control of the server environment.
- **How to fix:** Ensure user inputs are sanitized and validated before passing them to command-line executions, and use safer alternatives when possible.
- **Example fix (illustrative):**
  ```diff
  - child_process.exec('command ' + userInput) # Vulnerable command execution
  + child_process.spawn('command', [userInput], { stdio: 'inherit' }) # Secure execution
  ```

#### CRITICAL · js/code-injection — 1 occurrence(s) · P0
- **Scanners:** codeql
- **Where:** `security_samples/multilang/server.js:26`
- **Why it matters:** Code injection vulnerabilities can lead to arbitrary code execution, providing attackers with the ability to take control over the application.
- **How to fix:** Do not execute dynamic code from user inputs. Instead, use safe parsing libraries that ensure only expected commands are executed.
- **Example fix (illustrative):**
  ```diff
  - eval(userInput) # Dangerous code execution
  + const safeResult = safeEval(userInput) # Secure evaluation
  ```

#### CRITICAL · cve-2019-20477 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/multilang/requirements.txt:0`
- **Why it matters:** Vulnerabilities in libraries like PyYAML can lead to remote code execution through deserialization attacks, jeopardizing application security.
- **How to fix:** Upgrade to the latest version of PyYAML that has addressed this vulnerability or switch to a safer library for YAML parsing.
- **Example fix (illustrative):**
  ```diff
  - pyyaml.load(data) # Unsafe loading from untrusted source
  + pyyaml.safe_load(data) # Safe loading from untrusted source
  ```

#### CRITICAL · cve-2020-14343 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/multilang/requirements.txt:0`
- **Why it matters:** The dependency PyYAML contains a security vulnerability that is not fully resolved, which can lead to data exposure or code execution in the application.
- **How to fix:** Upgrade PyYAML to a version that fully addresses CVE-2020-14343. Consult the official PyYAML repository for the latest secure version.
- **Example fix (illustrative):**
  ```diff
  - PyYAML==5.3.1
  + PyYAML==5.4.1
  ```

#### CRITICAL · cve-2020-1747 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/multilang/requirements.txt:0`
- **Why it matters:** Using FullLoader with PyYAML can lead to arbitrary command execution, making the application vulnerable to attacks.
- **How to fix:** Change the loading method to use safe loading alternatives, such as 'yaml.safe_load'. Avoid using FullLoader for untrusted input.
- **Example fix (illustrative):**
  ```diff
  - data = yaml.load(yaml_string, Loader=yaml.FullLoader)
  + data = yaml.safe_load(yaml_string)
  ```

#### CRITICAL · aws-0104 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:37`
- **Why it matters:** A security group rule allowing unrestricted egress to any IP address poses a significant security risk, allowing outbound traffic to any destination.
- **How to fix:** Restrict the egress rule to specific, validated IP addresses or services, or remove unnecessary egress rules.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_security_group" "example" { 
  -   egress { 
  -     from_port = 0 
  -     to_port   = 0 
  -     protocol  = "-1" 
  -     cidr_blocks = ["0.0.0.0/0"] 
  -   }
  - }
  + resource "aws_security_group" "example" { 
  +   egress { 
  +     from_port = 0 
  +     to_port   = 0 
  +     protocol  = "-1" 
  +     cidr_blocks = ["192.168.1.0/24"] 
  +   }
  + }
  ```

#### CRITICAL · ds-0031 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/multilang/Dockerfile:9`
- **Why it matters:** Passing secrets via build arguments or environment variables can lead to exposure of sensitive data, especially when the data might be logged or viewed by unauthorized users.
- **How to fix:** Remove secrets from build arguments and environment variables; use secure storage solutions, such as AWS Secrets Manager or Docker secrets.
- **Example fix (illustrative):**
  ```diff
  - FROM node:14 
  - ARG SECRET_KEY 
  - RUN echo $SECRET_KEY
  + FROM node:14 
  + # Use a secure method to handle SECRET_KEY  
  + # such as a Docker secret or a secure volume.
  ```

#### HIGH · javascript.lang.security.detect-child-process.detect-child-process — 2 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\api.ts:8, security_samples\multilang\server.js:21`
- **Why it matters:** Using user-supplied input directly in child_process calls can lead to command injections, making the system susceptible to attacks.
- **How to fix:** Sanitize or validate all user inputs before using them in child_process calls to prevent command injection vulnerabilities.
- **Example fix (illustrative):**
  ```diff
  - const command = req.body.command; 
  - child_process.exec(command);
  + const sanitizedCommand = sanitizeInput(req.body.command); 
  + child_process.exec(sanitizedCommand);
  ```

#### HIGH · js/missing-rate-limiting — 2 occurrence(s) · P1
- **Scanners:** codeql
- **Where:** `security_samples/multilang/server.js:10, security_samples/multilang/server.js:19`
- **Why it matters:** Exposing a route handler without rate limiting allows an attacker to perform Denial of Service (DoS) attacks, overwhelming the server with requests.
- **How to fix:** Implement rate limiting for the route handler to control the number of requests it can handle in a given timeframe.
- **Example fix (illustrative):**
  ```diff
  - app.get('/api/data', (req, res) => { /* Database access here */ });
  + const rateLimit = require('express-rate-limit');
  + const limiter = rateLimit({ windowMs: 15 * 60 * 1000, max: 100 });
  + app.get('/api/data', limiter, (req, res) => { /* Database access here */ });
  ```

#### HIGH · generic-api-key — 2 occurrence(s) · P1
- **Scanners:** gitleaks
- **Where:** `security_samples/multilang/leaked_creds.env:11, security_samples/gitleaks_secrets.txt:13`
- **Why it matters:** Generic API keys can grant unauthorized access to sensitive services or data, leading to data breaches or misuse of system resources.
- **How to fix:** Replace the generic API key with a secure method for credentials management, such as environment variables or a secrets manager.
- **Example fix (illustrative):**
  ```diff
  - API_KEY=abcd1234 generic_api_request();
  + const apiKey = process.env.API_KEY;
  + generic_api_request(apiKey);
  ```

#### HIGH · private-key — 2 occurrence(s) · P1
- **Scanners:** gitleaks, trivy
- **Where:** `security_samples/gitleaks_secrets.txt:17, security_samples/gitleaks_secrets.txt:18`
- **Why it matters:** Private keys stored in code may allow unauthorized access to encrypted data and services, resulting in data leaks and security vulnerabilities.
- **How to fix:** Remove private keys from the codebase and use secure vault or environment variables to manage them.
- **Example fix (illustrative):**
  ```diff
  - PRIVATE_KEY='my_private_key'
  - use_key(PRIVATE_KEY);
  + const privateKey = process.env.PRIVATE_KEY;
  + use_key(privateKey);
  ```

#### HIGH · ds-0002 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/Dockerfile:0, security_samples/multilang/Dockerfile:0`
- **Why it matters:** Running a Docker container as the root user presents a significant security risk, as it could lead to privilege escalation and system compromise.
- **How to fix:** Specify a non-root user in the Dockerfile to limit the privileges of container processes.
- **Example fix (illustrative):**
  ```diff
  - FROM node:14
  - USER root
  - RUN npm install;
  + FROM node:14
  + RUN npm install;
  + USER node;
  ```

#### HIGH · aws-0086 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:14, security_samples/multilang/infra.tf:19`
- **Why it matters:** Allowing public access to S3 buckets can expose sensitive data to the internet, leading to potential data breaches.
- **How to fix:** Update the S3 bucket policy to block public ACLs and use private settings by default.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_s3_bucket" "my_bucket" {
  -   acl = "public-read"
  - }
  + resource "aws_s3_bucket" "my_bucket" {
  +   acl = "private"
  + }
  ```

#### HIGH · aws-0087 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:15, security_samples/multilang/infra.tf:19`
- **Why it matters:** Public access to S3 buckets can lead to sensitive data leakage. A proper access block policy ensures that unintended public access is restricted.
- **How to fix:** Update the S3 bucket policy to explicitly deny public access by ensuring the 'BlockPublicAcls' setting is applied.
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
  + }
  ```

#### HIGH · aws-0091 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:16, security_samples/multilang/infra.tf:19`
- **Why it matters:** Ignoring public ACLs is crucial to avoid allowing public access through misconfigured bucket permissions.
- **How to fix:** Set the 'IgnorePublicAcls' parameter to true in the S3 bucket settings to prevent public access through ACLs.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_s3_bucket" "example" {
  -   bucket = "example-bucket"
  -   acl    = "public-read"
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
- **Why it matters:** S3 buckets should be configured to avoid public access through ACL settings to protect sensitive data stored in them.
- **How to fix:** Ensure the S3 bucket's ACL is set to private or a restrictive setting to prevent public access.
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
- **Why it matters:** Restricting public bucket access limits data exposure to unauthorized users and helps maintain confidentiality.
- **How to fix:** Adjust the S3 bucket policy to include stricter permissions and limit public accessibility only to necessary resources.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_s3_bucket" "example" {
  -   bucket = "example-bucket"
  -   acl    = "public-read"
  - }
  + resource "aws_s3_bucket" "example" {
  +   bucket = "example-bucket"
  +   acl    = "private"
  +   block_public_policy = true
  + }
  ```

#### HIGH · aws-0107 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:29, security_samples/multilang/infra.tf:14`
- **Why it matters:** Unrestricted ingress rules for SSH/RDP increase the attack surface of your instances, making it easier for attackers to gain access.
- **How to fix:** Restrict ingress rules for SSH or RDP to known IP addresses or ranges only, rather than allowing access from anywhere.
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
  +     cidr_blocks = ["192.168.1.1/32"]
  +   }
  + }
  ```

#### HIGH · aws-0132 — 2 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:5, security_samples/multilang/infra.tf:19`
- **Why it matters:** Using Customer Managed Keys (CMKs) for S3 encryption enhances security by allowing more control over the encryption process and key management.
- **How to fix:** Ensure that all S3 buckets defined in your infrastructure as code (IAC) use Customer Managed Keys for encryption instead of default or no encryption.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_s3_bucket" "example" {
  -   bucket = "my-secure-bucket"
  -   server_side_encryption_configuration {
  -     rule {
  -       
  -     }
  -   }
  - }
  + resource "aws_s3_bucket" "example" {
  +   bucket = "my-secure-bucket"
  +   server_side_encryption_configuration {
  +     rule {
  +       apply_server_side_encryption_by_default {
  +         sse_algorithm = "aws:kms"
  +         kms_master_key_id = "arn:aws:kms:region:account-id:key/key-id"
  +       }
  +     }
  +   }
  + }
  ```

#### HIGH · python.flask.security.injection.subprocess-injection.subprocess-injection — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\vuln_app.py:23`
- **Why it matters:** Using unsanitized user input in a subprocess call can lead to command injection vulnerabilities, allowing attackers to execute arbitrary commands.
- **How to fix:** Avoid using user input directly in subprocess calls. If subprocess is necessary, restrict the commands by using allowlists or prefer Python APIs.
- **Example fix (illustrative):**
  ```diff
  - subprocess.call(user_input)
  + allowed_commands = {'ls': 'list directory', 'pwd': 'print working directory'}
  + subprocess.call(allowed_commands[user_input])
  ```

#### HIGH · python.lang.security.dangerous-subprocess-use.dangerous-subprocess-use — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\vuln_app.py:23`
- **Why it matters:** Using user-controlled data in the subprocess call can lead to command injection, exposing vulnerabilities in the application.
- **How to fix:** Sanitize user input before passing it to subprocess calls. Consider using 'shlex.quote()' or similar functions to escape inputs.
- **Example fix (illustrative):**
  ```diff
  - subprocess.call('echo ' + user_input, shell=True)
  + subprocess.call(['echo', shlex.quote(user_input)], shell=False)
  ```

#### HIGH · python.lang.security.audit.subprocess-shell-true.subprocess-shell-true — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\vuln_app.py:23`
- **Why it matters:** Setting 'shell=True' in subprocess calls can expose the application to shell injection attacks by allowing attacker-controlled variables to be executed.
- **How to fix:** Always set 'shell=False' when using subprocess to avoid executing commands through the shell.
- **Example fix (illustrative):**
  ```diff
  - subprocess.call(command, shell=True)
  + subprocess.call(command, shell=False)
  ```

#### HIGH · python.flask.security.injection.tainted-sql-string.tainted-sql-string — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\vuln_app.py:32`
- **Why it matters:** Manually constructing SQL strings with user input increases the risk of SQL injection, which could allow unauthorized data access or manipulation.
- **How to fix:** Use parameterized queries or ORM methods to safely handle user input when interacting with the database.
- **Example fix (illustrative):**
  ```diff
  - db.execute('SELECT * FROM users WHERE username = ' + username)
  + db.execute('SELECT * FROM users WHERE username = ?', (username,))
  ```

#### HIGH · py/sql-injection — 1 occurrence(s) · P1
- **Scanners:** codeql
- **Where:** `security_samples/multilang/vuln_app.py:32`
- **Why it matters:** User inputs are directly included in SQL queries without proper sanitization, leading to potential SQL injection vulnerabilities.
- **How to fix:** Use parameterized queries or an ORM to safely handle user inputs and prevent SQL injection.
- **Example fix (illustrative):**
  ```diff
  - cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')
  + cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
  ```

#### HIGH · b602 — 1 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `.\security_samples/multilang/vuln_app.py:23`
- **Why it matters:** Using 'shell=True' in subprocess calls can lead to shell injection vulnerabilities when user inputs are involved.
- **How to fix:** Avoid using 'shell=True' unless necessary. If required, carefully validate and sanitize all inputs passed to the shell.
- **Example fix (illustrative):**
  ```diff
  - subprocess.run('ls -l ' + user_input, shell=True)
  + subprocess.run(['ls', '-l', user_input])
  ```

#### HIGH · b324 — 1 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `.\security_samples/multilang/vuln_app.py:38`
- **Why it matters:** Using the MD5 hashing algorithm for security-related purposes is weak, as it is vulnerable to collision attacks.
- **How to fix:** Replace MD5 with a stronger hashing algorithm such as SHA-256 or use `usedforsecurity=False` if MD5 is not used for security.
- **Example fix (illustrative):**
  ```diff
  - hashlib.md5(data).hexdigest()
  + hashlib.sha256(data).hexdigest()
  ```

#### HIGH · go.lang.security.injection.tainted-sql-string.tainted-sql-string — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\handler.go:16`
- **Why it matters:** Manually constructing SQL strings with user data increases the risk of SQL injection attacks, allowing attackers to manipulate queries.
- **How to fix:** Use prepared statements or an ORM to safely include user data in SQL queries.
- **Example fix (illustrative):**
  ```diff
  - db.Query('SELECT * FROM items WHERE name = ' + name)
  + db.Query('SELECT * FROM items WHERE name = ?', name)
  ```

#### HIGH · php.lang.security.injection.tainted-sql-string.tainted-sql-string — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\index.php:7`
- **Why it matters:** Inserting user input directly into SQL strings can lead to SQL injection vulnerabilities, permitting unauthorized data access.
- **How to fix:** Utilize prepared statements or an ORM to safeguard against SQL injection by avoiding raw SQL query construction.
- **Example fix (illustrative):**
  ```diff
  - $mysqli->query('SELECT * FROM users WHERE username = ' . $username)
  + $stmt = $mysqli->prepare('SELECT * FROM users WHERE username = ?'); $stmt->bind_param('s', $username); $stmt->execute();
  ```

#### HIGH · php.lang.security.injection.echoed-request.echoed-request — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\index.php:11`
- **Why it matters:** `Echo`ing user input risks cross-site scripting vulnerability. You should use `htmlentities()` when showing data to users. (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · php.lang.security.tainted-exec.tainted-exec — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\index.php:11`
- **Why it matters:** Executing non-constant commands. This can lead to command injection. You should use `escapeshellarg()` when using command. (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · javascript.lang.security.audit.code-string-concat.code-string-concat — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\multilang\server.js:26`
- **Why it matters:** Found data from an Express or Next web request flowing to `eval`. If this data is user-controllable this can lead to execution of arbitrary system commands in the context of your application process. Avoid `eval` whenever possible. (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · js/sql-injection — 1 occurrence(s) · P1
- **Scanners:** codeql
- **Where:** `security_samples/multilang/server.js:14`
- **Why it matters:** This query string depends on a [user-provided value](1). (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · hashicorp-tf-password — 1 occurrence(s) · P1
- **Scanners:** gitleaks
- **Where:** `security_samples/multilang/infra.tf:30`
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
- **Where:** `security_samples/multilang/infra.tf:31`
- **Why it matters:** RDS encryption has not been enabled at a DB Instance level. (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0180 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/multilang/infra.tf:32`
- **Why it matters:** RDS Publicly Accessible (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

### 📋 Other Findings — Standard Remediation (no AI)
60 lower-severity rule(s), each with standard guidance (deterministic, no LLM call):

| Severity | Rule | Count | How to fix |
|---|---|---|---|
| MEDIUM | `ckv_aws_23` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_24` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv2_aws_62` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv2_aws_5` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv2_aws_61` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_21` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_145` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_20` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_18` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_aws_144` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv2_aws_6` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_docker_2` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_docker_3` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ckv_secret_6` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `aws-0090` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `python.lang.security.insecure-hash-algorithms-md5.insecure-hash-algorithm-md5` | 1 | Replace the weak hash (MD5/SHA1) with SHA-256+ (bcrypt/Argon2 for passwords). |
| MEDIUM | `python.lang.security.audit.eval-detected.eval-detected` | 1 | Remove `eval()`. Use explicit parsing or a whitelist dispatch instead. |
| MEDIUM | `b608` | 1 | Possible SQL injection from string-built queries. Use parameterized queries / an ORM, never string concatenation. |
| MEDIUM | `b307` | 1 | Do not use `eval()`. Parse input explicitly (e.g. `ast.literal_eval` for literals) or dispatch on a whitelist. |
| MEDIUM | `go.lang.security.audit.database.string-formatted-query.string-formatted-query` | 1 | Review against secure-coding guidance for this rule and apply the standard fix (validate input, avoid dangerous APIs). |
| MEDIUM | `go.lang.security.audit.net.use-tls.use-tls` | 1 | Review against secure-coding guidance for this rule and apply the standard fix (validate input, avoid dangerous APIs). |
| MEDIUM | `php.lang.security.injection.tainted-exec.tainted-exec` | 1 | Review against secure-coding guidance for this rule and apply the standard fix (validate input, avoid dangerous APIs). |
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
| MEDIUM | `cve-2024-56326` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2025-27516` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `ds-0001` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `ds-0004` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| MEDIUM | `aws-0077` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |

_…and 10 more lower-severity rule(s)._

### 🛰️ Scanner Coverage
6/6 scanner(s) completed. A ❌ scanner ran but its result could not be collected — treat its coverage as unknown, not clean.

| Scanner | Status | Findings | Detail |
|---|---|---|---|
| bandit | ✅ ran | 7 | completed |
| semgrep | ✅ ran | 18 | completed |
| codeql | ✅ ran | 7 | completed |
| gitleaks | ✅ ran | 4 | completed |
| checkov | ✅ ran | 46 | completed |
| trivy | ✅ ran | 50 | completed |

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

### ❗ Remaining Findings (132)
- **py/command-line-injection** (CRITICAL, code) at `security_samples/multilang/vuln_app.py:23` — scanners: codeql — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Command-line injection vulnerabilities allow attackers to execute arbitrary commands on the host machine, potentially compromising the system._
  - **Suggested fix approach:** Always validate and sanitize user inputs before using them in command-line executions. Prefer using safer API methods or libraries.
  - **Suggested change:**
    ```diff
    --- security_samples/multilang/vuln_app.py
    +++ security_samples/multilang/vuln_app.py
    @@ -1,5 +1,5 @@
     def dangerous(expr: str):
    -    # Bandit B307 / Semgrep: eval on untrusted input
    -    return eval(expr)
    +    # Avoid using eval on untrusted input
    +    return safe_eval(expr)
     
    -def safe_eval(expr: str):
    +def safe_eval(expr: str):
         # Implement a safe evaluation of expressions here
         pass
    ```
- **python.flask.security.injection.subprocess-injection.subprocess-injection** (HIGH, code) at `security_samples\multilang\vuln_app.py:23` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using unsanitized user input in a subprocess call can lead to command injection vulnerabilities, allowing attackers to execute arbitrary commands._
  - **Suggested fix approach:** Avoid using user input directly in subprocess calls. If subprocess is necessary, restrict the commands by using allowlists or prefer Python APIs.
- **python.lang.security.dangerous-subprocess-use.dangerous-subprocess-use** (HIGH, code) at `security_samples\multilang\vuln_app.py:23` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using user-controlled data in the subprocess call can lead to command injection, exposing vulnerabilities in the application._
  - **Suggested fix approach:** Sanitize user input before passing it to subprocess calls. Consider using 'shlex.quote()' or similar functions to escape inputs.
- **python.lang.security.audit.subprocess-shell-true.subprocess-shell-true** (HIGH, code) at `security_samples\multilang\vuln_app.py:23` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Setting 'shell=True' in subprocess calls can expose the application to shell injection attacks by allowing attacker-controlled variables to be executed._
  - **Suggested fix approach:** Always set 'shell=False' when using subprocess to avoid executing commands through the shell.
- **python.flask.security.injection.tainted-sql-string.tainted-sql-string** (HIGH, code) at `security_samples\multilang\vuln_app.py:32` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Manually constructing SQL strings with user input increases the risk of SQL injection, which could allow unauthorized data access or manipulation._
  - **Suggested fix approach:** Use parameterized queries or ORM methods to safely handle user input when interacting with the database.
- **py/sql-injection** (HIGH, code) at `security_samples/multilang/vuln_app.py:32` — scanners: codeql — Advisory — see remediation guide.
  - **AI triage:** P1
  - _User inputs are directly included in SQL queries without proper sanitization, leading to potential SQL injection vulnerabilities._
  - **Suggested fix approach:** Use parameterized queries or an ORM to safely handle user inputs and prevent SQL injection.
- **python.lang.security.insecure-hash-algorithms-md5.insecure-hash-algorithm-md5** (MEDIUM, code) at `security_samples\multilang\vuln_app.py:38` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Detected MD5 hash algorithm which is considered insecure. MD5 is not collision resistant and is therefore not suitable as a cryptographic signature. Use SHA256 or SHA3 instead._
  - **Suggested fix approach:** Replace the weak hash (MD5/SHA1) with SHA-256+ (bcrypt/Argon2 for passwords).
- **python.lang.security.audit.eval-detected.eval-detected** (MEDIUM, code) at `security_samples\multilang\vuln_app.py:43` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P2
  - _Detected the use of eval(). eval() can be dangerous if used to evaluate dynamic content. If this content can be input from outside the program, this may be a code injection vulnerability. Ensure evaluated content is not definable by external sources._
  - **Suggested fix approach:** Remove `eval()`. Use explicit parsing or a whitelist dispatch instead.
- **js/command-line-injection** (CRITICAL, code) at `security_samples/multilang/server.js:21` — scanners: codeql — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Command-line injection vulnerabilities can lead to severe exploitation where an attacker gains control of the server environment._
  - **Suggested fix approach:** Ensure user inputs are sanitized and validated before passing them to command-line executions, and use safer alternatives when possible.
- **js/code-injection** (CRITICAL, code) at `security_samples/multilang/server.js:26` — scanners: codeql — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Code injection vulnerabilities can lead to arbitrary code execution, providing attackers with the ability to take control over the application._
  - **Suggested fix approach:** Do not execute dynamic code from user inputs. Instead, use safe parsing libraries that ensure only expected commands are executed.
- **cve-2019-20477** (CRITICAL, dependency) at `security_samples/multilang/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Vulnerabilities in libraries like PyYAML can lead to remote code execution through deserialization attacks, jeopardizing application security._
  - **Suggested fix approach:** Upgrade to the latest version of PyYAML that has addressed this vulnerability or switch to a safer library for YAML parsing.
- **cve-2020-14343** (CRITICAL, dependency) at `security_samples/multilang/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _The dependency PyYAML contains a security vulnerability that is not fully resolved, which can lead to data exposure or code execution in the application._
  - **Suggested fix approach:** Upgrade PyYAML to a version that fully addresses CVE-2020-14343. Consult the official PyYAML repository for the latest secure version.
- **cve-2020-1747** (CRITICAL, dependency) at `security_samples/multilang/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Using FullLoader with PyYAML can lead to arbitrary command execution, making the application vulnerable to attacks._
  - **Suggested fix approach:** Change the loading method to use safe loading alternatives, such as 'yaml.safe_load'. Avoid using FullLoader for untrusted input.
- **aws-0104** (CRITICAL, iac) at `security_samples/insecure_terraform.tf:37` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _A security group rule allowing unrestricted egress to any IP address poses a significant security risk, allowing outbound traffic to any destination._
  - **Suggested fix approach:** Restrict the egress rule to specific, validated IP addresses or services, or remove unnecessary egress rules.
- **ds-0031** (CRITICAL, iac) at `security_samples/multilang/Dockerfile:9` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Passing secrets via build arguments or environment variables can lead to exposure of sensitive data, especially when the data might be logged or viewed by unauthorized users._
  - **Suggested fix approach:** Remove secrets from build arguments and environment variables; use secure storage solutions, such as AWS Secrets Manager or Docker secrets.
- **aws-access-key-id** (CRITICAL, secret) at `security_samples/gitleaks_secrets.txt:7` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Exposing AWS Access Key IDs can grant unauthorized access to your AWS resources, leading to potential data breaches and security vulnerabilities._
  - **Suggested fix approach:** Remove hardcoded AWS Access Key IDs from the repository and use environment variables or AWS IAM roles for access management.
  - **Suggested change:**
    ```diff
    --- security_samples/gitleaks_secrets.txt
    +++ security_samples/gitleaks_secrets.txt
    @@ -6,7 +6,7 @@
     internal
     1234567890abcdef1234567890abcdef
     -AWS_ACCESS_KEY_ID: AKIAIOSFODNN7EXAMPLE
     +AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
    ```
- **aws-access-key-id** (CRITICAL, secret) at `security_samples/multilang/leaked_creds.env:7` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Exposing AWS Access Key IDs can grant unauthorized access to your AWS resources, leading to potential data breaches and security vulnerabilities._
  - **Suggested fix approach:** Remove hardcoded AWS Access Key IDs from the repository and use environment variables or AWS IAM roles for access management.
- **b602** (HIGH, code) at `.\security_samples/multilang/vuln_app.py:23` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using 'shell=True' in subprocess calls can lead to shell injection vulnerabilities when user inputs are involved._
  - **Suggested fix approach:** Avoid using 'shell=True' unless necessary. If required, carefully validate and sanitize all inputs passed to the shell.
- **b324** (HIGH, code) at `.\security_samples/multilang/vuln_app.py:38` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using the MD5 hashing algorithm for security-related purposes is weak, as it is vulnerable to collision attacks._
  - **Suggested fix approach:** Replace MD5 with a stronger hashing algorithm such as SHA-256 or use `usedforsecurity=False` if MD5 is not used for security.
- **javascript.lang.security.detect-child-process.detect-child-process** (HIGH, code) at `security_samples\multilang\api.ts:8` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using user-supplied input directly in child_process calls can lead to command injections, making the system susceptible to attacks._
  - **Suggested fix approach:** Sanitize or validate all user inputs before using them in child_process calls to prevent command injection vulnerabilities.
- **go.lang.security.injection.tainted-sql-string.tainted-sql-string** (HIGH, code) at `security_samples\multilang\handler.go:16` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Manually constructing SQL strings with user data increases the risk of SQL injection attacks, allowing attackers to manipulate queries._
  - **Suggested fix approach:** Use prepared statements or an ORM to safely include user data in SQL queries.
- **php.lang.security.injection.tainted-sql-string.tainted-sql-string** (HIGH, code) at `security_samples\multilang\index.php:7` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Inserting user input directly into SQL strings can lead to SQL injection vulnerabilities, permitting unauthorized data access._
  - **Suggested fix approach:** Utilize prepared statements or an ORM to safeguard against SQL injection by avoiding raw SQL query construction.
- **php.lang.security.injection.echoed-request.echoed-request** (HIGH, code) at `security_samples\multilang\index.php:11` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _`Echo`ing user input risks cross-site scripting vulnerability. You should use `htmlentities()` when showing data to users. (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **php.lang.security.tainted-exec.tainted-exec** (HIGH, code) at `security_samples\multilang\index.php:11` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Executing non-constant commands. This can lead to command injection. You should use `escapeshellarg()` when using command. (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **javascript.lang.security.detect-child-process.detect-child-process** (HIGH, code) at `security_samples\multilang\server.js:21` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using user-supplied input directly in child_process calls can lead to command injections, making the system susceptible to attacks._
  - **Suggested fix approach:** Sanitize or validate all user inputs before using them in child_process calls to prevent command injection vulnerabilities.
- **javascript.lang.security.audit.code-string-concat.code-string-concat** (HIGH, code) at `security_samples\multilang\server.js:26` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Found data from an Express or Next web request flowing to `eval`. If this data is user-controllable this can lead to execution of arbitrary system commands in the context of your application process. Avoid `eval` whenever possible. (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **js/sql-injection** (HIGH, code) at `security_samples/multilang/server.js:14` — scanners: codeql — Advisory — see remediation guide.
  - **AI triage:** P1
  - _This query string depends on a [user-provided value](1). (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **js/missing-rate-limiting** (HIGH, code) at `security_samples/multilang/server.js:10` — scanners: codeql — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Exposing a route handler without rate limiting allows an attacker to perform Denial of Service (DoS) attacks, overwhelming the server with requests._
  - **Suggested fix approach:** Implement rate limiting for the route handler to control the number of requests it can handle in a given timeframe.
- **js/missing-rate-limiting** (HIGH, code) at `security_samples/multilang/server.js:19` — scanners: codeql — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Exposing a route handler without rate limiting allows an attacker to perform Denial of Service (DoS) attacks, overwhelming the server with requests._
  - **Suggested fix approach:** Implement rate limiting for the route handler to control the number of requests it can handle in a given timeframe.
- **hashicorp-tf-password** (HIGH, secret) at `security_samples/multilang/infra.tf:30` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Identified a HashiCorp Terraform password field, risking unauthorized infrastructure configuration and security breaches. (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **generic-api-key** (HIGH, secret) at `security_samples/multilang/leaked_creds.env:11` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Generic API keys can grant unauthorized access to sensitive services or data, leading to data breaches or misuse of system resources._
  - **Suggested fix approach:** Replace the generic API key with a secure method for credentials management, such as environment variables or a secrets manager.
- **private-key** (HIGH, secret) at `security_samples/gitleaks_secrets.txt:17` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Private keys stored in code may allow unauthorized access to encrypted data and services, resulting in data leaks and security vulnerabilities._
  - **Suggested fix approach:** Remove private keys from the codebase and use secure vault or environment variables to manage them.
- **generic-api-key** (HIGH, secret) at `security_samples/gitleaks_secrets.txt:13` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Generic API keys can grant unauthorized access to sensitive services or data, leading to data breaches or misuse of system resources._
  - **Suggested fix approach:** Replace the generic API key with a secure method for credentials management, such as environment variables or a secrets manager.
- **cve-2019-10906** (HIGH, dependency) at `security_samples/multilang/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _python-jinja2: str.format_map allows sandbox escape (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **ds-0002** (HIGH, iac) at `security_samples/Dockerfile:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Running a Docker container as the root user presents a significant security risk, as it could lead to privilege escalation and system compromise._
  - **Suggested fix approach:** Specify a non-root user in the Dockerfile to limit the privileges of container processes.
- **aws-0086** (HIGH, iac) at `security_samples/insecure_terraform.tf:14` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Allowing public access to S3 buckets can expose sensitive data to the internet, leading to potential data breaches._
  - **Suggested fix approach:** Update the S3 bucket policy to block public ACLs and use private settings by default.
- **aws-0087** (HIGH, iac) at `security_samples/insecure_terraform.tf:15` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Public access to S3 buckets can lead to sensitive data leakage. A proper access block policy ensures that unintended public access is restricted._
  - **Suggested fix approach:** Update the S3 bucket policy to explicitly deny public access by ensuring the 'BlockPublicAcls' setting is applied.
- **aws-0091** (HIGH, iac) at `security_samples/insecure_terraform.tf:16` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Ignoring public ACLs is crucial to avoid allowing public access through misconfigured bucket permissions._
  - **Suggested fix approach:** Set the 'IgnorePublicAcls' parameter to true in the S3 bucket settings to prevent public access through ACLs.
- **aws-0092** (HIGH, iac) at `security_samples/insecure_terraform.tf:8` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 buckets should be configured to avoid public access through ACL settings to protect sensitive data stored in them._
  - **Suggested fix approach:** Ensure the S3 bucket's ACL is set to private or a restrictive setting to prevent public access.
- **aws-0093** (HIGH, iac) at `security_samples/insecure_terraform.tf:17` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Restricting public bucket access limits data exposure to unauthorized users and helps maintain confidentiality._
  - **Suggested fix approach:** Adjust the S3 bucket policy to include stricter permissions and limit public accessibility only to necessary resources.
- **aws-0107** (HIGH, iac) at `security_samples/insecure_terraform.tf:29` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Unrestricted ingress rules for SSH/RDP increase the attack surface of your instances, making it easier for attackers to gain access._
  - **Suggested fix approach:** Restrict ingress rules for SSH or RDP to known IP addresses or ranges only, rather than allowing access from anywhere.
- **aws-0132** (HIGH, iac) at `security_samples/insecure_terraform.tf:5` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using Customer Managed Keys (CMKs) for S3 encryption enhances security by allowing more control over the encryption process and key management._
  - **Suggested fix approach:** Ensure that all S3 buckets defined in your infrastructure as code (IAC) use Customer Managed Keys for encryption instead of default or no encryption.
- **ds-0002** (HIGH, iac) at `security_samples/multilang/Dockerfile:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Running a Docker container as the root user presents a significant security risk, as it could lead to privilege escalation and system compromise._
  - **Suggested fix approach:** Specify a non-root user in the Dockerfile to limit the privileges of container processes.
- **ds-0029** (HIGH, iac) at `security_samples/multilang/Dockerfile:6` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _'apt-get' missing '--no-install-recommends' (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0080** (HIGH, iac) at `security_samples/multilang/infra.tf:31` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _RDS encryption has not been enabled at a DB Instance level. (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **aws-0086** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Allowing public access to S3 buckets can expose sensitive data to the internet, leading to potential data breaches._
  - **Suggested fix approach:** Update the S3 bucket policy to block public ACLs and use private settings by default.
- **aws-0087** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Public access to S3 buckets can lead to sensitive data leakage. A proper access block policy ensures that unintended public access is restricted._
  - **Suggested fix approach:** Update the S3 bucket policy to explicitly deny public access by ensuring the 'BlockPublicAcls' setting is applied.
- **aws-0091** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Ignoring public ACLs is crucial to avoid allowing public access through misconfigured bucket permissions._
  - **Suggested fix approach:** Set the 'IgnorePublicAcls' parameter to true in the S3 bucket settings to prevent public access through ACLs.
- **aws-0092** (HIGH, iac) at `security_samples/multilang/infra.tf:21` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _S3 buckets should be configured to avoid public access through ACL settings to protect sensitive data stored in them._
  - **Suggested fix approach:** Ensure the S3 bucket's ACL is set to private or a restrictive setting to prevent public access.
- **aws-0093** (HIGH, iac) at `security_samples/multilang/infra.tf:19` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Restricting public bucket access limits data exposure to unauthorized users and helps maintain confidentiality._
  - **Suggested fix approach:** Adjust the S3 bucket policy to include stricter permissions and limit public accessibility only to necessary resources.
- _…and 82 more (showing the 50 highest-risk findings; see the severity breakdown above for the full distribution)._

_The final merge decision is left to a human reviewer; this report is advisory and does not trigger a merge._
