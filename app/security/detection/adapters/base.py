"""Shared subprocess + output-parsing helpers for scanner adapters.

This module factors out the logic every scanner adapter needs so the six
concrete adapters stay small and focused on tool-specific command construction
and payload shape:

* :class:`ScannerError` — the single, well-defined failure signal every adapter
  raises when its tool is missing, times out, or fails unrecoverably. The Layer 2
  runner (task 4.1) catches this and records a ``ScannerCoverage`` entry with
  ``status = "incomplete"`` while keeping other scanners' findings (Requirement 3.4,
  design "Fail-open on scanner/parse errors").
* :func:`run_scanner` — runs a tool as a subprocess following the conventions used
  by ``app/services/validators.py`` / ``app/services/test_executor.py``
  (``subprocess.run`` with ``capture_output``/``text``/``check=False``, an inherited
  environment, an explicit ``cwd``), adding a timeout and mapping the
  tool-not-installed / launch-failure / timeout cases onto :class:`ScannerError`.
* :func:`load_json` — parses a tool's JSON/SARIF stdout, raising :class:`ScannerError`
  on undecodable output.
* :func:`map_severity` / :func:`severity_from_sarif_level` — translate a tool's native
  severity vocabulary into the shared :class:`Severity` enum.
* :func:`parse_sarif` — a reusable SARIF 2.1.0 → ``list[Finding]`` parser for the
  adapters whose tools emit SARIF (e.g. CodeQL).

The "run subprocess" step (:func:`run_scanner`) is deliberately separated from the
"parse output" step (each adapter's ``parse`` method + :func:`parse_sarif`) so the
parsers are pure and unit-testable against canned SARIF/JSON without spawning a
process (integration tests: task 4.6).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.security.models import Finding, Location, Severity
from app.utils.logger import logger

# Default per-scanner subprocess timeout (seconds). Generous because semantic
# scanners (CodeQL) and dependency scanners (Trivy) can take a while, but bounded
# so a hung tool degrades to a per-scanner failure rather than stalling the run.
DEFAULT_TIMEOUT = 600


class ScannerError(RuntimeError):
    """Raised when a scanner adapter cannot produce findings.

    Covers tool-not-installed, launch failures, timeouts, and unrecoverable
    non-zero exits with unparseable output. The runner treats any ``ScannerError``
    as a per-scanner failure: it records the scanner's coverage as ``incomplete``
    with :attr:`reason` and continues with the remaining scanners.
    """

    def __init__(self, scanner: str, reason: str) -> None:
        self.scanner = scanner
        self.reason = reason
        super().__init__(f"[{scanner}] {reason}")


@dataclass(frozen=True)
class CompletedScan:
    """The raw result of running a scanner subprocess."""

    stdout: str
    stderr: str
    returncode: int


def run_scanner(
    command: Sequence[str],
    *,
    scanner_name: str,
    cwd: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> CompletedScan:
    """Run ``command`` as a subprocess and capture its output.

    Follows the existing subprocess-service conventions (``capture_output``,
    ``text=True``, ``check=False``, explicit ``cwd``) and maps the failure modes a
    scanner can hit onto :class:`ScannerError`:

    * the tool binary is not installed (``FileNotFoundError``),
    * the tool cannot be launched (``OSError``),
    * the tool exceeds ``timeout`` (``subprocess.TimeoutExpired``).

    A non-zero exit is *not* treated as failure here: many scanners use non-zero
    exit codes to signal "findings were reported". Each adapter decides how to
    interpret the exit code together with the parsed payload.
    """

    # Resolve the tool to an absolute path via shutil.which. This respects
    # PATHEXT on Windows (so a tool installed as ``foo.cmd``/``foo.bat`` — e.g.
    # Checkov — resolves, not just ``foo.exe``) and lets us fail fast with a clear
    # "not installed" message. Python's subprocess on Windows otherwise only
    # auto-appends ``.exe`` when given a bare name.
    argv = list(command)
    resolved = shutil.which(argv[0])
    if resolved is None:
        raise ScannerError(
            scanner_name, f"tool not installed: '{argv[0]}' not found on PATH"
        )
    argv[0] = resolved

    logger.info("Running scanner '%s': %s", scanner_name, " ".join(argv))
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
            cwd=cwd,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise ScannerError(
            scanner_name, f"tool not installed: '{argv[0]}' not found on PATH"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ScannerError(
            scanner_name, f"timed out after {timeout}s"
        ) from exc
    except OSError as exc:  # pragma: no cover - platform dependent
        raise ScannerError(scanner_name, f"failed to launch: {exc}") from exc

    logger.info(
        "Scanner '%s' finished with exit code %s", scanner_name, proc.returncode
    )
    return CompletedScan(stdout=proc.stdout, stderr=proc.stderr, returncode=proc.returncode)


def load_json(text: str, *, scanner_name: str, stderr: str = "") -> Any:
    """Parse ``text`` as JSON (or SARIF), raising :class:`ScannerError` on failure.

    Empty output is treated as a parse failure because a well-behaved scanner run
    always emits at least an empty result document; empty output usually means the
    tool errored before producing a report.
    """

    if not text.strip():
        raise ScannerError(
            scanner_name,
            f"empty output; tool produced no report{f': {stderr.strip()}' if stderr.strip() else ''}",
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ScannerError(
            scanner_name,
            f"could not parse output as JSON: {exc}"
            f"{f'; stderr: {stderr.strip()}' if stderr.strip() else ''}",
        ) from exc


def new_temp_report(suffix: str) -> str:
    """Create an empty temp file for a scanner's report and return its path.

    Adapters whose tools mix progress logging into stdout (CodeQL, Bandit,
    Checkov) write their machine-readable report to this file instead of stdout,
    so the report is never polluted by log lines / banners.
    """

    fd, path = tempfile.mkstemp(prefix="secscan-", suffix=suffix)
    os.close(fd)
    return path


def read_report(path: str) -> str:
    """Read a scanner's report file, returning ``""`` when absent/unreadable."""

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def cleanup(path: str | None) -> None:
    """Best-effort removal of a temp report file."""

    if not path:
        return
    try:
        os.remove(path)
    except OSError:  # pragma: no cover - best effort
        pass


