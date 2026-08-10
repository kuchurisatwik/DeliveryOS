"""Runs the DAST tools against one target and aggregates their output.

The SAST detection stage fans every scanner out across a thread pool, which is
correct there: those tools only *read* a filesystem, so they cannot interfere.

DAST tools cannot be treated that way. They all hit the same live application, and
they are not read-only. An active scan writes records that the next tool then
reads; a content fuzzer can trip a rate limiter that makes every tool after it see
clean responses. So tools are split into two tiers:

* **read-only** — run concurrently, like the SAST scanners;
* **mutating** — run one at a time, in a defined order.

The tier is declared on the adapter (``mutating``), not decided here, so adding a
new tool cannot accidentally get it wrong.

Per-tool failure is isolated exactly as in the SAST runner: one tool blowing up
records an ``incomplete`` coverage entry and the rest of the scan continues.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Sequence

from app.security.detection.adapters.base import ScannerError
from app.security.models import Finding
from app.utils.logger import logger
from dast.adapters import NucleiAdapter
from dast.models import (
    DastAdapter,
    DastResult,
    DastScope,
    ScanOutcome,
    ToolActivity,
    ToolCoverage,
)


def default_adapters(profile: str = "fast") -> list[DastAdapter]:
    """Build the tool set for a scan profile.

    * ``fast`` — safe enough for every deploy; nothing here sends attack payloads.
    * ``deep`` — adds the slow, intrusive tools. Staging only.

    Phase 1 ships nuclei only, so both profiles are currently the same. ZAP,
    Schemathesis, sqlmap and testssl.sh slot in here as they land.
    """
    adapters: list[DastAdapter] = [NucleiAdapter()]
    return adapters


def run_scan(scope: DastScope, adapters: Sequence[DastAdapter] | None = None) -> DastResult:
    """Run every adapter against ``scope`` and aggregate findings + coverage."""
    tools = list(adapters if adapters is not None else default_adapters(scope.profile))
    read_only = [t for t in tools if not getattr(t, "mutating", False)]
    mutating = [t for t in tools if getattr(t, "mutating", False)]

    logger.info(
        "DAST scan starting on %s (profile=%s): %d read-only tool(s) in parallel, "
        "%d mutating tool(s) in sequence",
        scope.target_url,
        scope.profile,
        len(read_only),
        len(mutating),
    )

    findings: list[Finding] = []
    coverage: list[ToolCoverage] = []

    # Read-only tools cannot interfere with each other, so run them together.
    if read_only:
        with ThreadPoolExecutor(max_workers=len(read_only)) as pool:
            for tool_findings, tool_coverage in pool.map(
                lambda tool: _run_one(tool, scope), read_only
            ):
                findings.extend(tool_findings)
                coverage.append(tool_coverage)

    # Mutating tools change the target's state; running them concurrently would
    # make every result after the first untrustworthy.
    for tool in mutating:
        tool_findings, tool_coverage = _run_one(tool, scope)
        findings.extend(tool_findings)
        coverage.append(tool_coverage)

    complete = sum(1 for c in coverage if c.status == "complete")
    logger.info(
        "DAST scan finished on %s: %d finding(s), %d/%d tool(s) completed",
        scope.target_url,
        len(findings),
        complete,
        len(coverage),
    )
    return DastResult(findings=tuple(findings), coverage=tuple(coverage))


def _run_one(tool: DastAdapter, scope: DastScope) -> tuple[list[Finding], ToolCoverage]:
    """Run one adapter, converting any failure into an ``incomplete`` coverage entry."""
    started = time.monotonic()
    try:
        outcome: ScanOutcome = tool.scan(scope)
    except ScannerError as exc:
        logger.warning("DAST tool '%s' failed: %s", tool.name, exc.reason)
        return [], ToolCoverage(
            scanner=tool.name,
            status="incomplete",
            reason=exc.reason,
            activity=ToolActivity(duration_seconds=round(time.monotonic() - started, 2)),
        )
    except Exception as exc:  # noqa: BLE001 - one bad tool never kills the scan
        logger.error("DAST tool '%s' raised unexpectedly: %s", tool.name, exc)
        return [], ToolCoverage(
            scanner=tool.name,
            status="incomplete",
            reason=f"unexpected error: {str(exc)[:300]}",
            activity=ToolActivity(duration_seconds=round(time.monotonic() - started, 2)),
        )

    status, reason = _assess_activity(tool.name, outcome)
    return list(outcome.findings), ToolCoverage(
        scanner=tool.name, status=status, reason=reason, activity=outcome.activity
    )


def _assess_activity(name: str, outcome: ScanOutcome) -> tuple[str, str | None]:
    """Decide whether a completed tool run actually tested anything.

    A tool that returns no findings *and* no evidence of work has not told us the
    app is clean — it has told us nothing. Marking that ``complete`` is how an
    empty scan gets mistaken for a passing one.

    The checks are ordered by how conclusively they prove the scan was worthless,
    strongest first. The ``requests_made``/``request_errors`` pair matters most:
    our first live runs loaded ~7,000 templates and reported ``complete`` while
    every request failed DNS resolution and never left the machine. Counting
    loaded checks is not evidence; counting delivered requests is.
    """
    activity = outcome.activity

    if activity.units_executed == 0:
        return "incomplete", "tool executed zero checks"

    if activity.requests_made == 0:
        return (
            "incomplete",
            "tool sent zero requests — the target was never actually contacted",
        )

    if activity.requests_made and activity.request_errors >= activity.requests_made:
        return (
            "incomplete",
            f"all {activity.requests_made} request(s) failed (DNS, connection "
            "refused, or TLS) — the scanner could not reach the target",
        )

    # A few failures are normal on a large template set; a majority means most of
    # the scan surface went untested and a clean result would be misleading.
    if activity.requests_made and activity.request_errors > activity.requests_made * 0.5:
        return (
            "incomplete",
            f"{activity.request_errors}/{activity.requests_made} request(s) failed — "
            "most of the scan did not reach the target",
        )

    if activity.requests_made is None and not outcome.findings:
        return (
            "incomplete",
            "tool reported no findings and gave no evidence it contacted the "
            "target; treating as unverified",
        )

    # A handful of timeouts is normal; a flood means the target was overwhelmed and
    # the checks that timed out silently tested nothing.
    if activity.timeouts and activity.units_executed:
        if activity.timeouts > max(10, activity.units_executed * 0.05):
            return (
                "incomplete",
                f"{activity.timeouts} request timeout(s) — target may be overloaded; "
                "lower the rate limit",
            )
    return "complete", None
