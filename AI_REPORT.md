# AI Software Delivery Engineer: Architecture Review

**Repository:** kuchurisatwik/DeliveryOS
**Commit SHA:** 30819b0132e7493ebeecbc05b3ed725558aa521c
**Branch:** ai-sde/review-30819b0-20260715152918
**Timestamp:** 2026-07-15T15:31:34.620814Z

No AI analysis was generated.

---
## 🔒 Security Pipeline Report
**Commit:** `30819b0132e7493ebeecbc05b3ed725558aa521c`
**Security Summary:** 0 finding(s) fixed; 108 finding(s) remaining; quality gate failed.
**Scanned scope:** 12 changed file(s).

**Findings by severity:** CRITICAL: 11, HIGH: 48, MEDIUM: 40, LOW: 9

### 🛠️ Remediation Guide — Key High/Critical Findings
The 54 highest-severity rule(s) below account for the key risk in this change. Each fix applies to all listed occurrences.

#### CRITICAL · cve-2019-14234 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** SQL injection vulnerabilities can allow attackers to execute arbitrary SQL code, potentially compromising the entire database.
- **How to fix:** Upgrade to a secure version of Django that addresses the SQL injection risk in JSONField/HStoreField.

#### CRITICAL · cve-2019-19844 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** A crafted email address can lead to account takeover, jeopardizing user accounts and sensitive information.
- **How to fix:** Update Django to a version that properly validates email addresses to prevent account takeover vulnerabilities.

#### CRITICAL · cve-2020-7471 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Potential SQL injection can arise during the handling of untrusted data, leading to data breaches.
- **How to fix:** Ensure you are using a version of Django that fixes the SQL injection via StringAgg.

#### CRITICAL · cve-2022-28346 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** SQL injection in QuerySet methods can allow malicious attackers to manipulate database queries.
- **How to fix:** Upgrade to a Django version that patches the SQL injection vulnerability in QuerySet methods.

#### CRITICAL · cve-2022-28347 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** SQL injection vulnerabilities can help attackers gain unauthorized access or manipulate data.
- **How to fix:** Update Django to a version that mitigates SQL injection via QuerySet.explain.

#### CRITICAL · cve-2025-64459 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Django SQL injection issues can result in severe data leaks or manipulation of the application’s data.
- **How to fix:** Upgrade Django to a version that addresses the SQL injection vulnerabilities identified.

#### CRITICAL · cve-2019-20477 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Command execution vulnerabilities through the PyYAML library can allow malicious code execution on the server.
- **How to fix:** Upgrade PyYAML to a secure version where this vulnerability is fixed.

#### CRITICAL · cve-2020-14343 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Incomplete fixes can leave applications vulnerable to exploits similar to the original issue.
- **How to fix:** Ensure PyYAML is updated to the latest version that fully addresses CVE-2020-1747.

#### CRITICAL · cve-2020-1747 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Arbitrary command execution vulnerability poses a critical risk to any server using the affected version of PyYAML.
- **How to fix:** Upgrade to a fixed version of PyYAML where command execution risks are mitigated.

#### CRITICAL · aws-0104 — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:37`
- **Why it matters:** Allowing unrestricted egress can expose your infrastructure to data exfiltration or unwanted communication.
- **How to fix:** Restrict the security group rule to specific IP addresses or CIDR blocks instead of allowing all egress.

#### CRITICAL · aws-access-key-id — 1 occurrence(s) · P0
- **Scanners:** trivy
- **Where:** `security_samples/gitleaks_secrets.txt:7`
- **Why it matters:** Exposing AWS Access Key IDs can lead to unauthorized access to AWS resources.
- **How to fix:** Remove the AWS Access Key ID from the codebase and use environment variables or AWS IAM roles instead.

#### HIGH · b605 — 3 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `.\security_samples/bandit_samples.py:36, .\security_samples/codeql_taintflow.py:36, .\security_samples/semgrep_samples.py:39`
- **Why it matters:** Starting processes with a shell can lead to shell injection vulnerabilities, allowing for arbitrary code execution.
- **How to fix:** Refactor to avoid using shell=True when calling subprocess functions; use a list of arguments instead.

