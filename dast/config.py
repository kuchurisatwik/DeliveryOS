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
    #: This service's own base URL, as reachable *by the ZAP sidecar* over the
    #: shared network (e.g. ``http://dast:8020``). When set and the target
    #: publishes no runtime spec, the synthesised OpenAPI spec is served from here
    #: and ZAP imports it (with the target as host override) to seed its site tree
    #: — this is how the source-extracted endpoint inventory reaches ZAP. When
    #: unset, ZAP falls back to importing the target's own ``DAST_OPENAPI_PATH``.
    DAST_SELF_URL: Optional[str] = Field(
        default=None,
        description="This service's base URL as reachable by the ZAP sidecar (e.g. http://dast:8020).",
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

    # ------------------------------------------------------------------ #
    # ZAP (dynamic scanner sidecar)
    # ------------------------------------------------------------------ #
    #: ZAP runs as a long-lived daemon in its own container; we drive it over its
    #: REST API rather than starting a JVM per scan.
    DAST_ZAP_HOST: str = Field(
        default="127.0.0.1",
        description="Host of the ZAP sidecar exposing the REST API.",
    )
    DAST_ZAP_PORT: int = Field(
        default=8090,
        description="Port of the ZAP sidecar's REST API.",
    )
    #: Without this we only ever talk to an unauthenticated daemon; ZAP's REST API is
    #: gated by this key.
    DAST_ZAP_API_KEY: Optional[str] = Field(
        default=None,
        description="API key used to authenticate against the ZAP REST API.",
    )
    #: The tool deciding whether a build passes must not change without a reviewed
    #: change, so the sidecar image is pinned (digest or explicit version) and NEVER
    #: `latest`. Upgrade it exactly like any other dependency, via a reviewed PR.
    DAST_ZAP_IMAGE: str = Field(
        default="ghcr.io/zaproxy/zaproxy:2.16.1",
        description="Pinned ZAP sidecar image reference (digest/version, never 'latest').",
    )
    #: Logging out mid-scan destroys the authenticated session, after which every
    #: request tests the login page. Exclude logout URLs from all traffic.
    DAST_ZAP_LOGOUT_EXCLUDE: str = Field(
        default=".*/logout.*",
        description="Regex of URLs excluded from spidering and scanning (e.g. logout).",
    )
    #: Our staging target is typically a single worker; firing ZAP at full speed jams
    #: the door and the scan looks clean because requests never landed.
    DAST_ZAP_RATE_LIMIT: int = Field(
        default=50,
        description="Max requests per second ZAP sends to a single-worker target.",
    )
    #: Minimum fraction of the spec's endpoints that must land on ZAP's site tree for
    #: the scan to count as adequately seeded; below this the outcome is `incomplete`.
    DAST_ZAP_COVERAGE_TOLERANCE: float = Field(
        default=0.8,
        description="Min fraction of spec endpoints that must be discovered (else incomplete).",
    )
    #: A deliberately vulnerable route we control. If ZAP cannot flag it, ZAP's own
    #: detection is broken and any 'clean' result is untrustworthy.
    DAST_ZAP_CANARY_PATH: str = Field(
        default="/canary/xss",
        description="Path of the deliberately vulnerable canary endpoint.",
    )
    DAST_ZAP_TIMEOUT: int = Field(
        default=1800,
        description="Hard ceiling for one ZAP scan phase (seconds).",
    )
    #: Seeding imports the spec by URL, and ZAP fetches *every* endpoint during that
    #: single synchronous REST call. On a large spec or a slow target that easily
    #: exceeds the short per-call REST timeout, which would fail an otherwise healthy
    #: scan at seeding. This is the dedicated, generous ceiling for the import call
    #: (and the spider fallback) so the pipeline seeds large targets without breaking.
    DAST_ZAP_IMPORT_TIMEOUT: int = Field(
        default=300,
        description="Timeout (seconds) for the OpenAPI import / spider seeding call.",
    )
    #: Above this many timed-out requests the target was too slow to trust the run, so
    #: coverage is marked `incomplete`.
    DAST_ZAP_TIMEOUT_THRESHOLD: int = Field(
        default=20,
        description="Timeout count above which coverage is marked incomplete.",
    )
    #: Active scanning sends attack payloads; never do that to production. When set and
    #: matching the target URL, the active adapter refuses to run.
    DAST_ZAP_PROD_URL_PATTERN: Optional[str] = Field(
        default=None,
        description="Regex identifying a production target; active scanning is refused when it matches.",
    )

    # ------------------------------------------------------------------ #
    # Schemathesis (API-fuzzing dynamic scanner)
    # ------------------------------------------------------------------ #
    #: The tool deciding whether a build passes must not change without a reviewed
    #: change, so the CLI is pinned to an exact released version and NEVER `latest`
    #: or a branch. Upgrade it exactly like any other dependency, via a reviewed PR.
    DAST_SCHEMATHESIS_VERSION: str = Field(
        default="3.39.5",
        description="Pinned exact Schemathesis version (never 'latest' or a branch).",
    )
    #: When set, the OpenAPI schema is read from this file instead of being fetched
    #: from the target's DAST_OPENAPI_PATH.
    DAST_SCHEMATHESIS_SCHEMA_FILE: Optional[str] = Field(
        default=None,
        description="Optional file reference for the OpenAPI schema (else fetched from the target).",
    )
    DAST_SCHEMATHESIS_SCHEMA_TIMEOUT: int = Field(
        default=30,
        description="Seconds allowed to load the OpenAPI schema before failing.",
    )
    #: A fixed generation seed makes the fast profile reproducible: the same schema
    #: yields the same cases, so a finding can be re-run and confirmed.
    DAST_SCHEMATHESIS_SEED: int = Field(
        default=0,
        description="Fixed generation seed (integer) for the reproducible fast profile.",
    )
    #: Our staging target is typically a single worker; firing Schemathesis at full
    #: speed jams the door and the scan looks clean because requests never landed.
    DAST_SCHEMATHESIS_RATE_LIMIT: int = Field(
        default=10,
        description="Max requests per second (clamped 1-1000; default applied when out of range).",
    )
    DAST_SCHEMATHESIS_CONNECT_TIMEOUT: int = Field(
        default=30,
        description="Seconds to establish a connection to the target.",
    )
    #: Reachability probe for the ZAP proxy; if we cannot connect in time we refuse
    #: rather than silently send unproxied traffic.
    DAST_SCHEMATHESIS_PROXY_CONNECT_TIMEOUT: int = Field(
        default=5,
        description="Seconds to connect to the ZAP proxy before refusing to send traffic.",
    )
    DAST_SCHEMATHESIS_TIMEOUT: int = Field(
        default=900,
        description="Hard subprocess timeout for one Schemathesis run (seconds).",
    )
    #: Above this many timed-out requests the target was too slow to trust the run, so
    #: coverage is marked `incomplete`.
    DAST_SCHEMATHESIS_TIMEOUT_THRESHOLD: int = Field(
        default=50,
        description="Timeout count (1-100000) above which coverage is marked incomplete.",
    )
    #: Schemathesis sends mutating/attack traffic; never do that to production. When
    #: set and matching the target URL, the adapter refuses to run and sends nothing.
    DAST_SCHEMATHESIS_PROD_URL_PATTERN: Optional[str] = Field(
        default=None,
        description="Regex identifying a production target; scanning is refused when it matches.",
    )

    # ------------------------------------------------------------------ #
    # Endpoint extraction (static source-code walk)
    # ------------------------------------------------------------------ #
    #: Directories/files the extractor never reads. Dependency and version-control
    #: trees hold vendored routes that are not this target's attack surface and would
    #: only slow the walk and pollute the inventory. Comma-separated globs; the default
    #: is non-empty so an absent setting still prunes the obvious noise (Req 9.1, 9.2).
    DAST_EXTRACT_EXCLUDE_PATTERNS: str = Field(
        default="node_modules,vendor,.git,dist,build,__pycache__,.venv,venv,.tox,target",
        description="Comma-separated globs of directories/files the extractor never reads.",
    )
    #: A hard ceiling on how large a Source_File may be before the extractor skips it
    #: unread. A generated bundle or a checked-in data blob is not worth parsing and
    #: could stall the walk. Finite and positive so an absent setting still bounds
    #: traversal (Req 9.5, 9.6); files strictly larger than this are skipped (Req 9.7).
    DAST_EXTRACT_MAX_FILE_BYTES: int = Field(
        default=1_048_576,
        description="Max Source_File size in bytes; larger files are skipped unread.",
    )

    @property
    def dast_extract_exclude_patterns(self) -> tuple[str, ...]:
        """The exclusion patterns parsed into a de-duplicated, ordered collection.

        Splits ``DAST_EXTRACT_EXCLUDE_PATTERNS`` on commas, trims surrounding
        whitespace, and drops empty entries so a stray comma or trailing separator
        never yields a blank pattern that would match everything.
        """
        seen: set[str] = set()
        patterns: list[str] = []
        for raw in self.DAST_EXTRACT_EXCLUDE_PATTERNS.split(","):
            pattern = raw.strip()
            if pattern and pattern not in seen:
                seen.add(pattern)
                patterns.append(pattern)
        return tuple(patterns)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


dast_settings = DastSettings()