def load_json_multi(text: str, *, scanner_name: str, stderr: str = "") -> list[Any]:
    """Decode one or more *concatenated* JSON documents into a list.

    Some tools (e.g. Checkov scanning multiple frameworks) emit several JSON
    objects back-to-back rather than a single JSON value, which ``json.loads``
    rejects with "Extra data". This decodes each document in turn.
    """

    stripped = text.strip()
    if not stripped:
        raise ScannerError(
            scanner_name,
            f"empty output; tool produced no report{f': {stderr.strip()}' if stderr.strip() else ''}",
        )
    decoder = json.JSONDecoder()
    docs: list[Any] = []
    idx = 0
    length = len(stripped)
    while idx < length:
        while idx < length and stripped[idx].isspace():
            idx += 1
        if idx >= length:
            break
        try:
            obj, end = decoder.raw_decode(stripped, idx)
        except json.JSONDecodeError as exc:
            raise ScannerError(
                scanner_name, f"could not parse output as JSON: {exc}"
            ) from exc
        docs.append(obj)
        idx = end
    return docs


def map_severity(
    value: str | None,
    mapping: Mapping[str, Severity],
    default: Severity,
) -> Severity:
    """Map a tool's native severity string onto the shared :class:`Severity` enum.

    Lookup is case-insensitive; unknown or missing values fall back to ``default``.
    """

    if value is None:
        return default
    return mapping.get(value.strip().upper(), default)


# SARIF result-level severities (``result.level``) → shared Severity.
_SARIF_LEVEL_MAP: dict[str, Severity] = {
    "ERROR": Severity.HIGH,
    "WARNING": Severity.MEDIUM,
    "NOTE": Severity.LOW,
    "NONE": Severity.INFO,
}