#### HIGH · python.lang.security.audit.subprocess-shell-true.subprocess-shell-true — 2 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\bandit_samples.py:31, security_samples\semgrep_samples.py:34`
- **Why it matters:** Using 'shell=True' allows for potential command injection, making it a significant security risk.
- **How to fix:** Change subprocess calls to use shell=False to prevent potential command injection attacks.

#### HIGH · b602 — 2 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `.\security_samples/bandit_samples.py:31, .\security_samples/semgrep_samples.py:34`
- **Why it matters:** Using shell=True in subprocess calls can result in significant security issues due to shell injection risks.
- **How to fix:** Change the subprocess calls to use shell=False and pass the command as a list.

#### HIGH · private-key — 2 occurrence(s) · P1
- **Scanners:** gitleaks, trivy
- **Where:** `security_samples/gitleaks_secrets.txt:17, security_samples/gitleaks_secrets.txt:18`
- **Why it matters:** Exposing private keys can lead to unauthorized access to sensitive data and system compromise.
- **How to fix:** Remove the private key from the repository and manage keys securely using environment variables.

#### HIGH · python.requests.security.disabled-cert-validation.disabled-cert-validation — 1 occurrence(s) · P1
- **Scanners:** semgrep
- **Where:** `security_samples\semgrep_samples.py:44`
- **Why it matters:** Disabling SSL certificate validation exposes the application to man-in-the-middle (MITM) attacks.
- **How to fix:** Re-enable certificate validation to ensure secure connections to servers.

#### HIGH · py/clear-text-storage-sensitive-data — 1 occurrence(s) · P1
- **Scanners:** codeql
- **Where:** `security_samples/bandit_samples.py:58`
- **Why it matters:** Storing sensitive data in clear text can lead to exposure of confidential user data.
- **How to fix:** Implement encryption for sensitive data before storing it to prevent data breaches.

#### HIGH · py/weak-sensitive-data-hashing — 1 occurrence(s) · P1
- **Scanners:** codeql
- **Where:** `security_samples/bandit_samples.py:51`
- **Why it matters:** Using weak hashing algorithms can lead to easy cracking of sensitive data like passwords.
- **How to fix:** Switch to stronger, computationally intensive hashing algorithms such as bcrypt or Argon2.

#### HIGH · b324 — 1 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `.\security_samples/bandit_samples.py:51`
- **Why it matters:** Using weak MD5 hashes makes it trivial for attackers to crack hashed data.
- **How to fix:** Consider using stronger hash options and set usedforsecurity=False when applicable.

#### HIGH · b501 — 1 occurrence(s) · P1
- **Scanners:** bandit
- **Where:** `.\security_samples/semgrep_samples.py:44`
- **Why it matters:** Disabling SSL verification in requests can lead to insecure connections and data leaks.
- **How to fix:** Ensure SSL certificate checks are enabled by setting verify=True in requests.

#### HIGH · generic-api-key — 1 occurrence(s) · P1
- **Scanners:** gitleaks
- **Where:** `security_samples/gitleaks_secrets.txt:13`
- **Why it matters:** Exposing API keys can lead to unauthorized access and abuse of services.
- **How to fix:** Remove the generic API key from the code, and use environment variables to manage secrets securely.

#### HIGH · cve-2019-14232 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Backtracking vulnerabilities can lead to denial of service (DoS) by exploiting regular expressions.
- **How to fix:** Update to the latest version of Django that addresses the regular expression backtracking issue.

#### HIGH · cve-2019-14233 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Vulnerabilities in HTML parsing can lead to denial of service attacks, impacting application availability.
- **How to fix:** Upgrade Django to a version where this HTMLParser vulnerability is resolved.

#### HIGH · cve-2019-14235 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Potential memory exhaustion can lead to application crashes or unavailability.
- **How to fix:** Update Django to a version that mitigates the memory exhaustion risks.

#### HIGH · cve-2019-19118 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Privilege escalation vulnerabilities in the admin interface can allow unauthorized access to sensitive functionalities.
- **How to fix:** Upgrade your Django version to one that fixes the privilege escalation vulnerability in the admin panel.

