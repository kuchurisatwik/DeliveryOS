# INTENTIONALLY INSECURE — Trivy / Checkov test fixture (Dockerfile).
# Not built or deployed; exists only so Trivy (OS package vulns) and Checkov
# (Dockerfile misconfig) have something to detect. Do not copy these patterns.

# Outdated base image with many known OS-package CVEs (Trivy vuln scanner).
FROM python:3.4-jessie

# CKV: running as root (no USER directive dropping privileges).
WORKDIR /app
COPY . /app

# CKV: use of ADD with a remote URL and running pip as root.
RUN pip install -r requirements.txt

# CKV: container exposes a port and runs as root by default.
EXPOSE 8000
CMD ["python", "app.py"]