def severity_from_security_severity(score: str | float | None) -> Severity | None:
    """Map a SARIF ``security-severity`` numeric score (0–10) to a Severity.

    Uses the conventional CVSS-style bands. Returns ``None`` when no usable score
    is present so callers can fall back to the SARIF ``level``.
    """

    if score is None:
        return None
    try:
        value = float(score)
    except (TypeError, ValueError):
        return None
    if value >= 9.0:
        return Severity.CRITICAL
    if value >= 7.0:
        return Severity.HIGH
    if value >= 4.0:
        return Severity.MEDIUM
    if value > 0.0:
        return Severity.LOW
    return Severity.INFO


def severity_from_sarif_level(level: str | None, default: Severity = Severity.MEDIUM) -> Severity:
    """Map a SARIF ``result.level`` string to a shared :class:`Severity`."""

    return map_severity(level, _SARIF_LEVEL_MAP, default)


def parse_sarif(
    payload: Mapping[str, Any],
    *,
    scanner_name: str,
    default_severity: Severity = Severity.MEDIUM,
) -> list[Finding]:
    """Parse a SARIF 2.1.0 document into a list of :class:`Finding`.

    Reusable across every adapter whose tool emits SARIF. Severity is taken from
    the rule's ``security-severity`` property when present, otherwise from the
    result ``level``. Each :class:`Finding` retains the originating ``scanner``
    (provenance, Requirement 3.5), ``rule_id``, source :class:`Location`, mapped
    ``severity``, ``message``, and the original SARIF ``result`` object as ``raw``.
    """

    findings: list[Finding] = []
    runs = payload.get("runs") or []
    for run in runs:
        # Build a rule_id -> security-severity lookup from the run's rule metadata.
        rule_scores: dict[str, str] = {}
        tool = run.get("tool") or {}
        driver = tool.get("driver") or {}
        for rule in driver.get("rules") or []:
            rule_id = rule.get("id")
            props = rule.get("properties") or {}
            if rule_id is not None and "security-severity" in props:
                rule_scores[rule_id] = props["security-severity"]

        for result in run.get("results") or []:
            rule_id = result.get("ruleId") or result.get("rule", {}).get("id") or "unknown"
            severity = (
                severity_from_security_severity(rule_scores.get(rule_id))
                or severity_from_sarif_level(result.get("level"), default_severity)
            )
            message = ""
            msg = result.get("message")
            if isinstance(msg, Mapping):
                message = msg.get("text") or msg.get("markdown") or ""
            elif isinstance(msg, str):
                message = msg

            location = _first_sarif_location(result)
            findings.append(
                Finding(
                    scanner=scanner_name,
                    rule_id=str(rule_id),
                    location=location,
                    severity=severity,
                    message=message,
                    raw=dict(result),
                )
            )
    return findings


def _first_sarif_location(result: Mapping[str, Any]) -> Location:
    """Extract the primary source location from a SARIF result (best-effort)."""

    locations = result.get("locations") or []
    if locations:
        phys = locations[0].get("physicalLocation") or {}
        artifact = phys.get("artifactLocation") or {}
        region = phys.get("region") or {}
        path = artifact.get("uri") or "<unknown>"
        start_line = int(region.get("startLine") or 0)
        end_line = int(region.get("endLine") or start_line)
        symbol = None
        logical = result.get("locations", [{}])[0].get("logicalLocations") or []
        if logical:
            symbol = logical[0].get("fullyQualifiedName") or logical[0].get("name")
        return Location(path=path, start_line=start_line, end_line=end_line, symbol=symbol)
    return Location(path="<unknown>", start_line=0, end_line=0)


def make_location(
    path: str,
    start_line: int | None,
    end_line: int | None = None,
    symbol: str | None = None,
) -> Location:
    """Construct a :class:`Location`, tolerating missing/None line numbers."""

    start = int(start_line or 0)
    end = int(end_line if end_line is not None else start)
    if end < start:
        end = start
    return Location(path=path or "<unknown>", start_line=start, end_line=end, symbol=symbol)