#### HIGH · cve-2020-13254 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Potential data leakage through malformed keys could expose sensitive data.
- **How to fix:** Ensure your Django version is updated to handle memcached key formatting securely.

#### HIGH · cve-2020-24583 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Incorrect permissions can be exploited to gain unauthorized access to files, leading to data breaches.
- **How to fix:** Review and correct directory permissions on intermediate-level directories for compliance with security best practices.

#### HIGH · cve-2020-9402 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Potential SQL injection can lead to unauthorized data access or manipulation.
- **How to fix:** Upgrade to the latest version of Django that addresses SQL injection risks in GIS functions.

#### HIGH · cve-2021-31542 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Directory-traversal vulnerabilities allow attackers to access sensitive files outside intended directories.
- **How to fix:** Upgrade to a secure version of Django that mitigates directory traversal risks.

#### HIGH · cve-2021-33571 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Indeterminate SSRF, RFI, and LFI vulnerabilities can lead to significant security risks and unauthorized access.
- **How to fix:** Update the Django version to one that resolves the issue of accepting leading zeros in IPv4 addresses.

#### HIGH · cve-2021-45115 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** This vulnerability can lead to a denial-of-service attack by exhausting server resources through extensive similarity checks on user attributes.
- **How to fix:** Upgrade Django to version 3.2.10 or later, where this vulnerability has been addressed. Review configurations for the UserAttributeSimilarityValidator.

#### HIGH · cve-2021-45116 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** This flaw may allow attackers to expose sensitive information via the use of template filters in Django.
- **How to fix:** Update Django to version 3.2.10 or higher to mitigate this risk. Ensure template contexts do not unintentionally expose sensitive data.

#### HIGH · cve-2022-23833 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** This issue could allow attacks that exploit file uploads to cause denial-of-service conditions by sending crafted files.
- **How to fix:** Patch Django to version 4.0.1 or later, where this vulnerability is resolved. Implement file size limits and validation checks for uploads.

#### HIGH · cve-2022-36359 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Vulnerabilities in HTTP FileResponse can be exploited to cause denial-of-service by sending crafted requests.
- **How to fix:** Update Django to version 3.2.11 or newer to mitigate this risk. Review your implementation of FileResponse and consider rate limiting.

#### HIGH · cve-2025-57833 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** The vulnerability may allow an SQL injection attack through improperly handled aliases in FilteredRelation.
- **How to fix:** Upgrade to Django 4.2.0 or later where this issue is patched. Review all SQL queries and ORM usage for vulnerabilities.

#### HIGH · cve-2025-64458 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Denial-of-service vulnerabilities are present when Django is run in a Windows environment.
- **How to fix:** Either upgrade to a more recent Django version (4.2.0+) or consider deploying in a non-Windows environment to avoid this vulnerability.

#### HIGH · cve-2018-1000656 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** This vulnerability allows for denial-of-service attacks via specially crafted JSON files sent to Flask applications.
- **How to fix:** Upgrade Flask to version 1.0.2 or later to patch this vulnerability. Validate and sanitize incoming JSON data.

#### HIGH · cve-2019-1010083 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Unexpected memory usage may lead to a denial of service when handling crafted encoded JSON data in Flask applications.
- **How to fix:** Ensure Flask is updated to at least version 1.1.3. Regularly profile your application's memory usage and impose limits.

#### HIGH · cve-2023-30861 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Failure to include the appropriate Vary header could potentially allow for session cookie leakage.
- **How to fix:** Ensure your Flask application adds 'Vary: Cookie' to responses to mitigate cookie leakage risks. Review session management practices.

#### HIGH · cve-2018-18074 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** There is a risk of exposing the Authorization header during redirect processes from HTTPS to HTTP.
- **How to fix:** Review your application to ensure redirects do not occur from HTTPS to HTTP, or use secure methods to handle sensitive headers.

#### HIGH · cve-2019-11324 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Mismanagement of certifying requests could allow attackers to bypass security measures during mishandled errors.
- **How to fix:** Upgrade urllib3 to version 1.24.1 or later. Validate all SSL contexts and handle errors properly.

