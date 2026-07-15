# Security Samples — Intentionally Insecure Fixtures

⚠️ **These files are deliberately insecure and exist ONLY to test the security
pipeline's 6 scanners end-to-end.** They are:

- **Never imported** by the application (nothing in `app/` references this folder).
- **Never executed** — every function here is dead code that only sits on disk for
  static scanners to read.
- **Fake** — all "secrets", keys, and credentials are made-up, non-functional
  placeholders. None grant access to anything.

Do **not** copy these patterns into real code, and do **not** treat any value here
as a real credential.

## What each file targets

| File | Tool it should trip | What it plants |
|---|---|---|
| `bandit_samples.py` | **Bandit** | `eval`/`exec`, `subprocess(shell=True)`, `pickle`, `yaml.load`, MD5, hardcoded password |
| `semgrep_samples.py` | **Semgrep** | SQL injection (string concat), command injection, `os.system`, insecure `requests` (verify=False) |
| `codeql_taintflow.py` | **CodeQL** | multi-function taint flow: user input → helper → `os.system` / SQL |
| `gitleaks_secrets.txt` | **Gitleaks** | fake AWS key, fake private key block, fake generic API token |
| `insecure_terraform.tf` | **Checkov** | public S3 bucket, security group open to `0.0.0.0/0` |
| `requirements.txt` | **Trivy** | pinned, known-vulnerable dependency versions (CVEs) |
| `Dockerfile` | **Trivy / Checkov** | outdated base image, runs as root |

## How to use

Commit this folder and push to `feat/security-pipeline`. The webhook triggers the
pipeline, which clones/fetches the repo and scans it. You should then see findings
from all 6 tools in the generated report — confirming the full
detection → normalize → dedup → report flow works on real findings.
