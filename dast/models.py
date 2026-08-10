"""Data models for the standalone DAST service.

The *finding* model is deliberately not redefined here — we import
:class:`~app.security.models.Finding` and friends from the SAST package so both
pipelines speak one schema. What this module adds is the DAST-specific *input*
(what to scan, and how) and the *record* of a scan.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.security.models import Finding


@dataclass(frozen=True)
class DastScope:
    """What a DAST adapter is pointed at.

    The SAST equivalent (:class:`~app.security.models.ScanScope`) carries file
    paths. A DAST scope carries a live target instead — URLs cannot be jammed into
    ``paths`` without every downstream assumption about "this is a file" breaking.
    """

    #: Base URL of the running target, e.g. ``https://staging.example.com``.
    target_url: str
    #: The commit the target is running, when known. Recorded for traceability.
    commit_sha: str = ""
    #: Full ``Authorization`` header value. Without it, scanners test the login page.
    auth_header: Optional[str] = None
    #: Fetched OpenAPI path templates, used to templatise URLs into stable
    #: endpoint identities (see :mod:`dast.urls`).
    spec_paths: tuple[str, ...] = ()
    #: ``fast`` (every deploy, safe) or ``deep`` (nightly, sends real attacks).
    profile: str = "fast"


@dataclass(frozen=True)
class ToolActivity:
    """Evidence that a tool actually did work.

    Every scanner returns an empty finding list when the app is genuinely clean —
    and also when auth silently failed, the target was still booting, or a rate
    limiter started refusing us. A smoke detector with a dead battery is exactly as
    quiet as a house that is not on fire.

    Adapters therefore report what they *did*, not just what they found, so the
    service can tell "clean" apart from "broken".

    Note the distinction between *loaded* and *reached*, learned the hard way: our
    first live runs reported thousands of checks "executed" while every single
    request failed DNS resolution and never left the machine. Counting what the
    tool read off disk proves nothing. Only :attr:`requests_made` — traffic that
    actually reached the target — is evidence.
    """

    #: Checks/templates the tool loaded. Necessary but NOT sufficient: a tool can
    #: load 7,000 templates and reach the target zero times.
    units_executed: Optional[int] = None
    #: Requests that actually left the scanner. ``None`` = the tool did not say.
    requests_made: Optional[int] = None
    #: Requests that failed outright (DNS, connection refused, TLS). If this
    #: equals ``requests_made`` the scan tested nothing at all.
    request_errors: int = 0
    #: Requests that timed out. A high count means results are not trustworthy.
    timeouts: int = 0
    #: Process exit code, when the tool is a subprocess.
    exit_code: Optional[int] = None
    #: Wall-clock seconds the tool ran.
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class ScanOutcome:
    """What one tool produced: the findings *and* the evidence it really ran."""

    findings: tuple[Finding, ...] = ()
    activity: ToolActivity = field(default_factory=ToolActivity)


@runtime_checkable
class DastAdapter(Protocol):
    """A dynamic scanner pointed at a running target.

    Mirrors :class:`~app.security.protocols.ScannerAdapter` but takes a
    :class:`DastScope` and returns a :class:`ScanOutcome`. Returning findings *and*
    activity from the single ``scan`` call is deliberate: it makes reporting "what
    I did" impossible to forget when adding a new tool.

    Adapters are duck-typed against this Protocol; there is no base class.
    """

    name: str
    #: Whether this tool changes the target's state. Read-only tools can run
    #: concurrently; mutating tools must be serialised, because every DAST tool
    #: shares one live application and they interfere with each other.
    mutating: bool

    def scan(self, scope: DastScope) -> ScanOutcome: ...


@dataclass(frozen=True)
class ToolCoverage:
    """Per-tool outcome: did it complete, and what did it actually do?

    The SAST equivalent (:class:`~app.security.models.ScannerCoverage`) records
    status and reason. DAST adds the activity evidence, because a dynamic tool can
    complete successfully having tested nothing at all.
    """

    scanner: str
    status: str  # "complete" | "incomplete"
    reason: Optional[str] = None
    activity: ToolActivity = field(default_factory=ToolActivity)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scanner": self.scanner,
            "status": self.status,
            "reason": self.reason,
            "units_executed": self.activity.units_executed,
            "requests_made": self.activity.requests_made,
            "request_errors": self.activity.request_errors,
            "timeouts": self.activity.timeouts,
            "exit_code": self.activity.exit_code,
            "duration_seconds": self.activity.duration_seconds,
        }


@dataclass(frozen=True)
class DastResult:
    """Everything one scan produced across all tools."""

    findings: tuple[Finding, ...] = ()
    coverage: tuple[ToolCoverage, ...] = ()


class ScanRequest(BaseModel):
    """Body of ``POST /scan`` — sent by the deploy job, a cron, or the UI."""

    target_url: str = Field(description="Base URL of the running target to scan.")
    commit_sha: str = Field(default="", description="Commit the target is running.")
    profile: str = Field(
        default="fast",
        description="'fast' (safe, every deploy) or 'deep' (attacks, nightly).",
    )
    kind: str = Field(
        default="deploy", description="What triggered this: deploy | manual | scheduled."
    )


@dataclass
class ScanRecord:
    """The durable record of one scan. Serialised to JSON on disk."""

    scan_id: str
    target_url: str
    commit_sha: str
    profile: str
    kind: str
    status: str = "queued"  # queued | running | done | failed
    submitted_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None
    #: Deduplicated findings, each carrying a stable ``finding_id``
    #: (see :func:`dast.storage.normalized_finding_to_dict`).
    findings: list[dict[str, Any]] = field(default_factory=list)
    #: How many findings the tools reported before deduplication. One rule firing
    #: on 400 URLs is 400 raw findings and 1 real problem; showing both keeps the
    #: report honest without drowning it.
    raw_finding_count: int = 0
    #: Per-tool coverage: complete/incomplete plus the activity evidence above.
    coverage: list[dict[str, Any]] = field(default_factory=list)
    preflight: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        """Compact form for the scan list view (no findings payload)."""
        counts: dict[str, int] = {}
        for finding in self.findings:
            severity = str(finding.get("severity", "UNKNOWN"))
            counts[severity] = counts.get(severity, 0) + 1
        return {
            "scan_id": self.scan_id,
            "target_url": self.target_url,
            "commit_sha": self.commit_sha,
            "profile": self.profile,
            "kind": self.kind,
            "status": self.status,
            "submitted_at": self.submitted_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "finding_count": len(self.findings),
            "raw_finding_count": self.raw_finding_count,
            "severity_counts": counts,
            "incomplete_tools": [
                c["scanner"] for c in self.coverage if c.get("status") != "complete"
            ],
        }
