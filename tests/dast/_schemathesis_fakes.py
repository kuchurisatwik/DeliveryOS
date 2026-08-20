"""In-memory fake for the Schemathesis command-builder + ``run_scanner`` seam.

The real :class:`dast.adapters.schemathesis_adapter.SchemathesisAdapter` drives the
Schemathesis CLI as a subprocess through a single, deliberately narrow method —
:meth:`SchemathesisAdapter._run`, which wraps ``sast_base.run_scanner`` inside the
proxy-environment context manager. Everything the trust invariants care about is
decided *before* that call and handed to it as two values: the exact **argument
vector** (carrying ``--base-url``, ``--header``, ``--request-proxy``,
``--hypothesis-seed``, ``--rate-limit`` …) and the **subprocess environment**
(carrying ``HTTP_PROXY`` / ``HTTPS_PROXY``). The report the adapter then parses, and
the run statistics it reads, come straight out of that subprocess.

So a single substitution at ``_run`` is enough to exercise the whole of ``scan()``
with no subprocess and no network:

* it **records** the ``(argv, env)`` the adapter would have executed, so a test can
  assert over the auth header, proxy flag/vars, base URL, seed, and rate limit;
* it **injects** a configurable report + run-stats by writing them to the temp report
  file the adapter passed via ``--report-json-path``, so ``scan()`` parses real
  findings and reads real request evidence back; and
* it **returns** a configurable :class:`CompletedScan` (exit code / stdout / stderr),
  so the hard-failure and soft-evidence paths can both be driven.

This mirrors the ZAP fake-client approach (``tests/dast/_zap_fakes.py``): the adapter
is written against a seam, and the fake substitutes cleanly at it. This module is test
infrastructure only; it is never imported by production code.

Supports Properties 9–14, 16 and 17 (auth-everywhere, proxy routing, base-URL
confinement, seed determinism, rate-limit clamping, production refusal, hard-failure
isolation) plus the run-stats fixture unit tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.security.detection.adapters.base import CompletedScan
from dast.adapters.schemathesis_adapter import SchemathesisAdapter

#: Scanner name the adapter uses; re-exported so error-path assertions read identically.
SCANNER_NAME = "schemathesis"

#: The ``--cassette-path`` flag whose value tells the fake where to drop the report.
#: (The adapter reads this file back via ``_load_report``, which accepts either a
#: real VCR cassette or a report already in parse()'s shape — as the fake writes.)
_REPORT_FLAG = "--cassette-path"

# --------------------------------------------------------------------------- #
# Saved fixture: a real Schemathesis run summary
# --------------------------------------------------------------------------- #
_FIXTURES_DIR = Path(__file__).parent / "fixtures"

#: A captured machine-readable run summary from a real fast-profile scan. Its
#: ``statistics`` block is what ``_run_statistics`` reads request evidence from, and it
#: deliberately carries a ``generated_cases`` count far larger than ``requests_made`` so
#: a test can prove evidence comes from requests reached, never from cases generated.
RUN_STATS_FIXTURE = _FIXTURES_DIR / "schemathesis_run_stats.json"


def load_run_stats_fixture() -> dict[str, Any]:
    """Load the saved Schemathesis run-summary fixture as a decoded mapping."""
    return json.loads(RUN_STATS_FIXTURE.read_text(encoding="utf-8"))


def fixture_statistics() -> dict[str, Any]:
    """Just the ``statistics`` block of the saved run-summary fixture."""
    return dict(load_run_stats_fixture()["statistics"])


# --------------------------------------------------------------------------- #
# Recorded run — what the adapter WOULD have executed
# --------------------------------------------------------------------------- #
@dataclass
class RecordedRun:
    """One captured invocation of the ``_run`` seam.

    Holds the exact argument vector and subprocess environment the adapter handed to
    the runner, plus the temp report path it targeted. The convenience accessors below
    read the flags the trust invariants assert over, so property tests need not know
    the argv layout.
    """

    argv: list[str]
    env: dict[str, str]
    report_path: str | None = None

    # -- generic flag access ------------------------------------------------- #
    def flag(self, name: str) -> str | None:
        """The value following the first ``name`` occurrence, or ``None`` if absent."""
        for i, token in enumerate(self.argv):
            if token == name and i + 1 < len(self.argv):
                return self.argv[i + 1]
        return None

    def flag_values(self, name: str) -> list[str]:
        """Every value following each ``name`` occurrence (e.g. repeated ``--header``)."""
        values: list[str] = []
        for i, token in enumerate(self.argv):
            if token == name and i + 1 < len(self.argv):
                values.append(self.argv[i + 1])
        return values

    def has_flag(self, name: str) -> bool:
        """True when ``name`` appears anywhere in the argument vector."""
        return name in self.argv

    # -- the specific flags the invariants care about ------------------------ #
    @property
    def base_url(self) -> str | None:
        """Value of ``--base-url`` — every request must target only this (Property 11)."""
        return self.flag("--base-url")

    @property
    def header(self) -> str | None:
        """Value of the first ``--header`` (the auth header when set, Property 9)."""
        return self.flag("--header")

    @property
    def headers(self) -> list[str]:
        """All ``--header`` values passed to the CLI (Property 9)."""
        return self.flag_values("--header")

    @property
    def request_proxy(self) -> str | None:
        """Value of ``--request-proxy`` — present only when a proxy is configured (Property 10)."""
        return self.flag("--request-proxy")

    @property
    def seed(self) -> str | None:
        """Value of ``--hypothesis-seed`` — present on fast, absent on deep (Property 12)."""
        return self.flag("--hypothesis-seed")

    @property
    def rate_limit(self) -> str | None:
        """Value of ``--rate-limit`` (e.g. ``"10/s"``) — clamped into range (Property 14)."""
        return self.flag("--rate-limit")

    @property
    def http_proxy(self) -> str | None:
        """``HTTP_PROXY`` exported for the subprocess, or ``None`` (Property 10)."""
        return self.env.get("HTTP_PROXY")

    @property
    def https_proxy(self) -> str | None:
        """``HTTPS_PROXY`` exported for the subprocess, or ``None`` (Property 10)."""
        return self.env.get("HTTPS_PROXY")


# --------------------------------------------------------------------------- #
# The fake seam
# --------------------------------------------------------------------------- #
class FakeSchemathesisRun:
    """A drop-in stand-in for :meth:`SchemathesisAdapter._run`.

    Assign an instance to ``adapter._run`` (or use :func:`attach`) and it will, on each
    call: record the ``(argv, env)`` as a :class:`RecordedRun`, write the configured
    report to the temp path the adapter chose, and return the configured
    :class:`CompletedScan`. Because it is stored as an *instance attribute* it is
    invoked as ``fake(argv, env)`` — no ``self`` from the adapter — so its signature
    matches the seam exactly.

    Configure it with:

    * ``report`` — the full decoded report the adapter should parse (cases + optional
      ``statistics`` block). Build one with :func:`make_report`.
    * ``run_stats`` — sugar for the statistics block alone; merged into ``report`` under
      ``"statistics"`` when ``report`` does not already carry one. Pass
      :func:`fixture_statistics` to drive from the saved fixture.
    * ``returncode`` / ``stdout`` / ``stderr`` — the subprocess result. A non-zero
      ``returncode`` with no request evidence drives the hard-failure path (Property 17).
    """

    def __init__(
        self,
        *,
        report: Mapping[str, Any] | None = None,
        run_stats: Mapping[str, Any] | None = None,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        self.configured_report = self._merge_stats(report, run_stats)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

        #: Every recorded invocation, in order (usually exactly one per ``scan()``).
        self.calls: list[RecordedRun] = []

    @staticmethod
    def _merge_stats(
        report: Mapping[str, Any] | None, run_stats: Mapping[str, Any] | None
    ) -> dict[str, Any] | None:
        """Combine a report and a standalone stats block into one report mapping."""
        if report is None and run_stats is None:
            return None
        merged: dict[str, Any] = dict(report or {})
        if run_stats is not None and "statistics" not in merged:
            merged["statistics"] = dict(run_stats)
        return merged

    # ------------------------------------------------------------------ #
    # The seam itself
    # ------------------------------------------------------------------ #
    def __call__(self, argv: Sequence[str], env: Mapping[str, str]) -> CompletedScan:
        argv_list = [str(token) for token in argv]
        env_dict = {str(k): str(v) for k, v in dict(env).items()}
        report_path = self._report_path(argv_list)

        # Inject the configurable report at the exact path the adapter will read. When
        # no report is configured the temp file is left empty, so parse() yields no
        # findings — the shape of a hard-failure/aborted run.
        if report_path is not None and self.configured_report is not None:
            with open(report_path, "w", encoding="utf-8") as fh:
                json.dump(self.configured_report, fh)

        self.calls.append(
            RecordedRun(argv=argv_list, env=env_dict, report_path=report_path)
        )
        return CompletedScan(
            stdout=self.stdout, stderr=self.stderr, returncode=self.returncode
        )

    @staticmethod
    def _report_path(argv: Sequence[str]) -> str | None:
        for i, token in enumerate(argv):
            if token == _REPORT_FLAG and i + 1 < len(argv):
                return argv[i + 1]
        return None

    # ------------------------------------------------------------------ #
    # Inspection convenience (delegates to the last recorded run)
    # ------------------------------------------------------------------ #
    @property
    def called(self) -> bool:
        """True once the adapter has driven the seam at least once."""
        return bool(self.calls)

    @property
    def last(self) -> RecordedRun:
        """The most recent recorded run; raises if the seam was never reached."""
        if not self.calls:
            raise AssertionError(
                "FakeSchemathesisRun was never called — scan() aborted before "
                "building the command (e.g. a hard failure raised earlier)."
            )
        return self.calls[-1]


# --------------------------------------------------------------------------- #
# Wiring helpers
# --------------------------------------------------------------------------- #
def attach(adapter: SchemathesisAdapter, fake: FakeSchemathesisRun) -> FakeSchemathesisRun:
    """Substitute ``fake`` for the adapter's ``_run`` seam and return it for inspection."""
    adapter._run = fake  # type: ignore[method-assign, assignment]
    return fake