#### HIGH · cve-2023-43804 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Cookie headers may unintentionally be sent in a cross-origin redirect, causing potential information disclosure.
- **How to fix:** Upgrade to urllib3 version 1.26.8 or higher, and ensure proper handling of cookie headers across origins.

#### HIGH · cve-2025-66418 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Unbounded decompression chains can lead to resource exhaustion, making applications susceptible to denial-of-service attacks.
- **How to fix:** Ensure that you are using urllib3 version 1.26.9 or later, and implement limits on request sizes.

#### HIGH · cve-2025-66471 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** The streaming API does not handle compressed data properly, which could allow for denial-of-service attacks.
- **How to fix:** Update urllib3 to version 1.26.10 to address this issue. Review streaming data handling for vulnerabilities.

#### HIGH · cve-2026-21441 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** Improper handling of redirects while decompressing data may allow attackers to bypass safeguards in the streaming API.
- **How to fix:** Upgrade to the latest urllib3 to address this vulnerability. Implement strict checks on redirect handling.

#### HIGH · cve-2026-44431 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/requirements.txt:0`
- **Why it matters:** This vulnerability can lead to the exposure of sensitive headers during cross-origin redirects.
- **How to fix:** Ensure your urllib3 is updated and restrict forwarding sensitive headers during cross-origin requests.

#### HIGH · ds-0002 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/Dockerfile:0`
- **Why it matters:** Running Docker containers as the root user can lead to potential security risks, including privilege escalation.
- **How to fix:** Modify your Dockerfile to utilize a non-root user for executing the image to enhance security practices.

#### HIGH · aws-0086 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:14`
- **Why it matters:** Public access control lists (ACLs) on S3 can expose your resources to unauthorized access.
- **How to fix:** Ensure the S3 bucket policy is configured correctly to block public ACLs. Regularly audit S3 bucket permissions.

#### HIGH · aws-0087 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:15`
- **Why it matters:** Public policies on S3 can lead to unauthorized access and exposure of sensitive data.
- **How to fix:** Review the S3 bucket policies and ensure they do not allow public access. Implement least privilege principles.

#### HIGH · aws-0091 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:16`
- **Why it matters:** Public ACLs can inadvertently expose S3 buckets to public access, leading to data leaks.
- **How to fix:** Modify your S3 bucket settings to ignore public ACLs and implement strict access controls.

#### HIGH · aws-0092 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:8`
- **Why it matters:** S3 buckets that allow public access through ACLs pose a significant security risk.
- **How to fix:** Review and update your S3 configurations to ensure that buckets are not publicly accessible.

#### HIGH · aws-0093 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:17`
- **Why it matters:** S3 accesses that allow public access could lead to data exposure to malicious actors.
- **How to fix:** Restrict public access to S3 buckets through careful policy settings. Regularly review permissions.

#### HIGH · aws-0107 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:29`
- **Why it matters:** Unrestricted ingress rules in security groups can lead to unauthorized access to SSH or RDP services.
- **How to fix:** Modify security group settings to restrict access to only trusted IP addresses and use VPNs for secure connections.

#### HIGH · aws-0132 — 1 occurrence(s) · P1
- **Scanners:** trivy
- **Where:** `security_samples/insecure_terraform.tf:5`
- **Why it matters:** Using default S3 encryption instead of customer-managed keys can lead to insecure handling of sensitive data.
- **How to fix:** Ensure that your S3 buckets are configured to use customer-managed keys for encryption to enhance data security.

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
- **python.lang.security.audit.subprocess-shell-true.subprocess-shell-true** (HIGH, code) at `security_samples\bandit_samples.py:31` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using 'shell=True' allows for potential command injection, making it a significant security risk._
  - **Suggested fix approach:** Change subprocess calls to use shell=False to prevent potential command injection attacks.
- **python.lang.security.audit.subprocess-shell-true.subprocess-shell-true** (HIGH, code) at `security_samples\semgrep_samples.py:34` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using 'shell=True' allows for potential command injection, making it a significant security risk._
  - **Suggested fix approach:** Change subprocess calls to use shell=False to prevent potential command injection attacks.
