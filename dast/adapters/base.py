"""Helpers shared by DAST adapters.

The subprocess plumbing (:func:`run_scanner`, :class:`ScannerError`, temp-report
handling, severity mapping) is reused as-is from the SAST package — a tool is a
tool. What DAST adds is a location built from a *URL* rather than a file path, and
a reader for line-delimited JSON, which several dynamic scanners emit so results
can stream as they are found.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from typing import Any, Callable, Iterable

from app.security.detection.adapters.base import CompletedScan, ScannerError
from app.security.models import Location
from app.utils.logger import logger
from dast.urls import endpoint_identity


def run_scanner_cancellable(
    command: "list[str]",
    *,
    scanner_name: str,
    timeout: int,
    health_check: "Callable[[], bool] | None" = None,
    health_interval: float = 20.0,
    poll_interval: float = 1.0,
) -> CompletedScan:
    """Run a subprocess that can be aborted early when the target dies.

    This is the streaming counterpart to the SAST package's blocking
    :func:`run_scanner`. It exists for the one DAST case that helper cannot cover:
    a long-running scanner (nuclei) pointed at a target that *crashes mid-run*.
    With the blocking runner, nuclei keeps hammering a dead host until its full
    subprocess timeout (e.g. 900s) before anyone notices. Here a watchdog probes
    ``health_check`` every ``health_interval`` seconds and kills the process the
    moment the target is confirmed unreachable, so the tool degrades to a fast,
    honest ``incomplete`` instead of a long stall.

    Output is written to temp files rather than pipes so the poll loop cannot
    deadlock on a full pipe buffer. When ``health_check`` is ``None`` this behaves
    like a plain timed run.
    """
    argv = list(command)
    resolved = shutil.which(argv[0])
    if resolved is None:
        raise ScannerError(
            scanner_name, f"tool not installed: '{argv[0]}' not found on PATH"
        )
    argv[0] = resolved

    logger.info("Running scanner '%s': %s", scanner_name, " ".join(argv))
    # Temp files avoid the classic Popen pipe-buffer deadlock while we poll.
    out_f = tempfile.TemporaryFile(mode="w+b")
    err_f = tempfile.TemporaryFile(mode="w+b")
    try:
        try:
            proc = subprocess.Popen(argv, stdout=out_f, stderr=err_f)
        except FileNotFoundError as exc:
            raise ScannerError(
                scanner_name, f"tool not installed: '{argv[0]}' not found on PATH"
            ) from exc
        except OSError as exc:  # pragma: no cover - platform dependent
            raise ScannerError(scanner_name, f"failed to launch: {exc}") from exc

        deadline = time.monotonic() + timeout
        last_health = time.monotonic()
        while proc.poll() is None:
            now = time.monotonic()
            if now >= deadline:
                _kill(proc)
                raise ScannerError(scanner_name, f"timed out after {timeout}s")
            if health_check is not None and (now - last_health) >= health_interval:
                last_health = now
                try:
                    healthy = health_check()
                except Exception as exc:  # noqa: BLE001 - a broken probe never gates a scan
                    logger.warning("%s health probe errored (ignoring): %s", scanner_name, exc)
                    healthy = True
                if not healthy:
                    _kill(proc)
                    raise ScannerError(
                        scanner_name,
                        "target became unreachable mid-scan; aborted early to avoid "
                        "hammering a dead target",
                    )
            time.sleep(poll_interval)

        out_f.seek(0)
        err_f.seek(0)
        stdout = out_f.read().decode("utf-8", "replace")
        stderr = err_f.read().decode("utf-8", "replace")
        logger.info("Scanner '%s' finished with exit code %s", scanner_name, proc.returncode)
        return CompletedScan(stdout=stdout, stderr=stderr, returncode=proc.returncode)
    finally:
        out_f.close()
        err_f.close()


def _kill(proc: "subprocess.Popen[bytes]") -> None:
    """Terminate a subprocess and reap it, tolerating an already-dead process."""
    try:
        proc.kill()
        proc.wait(timeout=10)
    except Exception:  # noqa: BLE001 - best-effort cleanup
        pass


def make_web_location(
    url: str,
    *,
    method: str | None = None,
    param: str | None = None,
    spec_paths: Iterable[str] = (),
) -> Location:
    """Build a :class:`Location` for a finding on a live endpoint.

    A web finding has no file and no line number, so those are zero. The path
    carries the *endpoint identity* — host stripped, dynamic segments templatised
    (see :mod:`dast.urls`) — optionally prefixed with the HTTP method, since
    ``GET /orders`` and ``DELETE /orders`` are genuinely different attack surface.

    The affected parameter goes on ``symbol``, so two findings on the same endpoint
    but different parameters stay distinct.
    """
    path = endpoint_identity(url, spec_paths)
    label = f"{method.upper()} {path}" if method else path
    return Location(path=label, start_line=0, end_line=0, symbol=param)


def load_jsonl(text: str, *, scanner_name: str) -> list[Any]:
    """Decode line-delimited JSON into a list of events.

    Unlike :func:`app.security.detection.adapters.base.load_json`, **empty input is
    not an error**: a dynamic scanner that found nothing legitimately writes an
    empty report. Distinguishing "found nothing" from "did nothing" is the job of
    the adapter's activity reporting, not of the parser.

    Blank lines are skipped. A malformed line fails the whole parse rather than
    being silently dropped — quietly discarding findings is the one outcome worse
    than crashing.
    """
    events: list[Any] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            events.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            raise ScannerError(
                scanner_name, f"could not parse JSONL output at line {lineno}: {exc}"
            ) from exc
    return events
