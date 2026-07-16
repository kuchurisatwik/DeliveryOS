# AI Software Delivery Engineer: Architecture Review

**Repository:** kuchurisatwik/DeliveryOS
**Commit SHA:** 30819b0132e7493ebeecbc05b3ed725558aa521c
**Branch:** ai-sde/review-30819b0-20260716141920
**Timestamp:** 2026-07-16T14:21:23.669161Z

No AI analysis was generated.

---
## 🔒 Security Pipeline Report
**Commit:** [`30819b0132`](https://github.com/kuchurisatwik/DeliveryOS/commit/30819b0132e7493ebeecbc05b3ed725558aa521c)
**Repository:** `kuchurisatwik/DeliveryOS`
**Branch under review:** `feat/security-pipeline`
**Security Summary:** 0 finding(s) fixed; 108 finding(s) remaining; quality gate failed.
**Scanned scope:** 12 changed file(s).

**Findings by severity:** CRITICAL: 11, HIGH: 48, MEDIUM: 40, LOW: 9

### 🛠️ Remediation Guide — Key High/Critical Findings
The 54 highest-severity rule(s) below account for the key risk in this change. Each fix applies to all listed occurrences. CRITICAL rules include a concrete patch; HIGH rules include an illustrative before/after.

#### CRITICAL · cve-2019-14234 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** This vulnerability in Django allows for SQL injection due to improper handling of key and index lookups in JSONField and HStoreField, potentially exposing sensitive data.
- **How to fix:** Upgrade Django to a version where this vulnerability is patched. Avoid using JSONField and HStoreField without proper input validation.
- **Suggested patch:**
  ```diff
  --- security_samples/requirements.txt
  +++ security_samples/requirements.txt
  @@ -1,0 +1,1 @@
  +django >= 3.0, < 4.0
  ```

#### CRITICAL · cve-2019-19844 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** This vulnerability can lead to account takeover by allowing crafted email addresses to bypass authentication or other security checks.
- **How to fix:** Upgrade Django to a secure version. Implement additional validation to sanitize email inputs.
- **Suggested patch:**
  ```diff
  --- security_samples/requirements.txt
  +++ security_samples/requirements.txt
  @@ -1 +1 @@
  -Django==2.2.0
  +Django>=2.2.10,<3.0.0
  ```

#### CRITICAL · cve-2020-7471 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** The vulnerability allows SQL injection via unsanitized input to StringAgg, potentially exposing the database to malicious queries.
- **How to fix:** Upgrade to the latest Django version and ensure any input to StringAgg is properly sanitized.
- **Suggested patch:**
  ```diff
  --- security_samples/requirements.txt
  +++ security_samples/requirements.txt
  @@ -1 +1 @@
  -Django
  +Django<4.0
  ```

#### CRITICAL · cve-2022-28346 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** SQL injection can be executed through QuerySet.annotate(), aggregate(), and extra() if user inputs are not properly validated.
- **How to fix:** Update Django to the latest version to patch this issue. Always validate and sanitize input parameters for these methods.
- **Suggested patch:**
  ```diff
  --- security_samples/requirements.txt
  +++ security_samples/requirements.txt
  @@ -1 +1 @@
  -Django==2.2.0
  +Django>=2.2.0,<3.0.0
  ```

#### CRITICAL · cve-2022-28347 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** This vulnerability permits SQL injection via the QuerySet.explain method, especially when used with PostgreSQL.
- **How to fix:** Ensure Django is updated to a secure version and validate any input used in the explain method.
- **Suggested patch:**
  ```diff
  --- security_samples/requirements.txt
  +++ security_samples/requirements.txt
  @@ -1,3 +1,3 @@
  -Django==<vulnerable_version>
  +Django>=<fixed_version>
   # Other dependencies
  ```

#### CRITICAL · cve-2025-64459 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** The version of Django in use is vulnerable to SQL injection, which could allow an attacker to execute arbitrary SQL commands.
- **How to fix:** Upgrade Django to a secure version that addresses this vulnerability.
- **Example fix (illustrative):**
  ```diff
  - queryset = MyModel.objects.raw('SELECT * FROM mymodel WHERE id = ' + user_input_id)
  + queryset = MyModel.objects.raw('SELECT * FROM mymodel WHERE id = %s', [user_input_id])
  ```

#### CRITICAL · cve-2019-20477 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** The version of PyYAML being used is susceptible to remote code execution through insecure deserialization.
- **How to fix:** Upgrade PyYAML to a fixed version and avoid using FullLoader when loading YAML data.
- **Example fix (illustrative):**
  ```diff
  - data = yaml.load(yaml_string, Loader=yaml.FullLoader)
  + data = yaml.safe_load(yaml_string)
  ```

#### CRITICAL · cve-2020-14343 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** PyYAML contains an incomplete fix for a previous vulnerability that could still allow for code execution risks.
- **How to fix:** Ensure you are using the latest version of PyYAML that resolves this vulnerability completely.
- **Example fix (illustrative):**
  ```diff
  - data = yaml.load(yaml_string, Loader=yaml.FullLoader)
  + data = yaml.safe_load(yaml_string)
  ```

#### CRITICAL · cve-2020-1747 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Using FullLoader in PyYAML allows arbitrary command execution via untrusted YAML input.
- **How to fix:** Switch to using safe_load or ensure any YAML data is sanitized before loading.
- **Example fix (illustrative):**
  ```diff
  - data = yaml.load(yaml_string, Loader=yaml.FullLoader)
  + data = yaml.safe_load(yaml_string)
  ```

#### CRITICAL · aws-0104 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:37`
- **Why it matters:** Unrestricted egress rules in security groups may expose resources to potential attacks from any IP address.
- **How to fix:** Restrict egress rules to known IP addresses or CIDR ranges as per your security policy.
- **Example fix (illustrative):**
  ```diff
  - resource "aws_security_group" "example" { rules { egress { from_port = 0 to_port = 0 protocol = "-1" cidr_blocks = ["0.0.0.0/0"] } } } }
  + resource "aws_security_group" "example" { rules { egress { from_port = 0 to_port = 0 protocol = "-1" cidr_blocks = ["192.168.1.0/24"] } } } }
  ```

#### CRITICAL · aws-access-key-id — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/gitleaks_secrets.txt:7`
- **Why it matters:** Exposing AWS Access Key IDs can lead to unauthorized access to AWS resources. Malicious actors can use these credentials to gain control over your cloud infrastructure, leading to data breaches and financial loss.
- **How to fix:** Remove hardcoded AWS Access Key IDs and consider using AWS Identity and Access Management (IAM) roles to manage credentials securely. Store sensitive information in environment variables or secure vaults.
- **Example fix (illustrative):**
  ```diff
  - AWS_ACCESS_KEY_ID = 'AKIAxxxxxxxxxxxx'
  + AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
  ```

#### HIGH · b605 — 3 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `.\security_samples/bandit_samples.py:36, .\security_samples/codeql_taintflow.py:36, .\security_samples/semgrep_samples.py:39`
- **Why it matters:** Starting a process with a shell can lead to command injection vulnerabilities. If untrusted input is included, attackers can execute arbitrary commands, causing severe impacts on application integrity and security.
- **How to fix:** Use the `subprocess` module without `shell=True`. Pass command arguments as a list to prevent shell injection vulnerabilities.
- **Example fix (illustrative):**
  ```diff
  - subprocess.call('ls -l', shell=True)
  + subprocess.call(['ls', '-l'])
  ```

#### HIGH · python.lang.security.audit.subprocess-shell-true.subprocess-shell-true — 2 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\bandit_samples.py:31, security_samples\semgrep_samples.py:34`
- **Why it matters:** Using 'shell=True' in subprocess calls can expose the application to shell injection vulnerabilities. It allows the risk of executing unintended commands if user input is not properly validated.
- **How to fix:** Always pass arguments in a list and set `shell=False` to avoid unintended command execution.
- **Example fix (illustrative):**
  ```diff
  - subprocess.call(command, shell=True)
  + subprocess.call(command, shell=False)
  ```

#### HIGH · b602 — 2 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `.\security_samples/bandit_samples.py:31, .\security_samples/semgrep_samples.py:34`
- **Why it matters:** Using 'shell=True' in subprocess calls may lead to security issues, where an attacker can exploit command injection vulnerabilities, potentially compromising the system.
- **How to fix:** Refactor code to avoid using `shell=True` in subprocess calls. Provide the command and its arguments as a list instead.
- **Example fix (illustrative):**
  ```diff
  - subprocess.call('echo $USER', shell=True)
  + subprocess.call(['echo', os.getenv('USER')])
  ```

#### HIGH · private-key — 2 occurrence(s) · P1
- **Scanners:** gitleaks, trivy
- **Where:** `security_samples/gitleaks_secrets.txt:17, security_samples/gitleaks_secrets.txt:18`
- **Why it matters:** Hardcoded private keys can compromise cryptographic integrity, allowing attackers to decrypt sensitive data or impersonate users. This can lead to severe security breaches.
- **How to fix:** Avoid hardcoding private keys in your source code. Use secure storage solutions like environment variables or secret management services to store sensitive keys securely.
- **Example fix (illustrative):**
  ```diff
  - PRIVATE_KEY = '-----BEGIN PRIVATE KEY-----\n...'
  + PRIVATE_KEY = os.getenv('PRIVATE_KEY')
  ```

#### HIGH · python.requests.security.disabled-cert-validation.disabled-cert-validation — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\semgrep_samples.py:44`
- **Why it matters:** Disabling certificate verification undermines the integrity and authenticity of connections, exposing the application to man-in-the-middle attacks.
- **How to fix:** Re-enable SSL certificate validation by ensuring the 'verify' parameter in the requests library is set to True.
- **Example fix (illustrative):**
  ```diff
  - response = requests.get('https://example.com', verify=False)
  + response = requests.get('https://example.com', verify=True)
  ```

#### HIGH · py/clear-text-storage-sensitive-data — 1 occurrence(s) · P1
- **Scanners:** codeql
- **Where:** `security_samples/bandit_samples.py:58`
- **Why it matters:** Storing sensitive data in clear text allows unauthorized access to sensitive information, increasing the risk of data breaches.
- **How to fix:** Use secure storage mechanisms such as encryption when handling sensitive data.
- **Example fix (illustrative):**
  ```diff
  - password = 'my_secure_password'
  + encrypted_password = encrypt('my_secure_password')
  ```

#### HIGH · py/weak-sensitive-data-hashing — 1 occurrence(s) · P1
- **Scanners:** codeql
- **Where:** `security_samples/bandit_samples.py:51`
- **Why it matters:** Using weak hashing algorithms like MD5 for sensitive data (e.g., passwords) exposes stored data to vulnerabilities such as collision attacks.
- **How to fix:** Switch to stronger hashing algorithms like bcrypt or Argon2 for securely hashing sensitive data.
- **Example fix (illustrative):**
  ```diff
  - hashed_password = hashlib.md5(password.encode()).hexdigest()
  + hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
  ```

#### HIGH · b324 — 1 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `.\security_samples/bandit_samples.py:51`
- **Why it matters:** The use of the MD5 hash function is considered insecure and could lead to compromised data integrity.
- **How to fix:** Avoid using MD5 for any security-related functions; prefer SHA-256 or stronger hashing algorithms.
- **Example fix (illustrative):**
  ```diff
  - hash_value = hashlib.md5(data).hexdigest()
  + hash_value = hashlib.sha256(data).hexdigest()
  ```

#### HIGH · b501 — 1 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `.\security_samples/semgrep_samples.py:44`
- **Why it matters:** Disabling SSL certificate checks by setting verify=False allows connections to be made without validating the server's certificate, making it vulnerable to eavesdropping.
- **How to fix:** Ensure SSL certificate verification is enabled by setting 'verify' to True in requests.
- **Example fix (illustrative):**
  ```diff
  - response = requests.get('https://example.com', verify=False)
  + response = requests.get('https://example.com', verify=True)
  ```

#### HIGH · generic-api-key — 1 occurrence(s) · P1
- **Scanners:** gitleaks
- **Where:** `security_samples/gitleaks_secrets.txt:13`
- **Why it matters:** Detected a Generic API Key, potentially exposing access to various services and sensitive operations.
- **How to fix:** Remove the hardcoded API key from the source code and utilize environment variables or a secure vault service to safely manage sensitive information.
- **Example fix (illustrative):**
  ```diff
  - API_KEY = 'my-secret-api-key'
  + API_KEY = os.environ.get('MY_SECRET_API_KEY')
  ```

#### HIGH · cve-2019-14232 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Django: backtracking in a regular expression in django.utils.text.Truncator leads to DoS.
- **How to fix:** Update Django to a version that has fixed this vulnerability to prevent Denial of Service through regex backtracking.
- **Example fix (illustrative):**
  ```diff
  - from django.utils.text import Truncator
  - truncator = Truncator('Some very long string...')
  - truncator.truncate_words(5)
  + from django.utils.text import Truncator
  + truncator = Truncator('Some very long string...')
  + truncator.truncate_words(5, safe=True)
  ```

#### HIGH · cve-2019-14233 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Django: the behavior of the underlying HTMLParser leading to DoS.
- **How to fix:** Upgrade to a Django version where this behavior is mitigated or use alternate methods of HTML parsing.
- **Example fix (illustrative):**
  ```diff
  - from django.utils.html import escape
  - escaped = escape('<script>alert(1);</script>')
  + from django.utils.html import escape
  + escaped = escape('<safe_tag>')
  ```

#### HIGH · cve-2019-14235 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Django: Potential memory exhaustion in django.utils.encoding.uri_to_iri().
- **How to fix:** Ensure the Django version is recent, addressing the vulnerability, or restrict the data processed to avoid potential memory issues.
- **Example fix (illustrative):**
  ```diff
  - from django.utils.encoding import uri_to_iri
  - result = uri_to_iri('http://example.com')
  + from django.utils.encoding import uri_to_iri
  + result = uri_to_iri('http://example.com/valid-path')
  ```

#### HIGH · cve-2019-19118 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Django: privilege escalation in the django admin.
- **How to fix:** Update Django to a patched version to fix the privilege escalation vulnerability in the admin interface.
- **Example fix (illustrative):**
  ```diff
  - from django.contrib import admin
  - admin.site.register(MyModel)
  + from django.contrib import admin
  + admin.site.register(MyModel, MyModelAdmin)
  ```

#### HIGH · cve-2020-13254 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Malformed memcached keys can lead to unintended data exposure as sensitive information might be stored under incorrect keys.
- **How to fix:** Ensure that memcached keys are properly validated to prevent malformed inputs.
- **Example fix (illustrative):**
  ```diff
  - cache.set(memcached_key, data)
  + if is_valid_key(memcached_key): cache.set(memcached_key, data)
  ```

#### HIGH · cve-2020-24583 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Incorrect permissions on intermediate directories can expose sensitive files, allowing unauthorized access.
- **How to fix:** Review and set correct permissions for all directories, ensuring they restrict access appropriately.
- **Example fix (illustrative):**
  ```diff
  - os.makedirs(directory_path, exist_ok=True)
  + os.makedirs(directory_path, mode=0o750, exist_ok=True)
  ```

#### HIGH · cve-2020-9402 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** SQL injection vulnerabilities allow attackers to manipulate database queries through unvalidated parameters.
- **How to fix:** Use parameterized queries to safely handle inputs for SQL operations.
- **Example fix (illustrative):**
  ```diff
  - result = db.execute("SELECT * FROM table WHERE tolerance = '" + tolerance_value + "'")
  + result = db.execute("SELECT * FROM table WHERE tolerance = ?", (tolerance_value,))
  ```

#### HIGH · cve-2021-31542 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Directory traversal vulnerabilities permit unauthorized file access through crafted file paths.
- **How to fix:** Validate and sanitize file uploads to prevent directory traversal before processing them.
- **Example fix (illustrative):**
  ```diff
  - uploaded_file.save(os.path.join(upload_folder, file_name))
  + if is_safe_path(upload_folder, file_name): uploaded_file.save(os.path.join(upload_folder, file_name))
  ```

#### HIGH · cve-2021-33571 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Indeterminate SSRF, RFI, and LFI attacks can occur when input validation allows unexpected formats.
- **How to fix:** Implement stringent validation for IPv4 addresses to prevent leading zeros and other malicious inputs.
- **Example fix (illustrative):**
  ```diff
  - ip_address = user_input
  + if is_valid_ipv4(ip_address): ip_address = user_input
  ```

#### HIGH · cve-2021-45115 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** django: Denial-of-service possibility in UserAttributeSimilarityValidator (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · cve-2021-45116 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** django: Potential information disclosure in dictsort template filter (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · cve-2022-23833 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** django: Denial-of-service possibility in file uploads (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · cve-2022-36359 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** An issue was discovered in the HTTP FileResponse class in Django 3.2 b ... (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · cve-2025-57833 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** django: Django SQL injection in FilteredRelation column aliases (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · cve-2025-64458 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Django: Denial-of-service vulnerability in Django on Windows (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · cve-2018-1000656 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** python-flask: Denial of Service via crafted JSON file (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · cve-2019-1010083 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** python-flask: unexpected memory usage can lead to denial of service via crafted encoded JSON data (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · cve-2023-30861 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** flask: Possible disclosure of permanent session cookie due to missing Vary: Cookie header (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · cve-2018-18074 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** python-requests: Redirect from HTTPS to HTTP does not remove Authorization header (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · cve-2019-11324 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** python-urllib3: Certification mishandle when error should be thrown (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · cve-2023-43804 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** python-urllib3: Cookie request header isn't stripped during cross-origin redirects (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · cve-2025-66418 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** urllib3: urllib3: Unbounded decompression chain leads to resource exhaustion (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · cve-2025-66471 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** urllib3: urllib3 Streaming API improperly handles highly compressed data (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · cve-2026-21441 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** urllib3: urllib3 vulnerable to decompression-bomb safeguard bypass when following HTTP redirects (streaming API) (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · cve-2026-44431 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** urllib3: urllib3: Information disclosure via cross-origin redirects forwarding sensitive headers (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · ds-0002 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/Dockerfile:0`
- **Why it matters:** Image user should not be 'root' (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0086 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:14`
- **Why it matters:** S3 Access block should block public ACL (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0087 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:15`
- **Why it matters:** S3 Access block should block public policy (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0091 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:16`
- **Why it matters:** S3 Access Block should Ignore Public ACL (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0092 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:8`
- **Why it matters:** S3 Buckets not publicly accessible through ACL. (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0093 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:17`
- **Why it matters:** S3 Access block should restrict public bucket to limit access (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0107 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:29`
- **Why it matters:** Security groups should not allow unrestricted ingress to SSH or RDP from any IP address. (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

#### HIGH · aws-0132 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:5`
- **Why it matters:** S3 encryption should use Customer Managed Keys (beyond AI call budget — manual review recommended)
- **How to fix:** Review this rule against secure-coding guidance and remediate.

### 📋 Other Findings — Standard Remediation (no AI)
44 lower-severity rule(s), each with standard guidance (deterministic, no LLM call):

| Severity | Rule | Count | How to fix |
|---|---|---|---|
| MEDIUM | `b608` | 3 | Possible SQL injection from string-built queries. Use parameterized queries / an ORM, never string concatenation. |
| MEDIUM | `b113` | 2 | Set an explicit timeout on network requests to avoid indefinite hangs (e.g. `requests.get(..., timeout=10)`). |
| MEDIUM | `python.lang.security.audit.eval-detected.eval-detected` | 1 | Remove `eval()`. Use explicit parsing or a whitelist dispatch instead. |
| MEDIUM | `python.lang.security.audit.exec-detected.exec-detected` | 1 | Remove `exec()`. Call the intended logic directly. |
| MEDIUM | `python.lang.security.deserialization.pickle.avoid-pickle` | 1 | Do not deserialize untrusted data with pickle. Use JSON or a schema-validated format. |
| MEDIUM | `python.lang.security.insecure-hash-algorithms-md5.insecure-hash-algorithm-md5` | 1 | Replace the weak hash (MD5/SHA1) with SHA-256+ (bcrypt/Argon2 for passwords). |
| MEDIUM | `python.lang.security.audit.md5-used-as-password.md5-used-as-password` | 1 | MD5 is broken. Use SHA-256+ for integrity and bcrypt/scrypt/Argon2 for passwords. |
| MEDIUM | `b307` | 1 | Do not use `eval()`. Parse input explicitly (e.g. `ast.literal_eval` for literals) or dispatch on a whitelist. |
| MEDIUM | `b102` | 1 | Do not use `exec()`. Refactor to call the intended function/logic directly. |
| MEDIUM | `b301` | 1 | Do not `pickle.loads()` untrusted data — it enables arbitrary code execution. Use JSON or a safe serializer. |
| MEDIUM | `b506` | 1 | Do not use `yaml.load()` without a safe loader. Use `yaml.safe_load()`. |
| MEDIUM | `b108` | 1 | Avoid predictable temp paths like /tmp/x. Use `tempfile.mkstemp()`/`NamedTemporaryFile`. |
| MEDIUM | `cve-2019-11358` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2019-12308` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2019-12781` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2020-13596` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2020-24584` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2021-28658` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2021-32052` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2021-3281` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2021-33203` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2021-44420` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2021-45452` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2022-22818` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2024-45231` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2025-48432` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2023-32681` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2024-35195` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2024-47081` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2026-25645` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2018-25091` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2019-11236` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2020-26137` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2023-45803` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2024-37891` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `cve-2025-50181` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| MEDIUM | `aws-0090` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| LOW | `b404` | 2 | Importing `subprocess` is fine, but never call it with `shell=True` on untrusted input; pass an argument list. |
| LOW | `aws-0124` | 2 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| LOW | `b403` | 1 | Importing `pickle`/`marshal` is risky. Prefer JSON; never deserialize untrusted data with them. |
| LOW | `b105` | 1 | Remove hardcoded passwords/secrets. Load them from environment variables or a secrets manager. |
| LOW | `cve-2026-27205` | 1 | Upgrade the affected package to a patched version that resolves this advisory. |
| LOW | `ds-0026` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |
| LOW | `aws-0089` | 1 | Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled. |

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
- `max_leaked_secrets`: expected <= 0, actual 4
- `max_blocking_iac_issues`: expected <= 0, actual 9
- `min_coverage_percent`: expected >= 90.0, actual 0.0

### ✅ Fixed Findings (0)
None.

### ❗ Remaining Findings (108)
- **python.lang.security.audit.subprocess-shell-true.subprocess-shell-true** (HIGH, code) at `security_samples\bandit_samples.py:31` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using 'shell=True' in subprocess calls can expose the application to shell injection vulnerabilities. It allows the risk of executing unintended commands if user input is not properly validated._
  - **Suggested fix approach:** Always pass arguments in a list and set `shell=False` to avoid unintended command execution.
- **python.lang.security.audit.subprocess-shell-true.subprocess-shell-true** (HIGH, code) at `security_samples\semgrep_samples.py:34` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using 'shell=True' in subprocess calls can expose the application to shell injection vulnerabilities. It allows the risk of executing unintended commands if user input is not properly validated._
  - **Suggested fix approach:** Always pass arguments in a list and set `shell=False` to avoid unintended command execution.
- **python.requests.security.disabled-cert-validation.disabled-cert-validation** (HIGH, code) at `security_samples\semgrep_samples.py:44` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Disabling certificate verification undermines the integrity and authenticity of connections, exposing the application to man-in-the-middle attacks._
  - **Suggested fix approach:** Re-enable SSL certificate validation by ensuring the 'verify' parameter in the requests library is set to True.
- **py/clear-text-storage-sensitive-data** (HIGH, code) at `security_samples/bandit_samples.py:58` — scanners: codeql — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Storing sensitive data in clear text allows unauthorized access to sensitive information, increasing the risk of data breaches._
  - **Suggested fix approach:** Use secure storage mechanisms such as encryption when handling sensitive data.
- **py/weak-sensitive-data-hashing** (HIGH, code) at `security_samples/bandit_samples.py:51` — scanners: codeql — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using weak hashing algorithms like MD5 for sensitive data (e.g., passwords) exposes stored data to vulnerabilities such as collision attacks._
  - **Suggested fix approach:** Switch to stronger hashing algorithms like bcrypt or Argon2 for securely hashing sensitive data.
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
- **python.lang.security.audit.md5-used-as-password.md5-used-as-password** (MEDIUM, code) at `security_samples\bandit_samples.py:51` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P2
  - _It looks like MD5 is used as a password hash. MD5 is not considered a secure password hash because it can be cracked by an attacker in a short amount of time. Use a suitable password hashing function such as scrypt. You can use `hashlib.scrypt`._
  - **Suggested fix approach:** MD5 is broken. Use SHA-256+ for integrity and bcrypt/scrypt/Argon2 for passwords.
- **cve-2019-14234** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _This vulnerability in Django allows for SQL injection due to improper handling of key and index lookups in JSONField and HStoreField, potentially exposing sensitive data._
  - **Suggested fix approach:** Upgrade Django to a version where this vulnerability is patched. Avoid using JSONField and HStoreField without proper input validation.
  - **Suggested change:**
    ```diff
    --- security_samples/requirements.txt
    +++ security_samples/requirements.txt
    @@ -1,0 +1,1 @@
    +django >= 3.0, < 4.0
    ```
- **cve-2019-19844** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _This vulnerability can lead to account takeover by allowing crafted email addresses to bypass authentication or other security checks._
  - **Suggested fix approach:** Upgrade Django to a secure version. Implement additional validation to sanitize email inputs.
  - **Suggested change:**
    ```diff
    --- security_samples/requirements.txt
    +++ security_samples/requirements.txt
    @@ -1 +1 @@
    -Django==2.2.0
    +Django>=2.2.10,<3.0.0
    ```
- **cve-2020-7471** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _The vulnerability allows SQL injection via unsanitized input to StringAgg, potentially exposing the database to malicious queries._
  - **Suggested fix approach:** Upgrade to the latest Django version and ensure any input to StringAgg is properly sanitized.
  - **Suggested change:**
    ```diff
    --- security_samples/requirements.txt
    +++ security_samples/requirements.txt
    @@ -1 +1 @@
    -Django
    +Django<4.0
    ```
- **cve-2022-28346** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _SQL injection can be executed through QuerySet.annotate(), aggregate(), and extra() if user inputs are not properly validated._
  - **Suggested fix approach:** Update Django to the latest version to patch this issue. Always validate and sanitize input parameters for these methods.
  - **Suggested change:**
    ```diff
    --- security_samples/requirements.txt
    +++ security_samples/requirements.txt
    @@ -1 +1 @@
    -Django==2.2.0
    +Django>=2.2.0,<3.0.0
    ```
- **cve-2022-28347** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _This vulnerability permits SQL injection via the QuerySet.explain method, especially when used with PostgreSQL._
  - **Suggested fix approach:** Ensure Django is updated to a secure version and validate any input used in the explain method.
  - **Suggested change:**
    ```diff
    --- security_samples/requirements.txt
    +++ security_samples/requirements.txt
    @@ -1,3 +1,3 @@
    -Django==<vulnerable_version>
    +Django>=<fixed_version>
     # Other dependencies
    ```
- **cve-2025-64459** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _The version of Django in use is vulnerable to SQL injection, which could allow an attacker to execute arbitrary SQL commands._
  - **Suggested fix approach:** Upgrade Django to a secure version that addresses this vulnerability.
- **cve-2019-20477** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _The version of PyYAML being used is susceptible to remote code execution through insecure deserialization._
  - **Suggested fix approach:** Upgrade PyYAML to a fixed version and avoid using FullLoader when loading YAML data.
- **cve-2020-14343** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _PyYAML contains an incomplete fix for a previous vulnerability that could still allow for code execution risks._
  - **Suggested fix approach:** Ensure you are using the latest version of PyYAML that resolves this vulnerability completely.
- **cve-2020-1747** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Using FullLoader in PyYAML allows arbitrary command execution via untrusted YAML input._
  - **Suggested fix approach:** Switch to using safe_load or ensure any YAML data is sanitized before loading.
- **aws-0104** (CRITICAL, iac) at `security_samples/insecure_terraform.tf:37` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Unrestricted egress rules in security groups may expose resources to potential attacks from any IP address._
  - **Suggested fix approach:** Restrict egress rules to known IP addresses or CIDR ranges as per your security policy.
- **aws-access-key-id** (CRITICAL, secret) at `security_samples/gitleaks_secrets.txt:7` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Exposing AWS Access Key IDs can lead to unauthorized access to AWS resources. Malicious actors can use these credentials to gain control over your cloud infrastructure, leading to data breaches and financial loss._
  - **Suggested fix approach:** Remove hardcoded AWS Access Key IDs and consider using AWS Identity and Access Management (IAM) roles to manage credentials securely. Store sensitive information in environment variables or secure vaults.
- **b602** (HIGH, code) at `.\security_samples/bandit_samples.py:31` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using 'shell=True' in subprocess calls may lead to security issues, where an attacker can exploit command injection vulnerabilities, potentially compromising the system._
  - **Suggested fix approach:** Refactor code to avoid using `shell=True` in subprocess calls. Provide the command and its arguments as a list instead.
- **b605** (HIGH, code) at `.\security_samples/bandit_samples.py:36` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Starting a process with a shell can lead to command injection vulnerabilities. If untrusted input is included, attackers can execute arbitrary commands, causing severe impacts on application integrity and security._
  - **Suggested fix approach:** Use the `subprocess` module without `shell=True`. Pass command arguments as a list to prevent shell injection vulnerabilities.
- **b324** (HIGH, code) at `.\security_samples/bandit_samples.py:51` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _The use of the MD5 hash function is considered insecure and could lead to compromised data integrity._
  - **Suggested fix approach:** Avoid using MD5 for any security-related functions; prefer SHA-256 or stronger hashing algorithms.
- **b605** (HIGH, code) at `.\security_samples/codeql_taintflow.py:36` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Starting a process with a shell can lead to command injection vulnerabilities. If untrusted input is included, attackers can execute arbitrary commands, causing severe impacts on application integrity and security._
  - **Suggested fix approach:** Use the `subprocess` module without `shell=True`. Pass command arguments as a list to prevent shell injection vulnerabilities.
- **b602** (HIGH, code) at `.\security_samples/semgrep_samples.py:34` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using 'shell=True' in subprocess calls may lead to security issues, where an attacker can exploit command injection vulnerabilities, potentially compromising the system._
  - **Suggested fix approach:** Refactor code to avoid using `shell=True` in subprocess calls. Provide the command and its arguments as a list instead.
- **b605** (HIGH, code) at `.\security_samples/semgrep_samples.py:39` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Starting a process with a shell can lead to command injection vulnerabilities. If untrusted input is included, attackers can execute arbitrary commands, causing severe impacts on application integrity and security._
  - **Suggested fix approach:** Use the `subprocess` module without `shell=True`. Pass command arguments as a list to prevent shell injection vulnerabilities.
- **b501** (HIGH, code) at `.\security_samples/semgrep_samples.py:44` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Disabling SSL certificate checks by setting verify=False allows connections to be made without validating the server's certificate, making it vulnerable to eavesdropping._
  - **Suggested fix approach:** Ensure SSL certificate verification is enabled by setting 'verify' to True in requests.
- **generic-api-key** (HIGH, secret) at `security_samples/gitleaks_secrets.txt:13` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Detected a Generic API Key, potentially exposing access to various services and sensitive operations._
  - **Suggested fix approach:** Remove the hardcoded API key from the source code and utilize environment variables or a secure vault service to safely manage sensitive information.
- **private-key** (HIGH, secret) at `security_samples/gitleaks_secrets.txt:17` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Hardcoded private keys can compromise cryptographic integrity, allowing attackers to decrypt sensitive data or impersonate users. This can lead to severe security breaches._
  - **Suggested fix approach:** Avoid hardcoding private keys in your source code. Use secure storage solutions like environment variables or secret management services to store sensitive keys securely.
- **cve-2019-14232** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Django: backtracking in a regular expression in django.utils.text.Truncator leads to DoS._
  - **Suggested fix approach:** Update Django to a version that has fixed this vulnerability to prevent Denial of Service through regex backtracking.
- **cve-2019-14233** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Django: the behavior of the underlying HTMLParser leading to DoS._
  - **Suggested fix approach:** Upgrade to a Django version where this behavior is mitigated or use alternate methods of HTML parsing.
- **cve-2019-14235** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Django: Potential memory exhaustion in django.utils.encoding.uri_to_iri()._
  - **Suggested fix approach:** Ensure the Django version is recent, addressing the vulnerability, or restrict the data processed to avoid potential memory issues.
- **cve-2019-19118** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Django: privilege escalation in the django admin._
  - **Suggested fix approach:** Update Django to a patched version to fix the privilege escalation vulnerability in the admin interface.
- **cve-2020-13254** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Malformed memcached keys can lead to unintended data exposure as sensitive information might be stored under incorrect keys._
  - **Suggested fix approach:** Ensure that memcached keys are properly validated to prevent malformed inputs.
- **cve-2020-24583** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Incorrect permissions on intermediate directories can expose sensitive files, allowing unauthorized access._
  - **Suggested fix approach:** Review and set correct permissions for all directories, ensuring they restrict access appropriately.
- **cve-2020-9402** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _SQL injection vulnerabilities allow attackers to manipulate database queries through unvalidated parameters._
  - **Suggested fix approach:** Use parameterized queries to safely handle inputs for SQL operations.
- **cve-2021-31542** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Directory traversal vulnerabilities permit unauthorized file access through crafted file paths._
  - **Suggested fix approach:** Validate and sanitize file uploads to prevent directory traversal before processing them.
- **cve-2021-33571** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Indeterminate SSRF, RFI, and LFI attacks can occur when input validation allows unexpected formats._
  - **Suggested fix approach:** Implement stringent validation for IPv4 addresses to prevent leading zeros and other malicious inputs.
- **cve-2021-45115** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _django: Denial-of-service possibility in UserAttributeSimilarityValidator (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **cve-2021-45116** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _django: Potential information disclosure in dictsort template filter (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **cve-2022-23833** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _django: Denial-of-service possibility in file uploads (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **cve-2022-36359** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _An issue was discovered in the HTTP FileResponse class in Django 3.2 b ... (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **cve-2025-57833** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _django: Django SQL injection in FilteredRelation column aliases (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **cve-2025-64458** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Django: Denial-of-service vulnerability in Django on Windows (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **cve-2018-1000656** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _python-flask: Denial of Service via crafted JSON file (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **cve-2019-1010083** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _python-flask: unexpected memory usage can lead to denial of service via crafted encoded JSON data (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **cve-2023-30861** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _flask: Possible disclosure of permanent session cookie due to missing Vary: Cookie header (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **cve-2018-18074** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _python-requests: Redirect from HTTPS to HTTP does not remove Authorization header (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- **cve-2019-11324** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _python-urllib3: Certification mishandle when error should be thrown (beyond AI call budget — manual review recommended)_
  - **Suggested fix approach:** Review this rule against secure-coding guidance and remediate.
- _…and 58 more (showing the 50 highest-risk findings; see the severity breakdown above for the full distribution)._

_The final merge decision is left to a human reviewer; this report is advisory and does not trigger a merge._