- **python.requests.security.disabled-cert-validation.disabled-cert-validation** (HIGH, code) at `security_samples\semgrep_samples.py:44` — scanners: semgrep — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Disabling SSL certificate validation exposes the application to man-in-the-middle (MITM) attacks._
  - **Suggested fix approach:** Re-enable certificate validation to ensure secure connections to servers.
- **py/clear-text-storage-sensitive-data** (HIGH, code) at `security_samples/bandit_samples.py:58` — scanners: codeql — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Storing sensitive data in clear text can lead to exposure of confidential user data._
  - **Suggested fix approach:** Implement encryption for sensitive data before storing it to prevent data breaches.
- **py/weak-sensitive-data-hashing** (HIGH, code) at `security_samples/bandit_samples.py:51` — scanners: codeql — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using weak hashing algorithms can lead to easy cracking of sensitive data like passwords._
  - **Suggested fix approach:** Switch to stronger, computationally intensive hashing algorithms such as bcrypt or Argon2.
- **python.lang.security.audit.eval-detected.eval-detected** (MEDIUM, code) at `security_samples\bandit_samples.py:21` — scanners: semgrep
- **python.lang.security.audit.exec-detected.exec-detected** (MEDIUM, code) at `security_samples\bandit_samples.py:26` — scanners: semgrep
- **python.lang.security.deserialization.pickle.avoid-pickle** (MEDIUM, code) at `security_samples\bandit_samples.py:41` — scanners: semgrep
- **python.lang.security.insecure-hash-algorithms-md5.insecure-hash-algorithm-md5** (MEDIUM, code) at `security_samples\bandit_samples.py:51` — scanners: semgrep
- **python.lang.security.audit.md5-used-as-password.md5-used-as-password** (MEDIUM, code) at `security_samples\bandit_samples.py:51` — scanners: semgrep
- **cve-2019-14234** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _SQL injection vulnerabilities can allow attackers to execute arbitrary SQL code, potentially compromising the entire database._
  - **Suggested fix approach:** Upgrade to a secure version of Django that addresses the SQL injection risk in JSONField/HStoreField.
- **cve-2019-19844** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _A crafted email address can lead to account takeover, jeopardizing user accounts and sensitive information._
  - **Suggested fix approach:** Update Django to a version that properly validates email addresses to prevent account takeover vulnerabilities.
- **cve-2020-7471** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Potential SQL injection can arise during the handling of untrusted data, leading to data breaches._
  - **Suggested fix approach:** Ensure you are using a version of Django that fixes the SQL injection via StringAgg.
- **cve-2022-28346** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _SQL injection in QuerySet methods can allow malicious attackers to manipulate database queries._
  - **Suggested fix approach:** Upgrade to a Django version that patches the SQL injection vulnerability in QuerySet methods.
- **cve-2022-28347** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _SQL injection vulnerabilities can help attackers gain unauthorized access or manipulate data._
  - **Suggested fix approach:** Update Django to a version that mitigates SQL injection via QuerySet.explain.
- **cve-2025-64459** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Django SQL injection issues can result in severe data leaks or manipulation of the application’s data._
  - **Suggested fix approach:** Upgrade Django to a version that addresses the SQL injection vulnerabilities identified.
- **cve-2019-20477** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Command execution vulnerabilities through the PyYAML library can allow malicious code execution on the server._
  - **Suggested fix approach:** Upgrade PyYAML to a secure version where this vulnerability is fixed.
- **cve-2020-14343** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Incomplete fixes can leave applications vulnerable to exploits similar to the original issue._
  - **Suggested fix approach:** Ensure PyYAML is updated to the latest version that fully addresses CVE-2020-1747.