def make_adapter(
    *,
    settings: Any,
    fake: FakeSchemathesisRun,
    binary: str = "schemathesis",
) -> SchemathesisAdapter:
    """Construct a :class:`SchemathesisAdapter` with the seam already faked."""
    adapter = SchemathesisAdapter(settings=settings, binary=binary)
    attach(adapter, fake)
    return adapter


# --------------------------------------------------------------------------- #
# Report / stats builders (for constructing configurable fake reports)
# --------------------------------------------------------------------------- #
def make_check(name: str, *, failed: bool = True) -> dict[str, Any]:
    """One check-result entry as it appears in a Schemathesis case's ``checks`` list."""
    return {"name": name, "status": "failure" if failed else "success"}


def make_case(
    *,
    method: str = "GET",
    path: str = "/",
    uri: str | None = None,
    status_code: int = 200,
    failed_checks: Sequence[str] = (),
    passed_checks: Sequence[str] = (),
    headers: Mapping[str, str] | None = None,
    body: Any = None,
) -> dict[str, Any]:
    """Build one Schemathesis *case* (a request + response + the checks that ran).

    ``failed_checks`` become failing check entries (so ``parse`` emits findings);
    ``passed_checks`` become passing ones. The request records ``method``/``uri`` and
    any headers so ``parse`` can build the reproducing request.
    """
    request: dict[str, Any] = {
        "method": method,
        "uri": uri if uri is not None else f"http://target{path}",
        "headers": dict(headers or {}),
    }
    if body is not None:
        request["body"] = body
    checks = [make_check(name, failed=True) for name in failed_checks]
    checks += [make_check(name, failed=False) for name in passed_checks]
    return {
        "method": method,
        "path": path,
        "request": request,
        "response": {"status_code": status_code},
        "checks": checks,
    }


def make_stats(
    *,
    requests_made: int = 4791,
    request_errors: int = 0,
    timeouts: int = 0,
    generated_cases: int | None = None,
) -> dict[str, Any]:
    """Build a ``statistics`` block matching what ``_run_statistics`` reads.

    ``generated_cases`` (when given) sits alongside the request counts to let a test
    prove evidence is read from requests reached, never from the case count.
    """
    stats: dict[str, Any] = {
        "requests_made": requests_made,
        "request_errors": request_errors,
        "timeouts": timeouts,
    }
    if generated_cases is not None:
        stats["generated_cases"] = generated_cases
    return stats


def make_report(
    *,
    cases: Sequence[Mapping[str, Any]] = (),
    stats: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a decoded Schemathesis report from cases and an optional stats block."""
    report: dict[str, Any] = {"results": [dict(case) for case in cases]}
    if stats is not None:
        report["statistics"] = dict(stats)
    return report
