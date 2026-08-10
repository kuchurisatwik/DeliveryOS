"""Helpers shared by DAST adapters.

The subprocess plumbing (:func:`run_scanner`, :class:`ScannerError`, temp-report
handling, severity mapping) is reused as-is from the SAST package — a tool is a
tool. What DAST adds is a location built from a *URL* rather than a file path, and
a reader for line-delimited JSON, which several dynamic scanners emit so results
can stream as they are found.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from app.security.detection.adapters.base import ScannerError
from app.security.models import Location
from dast.urls import endpoint_identity


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
