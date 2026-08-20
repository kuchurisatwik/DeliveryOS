# syntax=docker/dockerfile:1
#
# Production image for the DeliveryOS Security Pipeline.
#
# Design principles (learned in testing):
#   * The app runs on a modern pydantic (2.13.x). Python-based scanners
#     (bandit/semgrep/checkov/njsscan) each pin their OWN, sometimes conflicting,
#     deps — so they are installed in ISOLATED environments via pipx and only
#     their entrypoints are exposed on PATH. This makes "njsscan downgraded
#     pydantic and broke the app" impossible.
#   * Binary tools (gitleaks, trivy, codeql) are pinned release downloads.
#   * CodeQL uses the *bundle* (CLI + query packs) so scans don't depend on a
#     live registry download at runtime.
#   * Runs as a non-root user; workspace/state/cache live on mounted volumes.
#
# IMPORTANT: run exactly ONE uvicorn worker. The in-process ScanQueue lives in
# the process; multiple workers would create multiple independent queues.

FROM python:3.12-slim AS base

# ---- Tool versions (bump here) --------------------------------------------
ARG GITLEAKS_VERSION=8.18.4
ARG TRIVY_VERSION=0.72.0
ARG CODEQL_BUNDLE_TAG=codeql-bundle-v2.18.1
ARG SEMGREP_VERSION=1.86.0
ARG BANDIT_VERSION=1.7.9
ARG CHECKOV_VERSION=3.2.256
ARG NJSSCAN_VERSION=0.4.3

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    PIPX_HOME=/opt/pipx \
    PIPX_BIN_DIR=/usr/local/bin \
    PATH="/usr/local/bin:/opt/codeql:${PATH}"

# ---- System deps -----------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates unzip tar gzip \
    && rm -rf /var/lib/apt/lists/*

# ---- Binary scanners (pinned releases) ------------------------------------
# gitleaks
RUN curl -fsSL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
      | tar -xz -C /usr/local/bin gitleaks \
    && chmod +x /usr/local/bin/gitleaks

# trivy — direct pinned tarball (asset name verified to exist for this version)
RUN curl -fsSL "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz" \
      | tar -xz -C /usr/local/bin trivy \
    && chmod +x /usr/local/bin/trivy \
    && trivy --version

# CodeQL bundle (CLI + prebuilt query packs) → /opt/codeql/codeql/codeql
RUN curl -fsSL "https://github.com/github/codeql-action/releases/download/${CODEQL_BUNDLE_TAG}/codeql-bundle-linux64.tar.gz" \
      | tar -xz -C /opt \
    && /opt/codeql/codeql version

# ---- Python scanners in ISOLATED envs (pipx) ------------------------------
RUN pip install --no-cache-dir pipx \
    && pipx install "semgrep==${SEMGREP_VERSION}" \
    && pipx install "bandit==${BANDIT_VERSION}" \
    && pipx install "checkov==${CHECKOV_VERSION}" \
    && pipx install "njsscan==${NJSSCAN_VERSION}" \
    # semgrep's opentelemetry dep imports pkg_resources (setuptools), which the
    # pipx venv lacks on py3.12 → inject it so `semgrep` doesn't crash on startup.
    && pipx inject semgrep setuptools

# ---- Application -----------------------------------------------------------
WORKDIR /app

# App deps in the MAIN interpreter. Pin pydantic modern; nothing above can
# touch it because the scanners live in their own pipx venvs.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt "uvicorn[standard]" "pydantic>=2.12,<3"

COPY app ./app

# ---- Runtime user + writable data dirs ------------------------------------
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data/workspace /data/state /data/codeql-cache \
    && chown -R appuser:appuser /data /app
USER appuser

ENV PIPELINE_MODE=security \
    SECURITY_SCAN_SCOPE=auto \
    SECURITY_SCAN_WORKERS=1 \
    WORKSPACE_DIR=/data/workspace \
    SECURITY_STATE_DIR=/data/state

VOLUME ["/data"]
EXPOSE 8010

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8010/health || exit 1

# One worker only (in-process queue). Scale by running more containers, not workers.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010", "--workers", "1"]