- **cve-2020-1747** (CRITICAL, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Arbitrary command execution vulnerability poses a critical risk to any server using the affected version of PyYAML._
  - **Suggested fix approach:** Upgrade to a fixed version of PyYAML where command execution risks are mitigated.
- **aws-0104** (CRITICAL, dependency) at `security_samples/insecure_terraform.tf:37` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Allowing unrestricted egress can expose your infrastructure to data exfiltration or unwanted communication._
  - **Suggested fix approach:** Restrict the security group rule to specific IP addresses or CIDR blocks instead of allowing all egress.
- **aws-access-key-id** (CRITICAL, dependency) at `security_samples/gitleaks_secrets.txt:7` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P0
  - _Exposing AWS Access Key IDs can lead to unauthorized access to AWS resources._
  - **Suggested fix approach:** Remove the AWS Access Key ID from the codebase and use environment variables or AWS IAM roles instead.
- **b602** (HIGH, code) at `.\security_samples/bandit_samples.py:31` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using shell=True in subprocess calls can result in significant security issues due to shell injection risks._
  - **Suggested fix approach:** Change the subprocess calls to use shell=False and pass the command as a list.
- **b605** (HIGH, code) at `.\security_samples/bandit_samples.py:36` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Starting processes with a shell can lead to shell injection vulnerabilities, allowing for arbitrary code execution._
  - **Suggested fix approach:** Refactor to avoid using shell=True when calling subprocess functions; use a list of arguments instead.
- **b324** (HIGH, code) at `.\security_samples/bandit_samples.py:51` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using weak MD5 hashes makes it trivial for attackers to crack hashed data._
  - **Suggested fix approach:** Consider using stronger hash options and set usedforsecurity=False when applicable.
- **b605** (HIGH, code) at `.\security_samples/codeql_taintflow.py:36` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Starting processes with a shell can lead to shell injection vulnerabilities, allowing for arbitrary code execution._
  - **Suggested fix approach:** Refactor to avoid using shell=True when calling subprocess functions; use a list of arguments instead.
- **b602** (HIGH, code) at `.\security_samples/semgrep_samples.py:34` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Using shell=True in subprocess calls can result in significant security issues due to shell injection risks._
  - **Suggested fix approach:** Change the subprocess calls to use shell=False and pass the command as a list.
- **b605** (HIGH, code) at `.\security_samples/semgrep_samples.py:39` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Starting processes with a shell can lead to shell injection vulnerabilities, allowing for arbitrary code execution._
  - **Suggested fix approach:** Refactor to avoid using shell=True when calling subprocess functions; use a list of arguments instead.
- **b501** (HIGH, code) at `.\security_samples/semgrep_samples.py:44` — scanners: bandit — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Disabling SSL verification in requests can lead to insecure connections and data leaks._
  - **Suggested fix approach:** Ensure SSL certificate checks are enabled by setting verify=True in requests.
- **generic-api-key** (HIGH, secret) at `security_samples/gitleaks_secrets.txt:13` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Exposing API keys can lead to unauthorized access and abuse of services._
  - **Suggested fix approach:** Remove the generic API key from the code, and use environment variables to manage secrets securely.
- **private-key** (HIGH, secret) at `security_samples/gitleaks_secrets.txt:17` — scanners: gitleaks — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Exposing private keys can lead to unauthorized access to sensitive data and system compromise._
  - **Suggested fix approach:** Remove the private key from the repository and manage keys securely using environment variables.
- **cve-2019-14232** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Backtracking vulnerabilities can lead to denial of service (DoS) by exploiting regular expressions._
  - **Suggested fix approach:** Update to the latest version of Django that addresses the regular expression backtracking issue.
- **cve-2019-14233** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Vulnerabilities in HTML parsing can lead to denial of service attacks, impacting application availability._
  - **Suggested fix approach:** Upgrade Django to a version where this HTMLParser vulnerability is resolved.
- **cve-2019-14235** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Potential memory exhaustion can lead to application crashes or unavailability._
  - **Suggested fix approach:** Update Django to a version that mitigates the memory exhaustion risks.
- **cve-2019-19118** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Privilege escalation vulnerabilities in the admin interface can allow unauthorized access to sensitive functionalities._
  - **Suggested fix approach:** Upgrade your Django version to one that fixes the privilege escalation vulnerability in the admin panel.
- **cve-2020-13254** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Potential data leakage through malformed keys could expose sensitive data._
  - **Suggested fix approach:** Ensure your Django version is updated to handle memcached key formatting securely.
- **cve-2020-24583** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Incorrect permissions can be exploited to gain unauthorized access to files, leading to data breaches._
  - **Suggested fix approach:** Review and correct directory permissions on intermediate-level directories for compliance with security best practices.
- **cve-2020-9402** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Potential SQL injection can lead to unauthorized data access or manipulation._
  - **Suggested fix approach:** Upgrade to the latest version of Django that addresses SQL injection risks in GIS functions.
- **cve-2021-31542** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Directory-traversal vulnerabilities allow attackers to access sensitive files outside intended directories._
  - **Suggested fix approach:** Upgrade to a secure version of Django that mitigates directory traversal risks.
- **cve-2021-33571** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Indeterminate SSRF, RFI, and LFI vulnerabilities can lead to significant security risks and unauthorized access._
  - **Suggested fix approach:** Update the Django version to one that resolves the issue of accepting leading zeros in IPv4 addresses.
- **cve-2021-45115** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _This vulnerability can lead to a denial-of-service attack by exhausting server resources through extensive similarity checks on user attributes._
  - **Suggested fix approach:** Upgrade Django to version 3.2.10 or later, where this vulnerability has been addressed. Review configurations for the UserAttributeSimilarityValidator.
- **cve-2021-45116** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _This flaw may allow attackers to expose sensitive information via the use of template filters in Django._
  - **Suggested fix approach:** Update Django to version 3.2.10 or higher to mitigate this risk. Ensure template contexts do not unintentionally expose sensitive data.
- **cve-2022-23833** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _This issue could allow attacks that exploit file uploads to cause denial-of-service conditions by sending crafted files._
  - **Suggested fix approach:** Patch Django to version 4.0.1 or later, where this vulnerability is resolved. Implement file size limits and validation checks for uploads.
- **cve-2022-36359** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Vulnerabilities in HTTP FileResponse can be exploited to cause denial-of-service by sending crafted requests._
  - **Suggested fix approach:** Update Django to version 3.2.11 or newer to mitigate this risk. Review your implementation of FileResponse and consider rate limiting.
- **cve-2025-57833** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _The vulnerability may allow an SQL injection attack through improperly handled aliases in FilteredRelation._
  - **Suggested fix approach:** Upgrade to Django 4.2.0 or later where this issue is patched. Review all SQL queries and ORM usage for vulnerabilities.
- **cve-2025-64458** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Denial-of-service vulnerabilities are present when Django is run in a Windows environment._
  - **Suggested fix approach:** Either upgrade to a more recent Django version (4.2.0+) or consider deploying in a non-Windows environment to avoid this vulnerability.
- **cve-2018-1000656** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _This vulnerability allows for denial-of-service attacks via specially crafted JSON files sent to Flask applications._
  - **Suggested fix approach:** Upgrade Flask to version 1.0.2 or later to patch this vulnerability. Validate and sanitize incoming JSON data.
- **cve-2019-1010083** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Unexpected memory usage may lead to a denial of service when handling crafted encoded JSON data in Flask applications._
  - **Suggested fix approach:** Ensure Flask is updated to at least version 1.1.3. Regularly profile your application's memory usage and impose limits.
- **cve-2023-30861** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Failure to include the appropriate Vary header could potentially allow for session cookie leakage._
  - **Suggested fix approach:** Ensure your Flask application adds 'Vary: Cookie' to responses to mitigate cookie leakage risks. Review session management practices.
- **cve-2018-18074** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _There is a risk of exposing the Authorization header during redirect processes from HTTPS to HTTP._
  - **Suggested fix approach:** Review your application to ensure redirects do not occur from HTTPS to HTTP, or use secure methods to handle sensitive headers.
- **cve-2019-11324** (HIGH, dependency) at `security_samples/requirements.txt:0` — scanners: trivy — Advisory — see remediation guide.
  - **AI triage:** P1
  - _Mismanagement of certifying requests could allow attackers to bypass security measures during mishandled errors._
  - **Suggested fix approach:** Upgrade urllib3 to version 1.24.1 or later. Validate all SSL contexts and handle errors properly.
- _…and 58 more (showing the 50 highest-risk findings; see the severity breakdown above for the full distribution)._

_The final merge decision is left to a human reviewer; this report is advisory and does not trigger a merge._
