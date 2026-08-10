"""Configuration for the standalone DAST service.

Every knob is ``DAST_``-prefixed so this service's settings never collide with the
SAST pipeline's ``SECURITY_*`` settings, even when both read the same ``.env``.
"""

from __future__ import annotations

import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class DastSettings(BaseSettings):
    """Standalone DAST service configuration."""

    # ------------------------------------------------------------------ #
    # Service
    # ------------------------------------------------------------------ #
    DAST_STATE_DIR: str = Field(
        default=os.path.join(".deliveryos", "dast-state"),
        description="Directory holding scan records and baselines (service-side only).",
    )
    #: Concurrent scans. Keep at 1: every tool hits the SAME target, so two scans
    #: at once means two tools fighting over one app and results neither can trust.
    DAST_SCAN_WORKERS: int = Field(
        default=1,
        description="Concurrent DAST scans (1 = one target at a time; recommended).",
    )
    DAST_SCAN_QUEUE_MAX: int = Field(
        default=20, description="Max queued scans before /scan sheds load with 503."
    )

    # ------------------------------------------------------------------ #
    # Target / preflight
    # ------------------------------------------------------------------ #
    DAST_HEALTH_PATH: str = Field(
        default="/health", description="Path polled to confirm the target is up."
    )
    DAST_HEALTH_TIMEOUT: int = Field(
        default=120, description="Seconds to wait for the target to become reachable."
    )
    #: When True, preflight requires the target's health payload to report the same
    #: commit SHA we were asked to scan. Without this you eventually spend a day
    #: chasing findings that live in yesterday's build.
    DAST_REQUIRE_SHA_MATCH: bool = Field(
        default=False,
        description="Fail preflight when the target's reported commit SHA differs.",
    )
    DAST_SHA_FIELD: str = Field(
        default="commit_sha",
        description="Key in the /health JSON payload carrying the deployed commit SHA.",
    )
    #: Sent verbatim as the Authorization header by every tool that supports auth.
    #: Without it we only ever test the login page.
    DAST_AUTH_HEADER: Optional[str] = Field(
        default=None,
        description="Authorization header value for authenticated scans (e.g. 'Bearer ey...').",
    )
    DAST_OPENAPI_PATH: str = Field(
        default="/openapi.json",
        description="Path to the target's OpenAPI spec; used to seed scanners and templatise URLs.",
    )

    # ------------------------------------------------------------------ #
    # Nuclei
    # ------------------------------------------------------------------ #
    #: Pinned template directory baked into the image. Templates are executable
    #: code, not data — they issue requests — so they are pinned and upgraded via a
    #: reviewed PR exactly like any other dependency.
    DAST_NUCLEI_TEMPLATES: str = Field(
        default="/opt/nuclei-templates",
        description="Path to the pinned nuclei template set.",
    )
    DAST_NUCLEI_SEVERITY: str = Field(
        default="critical,high,medium",
        description="Comma-separated severities to report (info is mostly fingerprinting noise).",
    )
    #: Some templates are deliberately destructive or extremely noisy. Never run
    #: these against a shared environment.
    DAST_NUCLEI_EXCLUDE_TAGS: str = Field(
        default="dos,fuzz,intrusive",
        description="Comma-separated template tags never to run.",
    )
    #: Our staging target is typically a single uvicorn worker. Firing nuclei at
    #: full default speed jams the door: requests time out, timed-out templates
    #: report nothing, and the scan looks clean because it never landed.
    DAST_NUCLEI_RATE_LIMIT: int = Field(
        default=50, description="Max requests per second sent to the target."
    )
    DAST_NUCLEI_CONCURRENCY: int = Field(
        default=25, description="Templates executed in parallel."
    )
    DAST_NUCLEI_TIMEOUT: int = Field(
        default=900, description="Hard subprocess timeout for a nuclei run (seconds)."
    )
    #: Out-of-band detection (blind SSRF/RCE) works by calling a public interact.sh
    #: server, which means target hostnames and payload data leave our network.
    #: Off by default; enable only with a self-hosted interactsh server.
    DAST_NUCLEI_INTERACTSH: bool = Field(
        default=False,
        description="Enable out-of-band (interact.sh) detection. Leaks data to a public server unless self-hosted.",
    )
    DAST_NUCLEI_INTERACTSH_SERVER: Optional[str] = Field(
        default=None, description="Self-hosted interactsh server URL."
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


dast_settings = DastSettings()
