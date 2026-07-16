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
        default="commit",
        description="'commit' scans changed files (PR gate); 'full' scans the whole repo (audit).",
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
