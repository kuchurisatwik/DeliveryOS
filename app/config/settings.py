from pydantic_settings import BaseSettings
from pydantic import Field
import os
from typing import Optional

class Settings(BaseSettings):
    """Application configuration settings."""
    # Webhook settings
    WEBHOOK_SECRET: Optional[str] = Field(None, description="GitHub webhook secret for validation")
    
    # GitHub settings
    GITHUB_TOKEN: Optional[str] = Field(None, description="GitHub Personal Access Token")
    
    # AI settings
    GEMINI_API_KEY: Optional[str] = Field(None, description="Google Gemini API Key")
    OPENROUTER_API_KEY: Optional[str] = Field(None, description="OpenRouter API Key")

    # SonarQube settings (Layer 4 Quality Gate)
    SONARQUBE_URL: str = Field(
        default="https://sonarcloud.io",
        description="Base URL of the SonarQube / SonarCloud instance",
    )
    SONARQUBE_TOKEN: Optional[str] = Field(
        None, description="SonarQube project analysis token (used as HTTP Basic auth user)"
    )
    SONARQUBE_PROJECT_KEY: Optional[str] = Field(
        None, description="SonarQube project key whose metrics back the Quality Gate"
    )
    
    # Pipeline selection
    PIPELINE_MODE: str = Field(
        default="both",
        description=(
            "Which pipeline(s) to run on a push: 'security' (security pipeline "
            "only), 'testing' (test-generation/validation pipeline only), or "
            "'both' (default)."
        ),
    )

    # Security pipeline — AI triage strategy
    SECURITY_TRIAGE_MODE: str = Field(
        default="batch",
        description=(
            "How the Intelligence layer uses the LLM: 'batch' (default, "
            "production) groups findings by rule and severity-gates them, then "
            "makes 1-5 batched LLM calls to produce a remediation guide for the "
            "HIGH/CRITICAL rule-groups; 'per_finding' makes one triage (+repair) "
            "call per finding (accurate but ~2N calls, dev/testing only); 'off' "
            "makes zero LLM calls and produces a deterministic-only report."
        ),
    )
    #: Detection scope: 'commit' (default, PR-gate — scan only changed files) or
    #: 'full' (audit — scan the entire repository). Full is for one-off/scheduled
    #: whole-repo audits; commit-scoping is right for per-push PR checks.
    SECURITY_SCAN_SCOPE: str = Field(
        default="auto",
        description=(
            "'auto' (default): scan the WHOLE repo the first time this repo is seen "
            "(onboarding), then commit-scoped on every push after. 'commit': always "
            "scan only changed files. 'full': always scan the whole repo (audit)."
        ),
    )
    #: Where the pipeline stores per-repo scan state (which repos were onboarded).
    #: Pipeline-side only — never written into the scanned repository.
    SECURITY_STATE_DIR: str = Field(
        default=os.path.join(".deliveryos", "state"),
        description="Directory for pipeline state (e.g. which repos have been scanned).",
    )
    #: Language coverage for the SAST scanners (Semgrep, CodeQL). 'auto' (default)
    #: detects languages from the scan scope and selects matching rule packs /
    #: query suites. A comma-separated list (e.g. 'python,javascript,go') pins the
    #: languages explicitly. The other scanners (Gitleaks/Checkov/Trivy/Bandit)
    #: are unaffected — they are language-agnostic or Python-specific by design.
    SECURITY_LANGUAGES: str = Field(
        default="auto",
        description="'auto' detects languages from the scope; or a comma-separated allow-list.",
    )
    #: Whether CodeQL (deep, slow, per-language DB build) runs for compiled
    #: languages (Java, C#, C/C++, Go) that require an autobuild. Interpreted
    #: languages (Python, JavaScript/TypeScript, Ruby) always run when detected.
    #: Compiled-language builds are the main cost/failure risk, so they are opt-in.
    SECURITY_CODEQL_COMPILED: bool = Field(
        default=False,
        description="When True, CodeQL also analyses compiled languages (needs a working build).",
    )
    #: Cross-tool correlation: merge findings of the same vulnerability class at the
    #: same file:line reported by different scanners into one (unioning the tools),
    #: reducing duplicate noise (e.g. one shell-injection line reported by 4 tools).
    SECURITY_CORRELATE_FINDINGS: bool = Field(
        default=True,
        description="Merge same-class, same-location findings across scanners into one.",
    )
    #: Baseline / delta mode. A path (relative to the repo, or absolute) to a JSON
    #: baseline of known-finding fingerprints. When set and the file exists, only
    #: NEWLY introduced findings are reported. Empty/'off' disables delta mode.
    SECURITY_BASELINE: str = Field(
        default="",
        description="Path to a baseline fingerprint file; when present, report only new findings.",
    )
    #: When True, (re)write the baseline file from the current run's findings instead
    #: of filtering — use once to establish/refresh the baseline.
    SECURITY_BASELINE_UPDATE: bool = Field(
        default=False,
        description="Write/refresh the baseline from this run instead of filtering.",
    )
    #: How many security scans run concurrently. Keep at 1 on small/single boxes
    #: (e.g. t3.medium) — CodeQL is CPU/RAM heavy and two at once will thrash/OOM.
    SECURITY_SCAN_WORKERS: int = Field(
        default=1,
        description="Concurrent security scans (1 = one-at-a-time; safe for small instances).",
    )
    #: Max queued scans before the webhook sheds load with HTTP 503 (backpressure).
    SECURITY_SCAN_QUEUE_MAX: int = Field(
        default=20,
        description="Max queued scans; beyond this the webhook returns 503.",
    )
    #: Cache CodeQL databases keyed by commit SHA so the same commit isn't
    #: re-extracted (safe — same code = same DB). Only the newest DB per language
    #: is kept. Databases for a NEW commit are always rebuilt (never stale).
    SECURITY_CODEQL_CACHE: bool = Field(
        default=True,
        description="Reuse a CodeQL DB when re-scanning the same commit SHA.",
    )
    #: Severities the batch triage sends to the LLM. Lower-severity findings are
    #: listed deterministically in the report without an AI call.
    SECURITY_AI_SEVERITIES: str = Field(
        default="HIGH,CRITICAL",
        description="Comma-separated severities escalated to AI in batch mode.",
    )
    #: Max finding-groups per batched LLM call, and the hard cap on batch calls/run.
    SECURITY_AI_BATCH_SIZE: int = Field(default=5, description="Rule-groups per batched LLM call (<=5 keeps every item in the model's high-attention window).")
    SECURITY_AI_MAX_CALLS: int = Field(default=6, description="Hard cap on batched triage calls per run.")
    #: Cap on dedicated per-rule CRITICAL repair calls (each yields a real +/- diff).
    SECURITY_AI_MAX_REPAIR_CALLS: int = Field(
        default=5,
        description=(
            "Max dedicated LLM repair calls per run — one per CRITICAL rule-group, "
            "each producing a concrete unified diff. Beyond this cap, CRITICAL rules "
            "fall back to batch text + illustrative snippets like HIGH."
        ),
    )

    # Security pipeline — deterministic patch verification
    SECURITY_VERIFY_PATCHES: bool = Field(
        default=False,
        description=(
            "When True, the Intelligence layer re-runs every scanner after each "
            "AI-generated patch to deterministically verify the fix (Requirement 11). "
            "When False (default), AI patches are attached to the report as advisory "
            "suggestions only — no re-scan, no scanner-confirmed 'fixed' status. This "
            "avoids the ~40s-per-finding re-scan cost until patch-application-to-disk "
            "is implemented; see the architecture doc for the tradeoff."
        ),
    )

    # Workspace settings
    WORKSPACE_DIR: str = Field(
        default=os.path.join(os.getcwd(), "workspace"), 
        description="Local directory for cloning repositories"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
