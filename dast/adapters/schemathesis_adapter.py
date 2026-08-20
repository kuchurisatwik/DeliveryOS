"""Schemathesis adapter — does our API behave the way its OpenAPI spec promises?

Where :class:`~dast.adapters.nuclei_adapter.NucleiAdapter` answers "are we exposed
to anything already publicly known?" and :class:`~dast.adapters.zap_adapter.ZapAdapter`
answers "does *our own code* have injection/XSS/access-control flaws?", the
``SchemathesisAdapter`` answers a third question: **does our API honour its own
contract?** It reads the target's OpenAPI schema, generates thousands of valid and
deliberately malformed requests from it, and inspects the responses. Three kinds of
response are turned into security findings:

* an **undeclared 5xx** (Schemathesis's ``not_a_server_error`` check) — unvalidated
  input reached our code and usually leaked a stack trace → ``HIGH``;
* an operation that answers **without authentication** (``ignored_auth``) — broken
  access control → an access-control severity, carrying the observed status; and
* a response that **violates its own declared contract** (the schema-conformance
  checks) → a contract-violation severity, with a description enumerating every
  violated element.

Design notes (mirrors the nuclei pattern, **not** ZAP's REST sidecar):

* Schemathesis is a CLI that runs to completion per scan, so ``scan()`` is impure
  (drives the CLI as a subprocess — implemented in a later task) and
  :meth:`SchemathesisAdapter.parse` is a pure classmethod over Schemathesis's
  machine-readable report, unit-testable from a saved fixture with no network.
* One construction mode. ``mutating = True`` (it sends malformed/state-changing
  traffic), so the runner serialises it in the mutating tier — ahead of the active
  ZAP scan, whose site tree it seeds when proxied.
* Findings reuse the shared ``Finding`` model unchanged; the reproducing request
  (the single most valuable triage artefact) rides in ``Finding.raw``.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import socket
import time
from typing import Any, Iterable, Iterator, Mapping, Sequence
from urllib.parse import urlsplit

import yaml

from app.security.detection.adapters import base as sast_base
from app.security.detection.adapters.base import ScannerError
from app.security.models import Finding, Severity
from dast.adapters.base import make_web_location
from dast.config import DastSettings, dast_settings
from dast.models import DastScope, ScanOutcome, ToolActivity

# --------------------------------------------------------------------------- #
# Check names → finding kinds
# --------------------------------------------------------------------------- #
#: Schemathesis's undeclared-5xx check. A *failed* ``not_a_server_error`` check is by
#: definition an *undeclared* server error — a 5xx the schema declares for the
#: operation never fails this check — so no re-derivation of "declared vs undeclared"
#: is needed here (Req 5.1, 5.2).
_SERVER_ERROR_CHECK = "not_a_server_error"

#: Schemathesis's check for an operation that answered 2xx with auth omitted despite
#: declaring a security requirement (Req 6.1).
_IGNORED_AUTH_CHECK = "ignored_auth"

#: The four schema-conformance checks, in a fixed enumeration order so a response that
#: breaks several elements yields a *deterministic* description (Req 7.4).
_SCHEMA_CHECK_ORDER: tuple[str, ...] = (
    "status_code_conformance",
    "content_type_conformance",
    "response_headers_conformance",
    "response_schema_conformance",
)
_SCHEMA_CHECKS = frozenset(_SCHEMA_CHECK_ORDER)

#: Human-readable name of the contract element each conformance check guards.
_ELEMENT_LABELS: dict[str, str] = {
    "status_code_conformance": "status code",
    "content_type_conformance": "content type",
    "response_headers_conformance": "response headers",
    "response_schema_conformance": "response body",
}

#: Finding-kind identifiers used as the stable ``rule_id`` prefix (Req 5.4, 9.1).
_KIND_SERVER_ERROR = "server_error"
_KIND_IGNORED_AUTH = "ignored_auth"
_KIND_SCHEMA_VIOLATION = "schema_violation"

#: Severity per finding kind. Undeclared 5xx is HIGH (Req 5.3); broken access control
#: is treated as HIGH (Req 6.2); a contract violation is MEDIUM (Req 7.3).
_KIND_SEVERITY: dict[str, Severity] = {
    _KIND_SERVER_ERROR: Severity.HIGH,
    _KIND_IGNORED_AUTH: Severity.HIGH,
    _KIND_SCHEMA_VIOLATION: Severity.MEDIUM,
}

#: The same default category the other DAST adapters use.
DEFAULT_CATEGORY = "dast"

#: Values (case-insensitive) that mark a check result as failing. When a check dict
#: carries none of the recognised status fields we assume the report lists only
#: failures, so an un-annotated check counts as failed.
_FAILURE_VALUES = frozenset({"failure", "failed", "error"})

# --------------------------------------------------------------------------- #
# Run-statistics parsing (Req 11.1, 11.4)
# --------------------------------------------------------------------------- #
# The single most important trust rule: request evidence is read from Schemathesis's
# OWN run statistics — the count of requests that actually reached the target — and
# NEVER from the number of generated test cases. A run that generated 5,000 cases but
# resolved no DNS sent zero requests, and reporting that as "clean" is exactly the
# failure mode the whole service exists to avoid. So none of the keys below ever
# reference a "cases"/"examples"/"generated" count.

#: Keys under which Schemathesis's stats block may live in the machine-readable report.
_STATS_BLOCK_KEYS: tuple[str, ...] = (
    "statistics",
    "stats",
    "summary",
    "run_statistics",
    "network",
)
#: Keys carrying the count of requests that actually left the scanner and returned a
#: response (transport reached the target). Never a generated-case count.
_STATS_REQUEST_KEYS: tuple[str, ...] = (
    "requests_made",
    "requests",
    "total_requests",
    "request_count",
    "sent_requests",
    "sent",
)
#: Keys carrying the count of requests that failed at the transport level (DNS,
#: connection refused, TLS).
_STATS_ERROR_KEYS: tuple[str, ...] = (
    "request_errors",
    "network_errors",
    "errored",
    "errors",
    "error_count",
)
#: Keys carrying the count of requests that timed out.
_STATS_TIMEOUT_KEYS: tuple[str, ...] = (
    "timeouts",
    "timed_out",
    "timeout_count",
)

#: Fallback text patterns for reading the totals from Schemathesis's end-of-run
#: summary line when the report carries no machine-readable stats block. The LAST
#: match holds the final totals.
_TEXT_REQUESTS = re.compile(r'requests(?:_made)?["\s:=]+"?(\d+)', re.IGNORECASE)
_TEXT_ERRORS = re.compile(r'(?:request_errors|network errors?|errors?)["\s:=]+"?(\d+)', re.IGNORECASE)
#: Emitted per request that exceeded the per-request timeout.
_TIMEOUT_HINT = re.compile(r"timed out|timeout|deadline exceeded", re.IGNORECASE)


class SchemathesisAdapter:
    """Runs Schemathesis against a live target and returns shared ``Finding`` objects.

    A single construction mode; ``mutating`` is a fixed class attribute. ``scan()``
    (impure, drives the CLI) is implemented in a later task; :meth:`parse` (pure) is
    implemented here.
    """

    name = "schemathesis"
    #: Schemathesis sends deliberately malformed and state-changing requests, so it
    #: must be serialised — the runner places it in the mutating tier.
    mutating = True

    def __init__(
        self,
        *,
        settings: DastSettings = dast_settings,
        binary: str = "schemathesis",
    ) -> None:
        self._settings = settings
        self._binary = binary

    # ------------------------------------------------------------------ #
    # Impure: drive the tool (implemented in a later task)
    # ------------------------------------------------------------------ #
    def scan(self, scope: DastScope) -> ScanOutcome:
        """Drive one Schemathesis scan against ``scope`` and return findings + evidence.

        Orchestrates the fixed sequence from the design behind a narrow
        command-builder + runner seam, mirroring :meth:`NucleiAdapter.scan`:

        1. **argument-type guard** (Req 1.4) — a non-:class:`DastScope` argument
           raises immediately, before any work, and produces no ``ScanOutcome``;
        2. **production refusal** (Req 14.2, 14.3) — a ``target_url`` matching
           ``DAST_SCHEMATHESIS_PROD_URL_PATTERN`` sends nothing and raises
           :class:`ScannerError`;
        3. **seed resolution** (Req 4.1, 4.2, 4.4) — the ``fast`` profile reads a
           fixed integer seed (missing/non-integer → ``ScannerError``); ``deep``
           runs unseeded;
        4. **schema source** (Req 2.1, 2.2) — a configured file, else the URL from
           ``target_url`` + ``DAST_OPENAPI_PATH`` loaded within the schema timeout;
        5. **proxy reachability** (Req 3.2, 3.4) — when the ZAP proxy is configured,
           a TCP connect check proves it is up before any traffic is sent, so a
           configured-but-down proxy is a hard failure, never silent unproxied
           traffic;
        6. **build + run** (Req 2.3, 2.4, 3.1, 3.3, 13.1-13.3) — assemble the CLI
           arg vector and proxy environment and run it through the shared
           ``run_scanner`` with the hard ``DAST_SCHEMATHESIS_TIMEOUT``.

        Two channels signal an untrustworthy run, both already honoured by the
        runner (mirrors nuclei/ZAP):

        * **Hard failures** (not a ``DastScope``; production target; missing/invalid
          seed on fast; schema unavailable/invalid; proxy configured but unreachable;
          target unreachable; non-zero exit before any request completed) raise
          :class:`ScannerError`; :func:`dast.runner._run_one` records an
          ``incomplete`` coverage entry with the reason and keeps scanning.
        * **Soft evidence** (zero requests, all-errors, timeout flood) is returned in
          a truthful :class:`ToolActivity`; the existing ``_assess_activity``
          classifies it.

        ``requests_made``, ``request_errors``, and ``timeouts`` are read from
        Schemathesis's OWN run statistics (never the generated-case count, Req 11.4),
        and the hard-failure reason carries that same evidence so the coverage entry
        is diagnostic even on the failure path (Req 12.4).
        """
        # 1. Argument-type guard (Req 1.4) — raise before any work; no ScanOutcome,
        #    no request. The runner's catch-all records this as incomplete.
        if not isinstance(scope, DastScope):
            raise TypeError(
                f"SchemathesisAdapter.scan expects a DastScope, got "
                f"{type(scope).__name__}"
            )

        settings = self._settings

        # 2. Production refusal (Req 14.2, 14.3) — determined before any request.
        pattern = settings.DAST_SCHEMATHESIS_PROD_URL_PATTERN
        if pattern and re.search(pattern, scope.target_url):
            raise ScannerError(self.name, "refused: production target")

        # 3. Seed resolution (Req 4.1, 4.2, 4.4) — fast is seeded/reproducible, deep
        #    is unseeded/exploratory; a missing/invalid seed on fast is a hard failure.
        seed = self._resolve_seed(scope.profile)

        # 4. Schema source (Req 2.1, 2.2).
        schema_source, schema_is_file = self._schema_source(scope)

        # 5. Proxy reachability (Req 3.2, 3.4) — prove the proxy is up before sending
        #    anything; a configured-but-down proxy never falls back to unproxied
        #    traffic.
        proxy = self._proxy_target()
        if proxy is not None:
            self._check_proxy_reachable(proxy)
        proxy_url = f"http://{proxy[0]}:{proxy[1]}" if proxy is not None else None

        report = sast_base.new_temp_report(".yaml")
        started = time.monotonic()
        try:
            argv, env = self._build_command(
                scope,
                report,
                schema_source=schema_source,
                schema_is_file=schema_is_file,
                seed=seed,
                proxy_url=proxy_url,
            )

            # 6. Run the CLI through the shared runner with the hard timeout. The
            #    proxy env is exported for the child process as a belt-and-braces
            #    equivalent of --request-proxy (Req 3.1), so no generated request can
            #    bypass the proxy.
            result = self._run(argv, env)
            duration = time.monotonic() - started

            report_text = sast_base.read_report(report)
            report_data = _load_report(report_text)
            diagnostics = f"{result.stderr}\n{result.stdout}"

            # Request evidence from Schemathesis's OWN stats, never the case count.
            requests_made, request_errors, timeouts = _run_statistics(
                report_data, diagnostics
            )

            # Truthful activity — populated even on the failure path (Req 12.4).
            activity = ToolActivity(
                requests_made=requests_made,
                request_errors=request_errors or 0,
                timeouts=timeouts or 0,
                exit_code=result.returncode,
                duration_seconds=round(duration, 2),
            )

            # 7. Classify hard failures (Req 2.5, 12.1, 12.2). Schemathesis exits
            #    non-zero to signal "checks failed" (i.e. findings were produced), so
            #    a non-zero exit WITH requests made is a normal, successful run. Only
            #    a non-zero exit that never landed a single request is a hard failure:
            #    schema unavailable/invalid, target unreachable, or an early abort.
            if result.returncode != 0 and not requests_made:
                raise ScannerError(
                    self.name,
                    _hard_failure_reason(result, requests_made, request_errors),
                )

            findings = self.parse(
                report_data, spec_paths=scope.spec_paths, scanner_name=self.name
            )
            return ScanOutcome(findings=tuple(findings), activity=activity)
        finally:
            sast_base.cleanup(report)

    # ------------------------------------------------------------------ #
    # Impure helpers (the command-builder + runner seam)
    # ------------------------------------------------------------------ #
    def _build_command(
        self,
        scope: DastScope,
        report: str,
        *,
        schema_source: str,
        schema_is_file: bool,
        seed: int | None,
        proxy_url: str | None,
    ) -> tuple[list[str], dict[str, str]]:
        """Assemble the Schemathesis CLI arg vector and proxy environment.

        Kept a separate method so tests (task 4.3/4.11) can substitute the seam and
        assert over the exact argument vector and subprocess environment without
        spawning a process. Returns ``(argv, env)`` where ``env`` carries the proxy
        variables to export for the child process.

        The exact flag spellings are pinned to ``DAST_SCHEMATHESIS_VERSION`` and are
        exercised end-to-end by the integration tests; the design commitments they
        satisfy are: every generated request carries the auth header when configured
        (Req 2.4, 3.3) and routes through the proxy (Req 3.1), requests target only
        the configured base URL (Req 2.3), generation is seeded on fast and unseeded
        on deep (Req 4.1, 4.2), and the rate limit is clamped into range (Req 13.3).
        """
        settings = self._settings
        argv: list[str] = [
            self._binary,
            "run",
            schema_source,
            # Confine every generated request to the target (Req 2.3).
            "--base-url", scope.target_url,
            # Run all built-in checks: undeclared 5xx, ignored auth, schema
            # conformance — the three finding kinds parse() classifies.
            "--checks", "all",
            # Cap outgoing req/s so a single-worker target is not jammed into timing
            # out — a scan that looks clean because it never landed (Req 13.3).
            "--rate-limit", f"{self._rate_limit()}/s",
            # Per-request connect/response ceiling (milliseconds).
            "--request-timeout", str(settings.DAST_SCHEMATHESIS_CONNECT_TIMEOUT * 1000),
            # VCR cassette of every request/response + per-case checks. This is the
            # machine-readable per-interaction record Schemathesis actually emits;
            # scan() translates it into the case shape parse() consumes.
            "--cassette-path", report,
        ]

        # Bound schema loading when fetched from a URL (Req 2.2). A file schema is
        # local, so the wait-for-schema window does not apply.
        if not schema_is_file:
            argv += ["--wait-for-schema", str(settings.DAST_SCHEMATHESIS_SCHEMA_TIMEOUT)]

        # Auth header on EVERY generated request when set; anonymous otherwise —
        # never a blank header (Req 2.4, 3.3).
        if scope.auth_header:
            argv += ["--header", f"Authorization: {scope.auth_header}"]

        # Fixed seed on fast (reproducible); omitted on deep (exploratory) (Req 4.1,
        # 4.2).
        if seed is not None:
            argv += ["--hypothesis-seed", str(seed)]

        env: dict[str, str] = {}
        if proxy_url:
            # Both the explicit flag and the environment, so NO generated request can
            # bypass the proxy (Req 3.1).
            argv += ["--request-proxy", proxy_url]
            env["HTTP_PROXY"] = proxy_url
            env["HTTPS_PROXY"] = proxy_url

        return argv, env

    def _run(self, argv: Sequence[str], env: Mapping[str, str]):
        """Run the arg vector through the shared runner with the proxy env applied.

        ``run_scanner`` inherits the process environment, so the proxy variables are
        exported around the call (and restored after) rather than passed through a
        parameter it does not accept. Isolated here so the seam is a single, easily
        faked method.
        """
        with _augmented_environ(env):
            return sast_base.run_scanner(
                list(argv),
                scanner_name=self.name,
                timeout=self._settings.DAST_SCHEMATHESIS_TIMEOUT,
            )

    def _resolve_seed(self, profile: str) -> int | None:
        """Resolve the generation seed for ``profile`` (Req 4.1, 4.2, 4.4).

        ``deep`` runs unseeded (returns ``None``). ``fast`` (the default, and any
        non-``deep`` profile) requires a valid integer seed; a missing or
        non-integer seed is a hard failure — refusing a non-reproducible fast run is
        safer than silently running one whose findings cannot be re-confirmed.
        """
        if profile == "deep":
            return None
        raw = self._settings.DAST_SCHEMATHESIS_SEED
        if raw is None or isinstance(raw, bool):
            raise ScannerError(
                self.name, "seed unavailable — refusing non-reproducible fast run"
            )
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise ScannerError(
                self.name, "seed unavailable — refusing non-reproducible fast run"
            ) from None

    def _schema_source(self, scope: DastScope) -> tuple[str, bool]:
        """Resolve the OpenAPI schema source (Req 2.1, 2.2).

        Returns ``(source, is_file)``: the configured file when
        ``DAST_SCHEMATHESIS_SCHEMA_FILE`` is set, otherwise the URL derived from the
        target and ``DAST_OPENAPI_PATH``.
        """
        schema_file = self._settings.DAST_SCHEMATHESIS_SCHEMA_FILE
        if schema_file and str(schema_file).strip():
            return str(schema_file).strip(), True
        url = scope.target_url.rstrip("/") + self._settings.DAST_OPENAPI_PATH
        return url, False

    def _rate_limit(self) -> int:
        """Clamp the configured rate limit into 1-1000, defaulting to 10 (Req 13.1-13.3).

        A value inside the range is used as-is; an absent or out-of-range value falls
        back to the safe default of 10 req/s rather than firing at an unbounded rate.
        """
        try:
            value = int(self._settings.DAST_SCHEMATHESIS_RATE_LIMIT)
        except (TypeError, ValueError):
            return 10
        if 1 <= value <= 1000:
            return value
        return 10

    def _proxy_target(self) -> tuple[str, int] | None:
        """The ZAP proxy ``(host, port)`` when configured, else ``None`` (Req 3.2).

        The proxy is configured only when both ``DAST_ZAP_HOST`` and
        ``DAST_ZAP_PORT`` are present and non-empty; when either is absent/empty (or
        the port is zero/unparseable) the proxy is treated as not configured and
        Schemathesis talks to the target directly.
        """
        host = self._settings.DAST_ZAP_HOST
        port = self._settings.DAST_ZAP_PORT
        if host is None or not str(host).strip():
            return None
        port_str = str(port).strip()
        if not port_str or port_str == "0":
            return None
        try:
            port_int = int(port_str)
        except (TypeError, ValueError):
            return None
        if port_int <= 0:
            return None
        return str(host).strip(), port_int

    def _check_proxy_reachable(self, proxy: tuple[str, int]) -> None:
        """TCP-connect to the proxy within the connect timeout, or raise (Req 3.4).

        A configured-but-unreachable proxy is a hard failure: sending unproxied
        traffic instead would silently defeat the whole point of routing through ZAP.
        """
        host, port = proxy
        timeout = self._settings.DAST_SCHEMATHESIS_PROXY_CONNECT_TIMEOUT
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return
        except OSError as exc:
            raise ScannerError(
                self.name,
                f"ZAP proxy unreachable at {host}:{port} within {timeout}s: {exc}",
            ) from exc

    # ------------------------------------------------------------------ #
    # Pure: parse the payload
    # ------------------------------------------------------------------ #
    @classmethod
    def parse(
        cls,
        report: Any,
        *,
        spec_paths: Iterable[str] = (),
        scanner_name: str = "schemathesis",
    ) -> list[Finding]:
        """Convert a decoded Schemathesis report into shared ``Finding`` objects.

        Pure and deterministic — performs no network or filesystem I/O, and returns
        equal results on repeated calls with equal arguments (Req 1.5). Mirrors
        :meth:`NucleiAdapter.parse`.

        Each failing *case* (one generated request + its response + the checks that
        ran against it) yields up to three findings — one per finding kind present:

        * a failed ``not_a_server_error`` → one high-severity server-error finding;
        * a failed ``ignored_auth`` → one access-control finding carrying the status;
        * one or more failed schema-conformance checks → a **single** contract
          finding whose message enumerates every violated element (Req 7.4).

        The reproducing request and observed response are recorded under
        ``Finding.raw`` (Req 8.1-8.5).
        """
        spec = tuple(spec_paths)
        findings: list[Finding] = []

        for case in _iter_cases(report):
            failed = _failed_checks(case)
            if not failed:
                continue

            request = _request_info(case)
            method = _case_method(case, request)
            url = _case_url(case, request)
            status = _response_status(case)
            response = case.get("response")
            location = make_web_location(url, method=method, spec_paths=spec)
            repro = _reproducing_request(request)
            response_raw = dict(response) if isinstance(response, Mapping) else {}

            # 1. Undeclared server error -> HIGH.
            if _SERVER_ERROR_CHECK in failed:
                findings.append(
                    _build_finding(
                        scanner_name=scanner_name,
                        kind=_KIND_SERVER_ERROR,
                        location=location,
                        status=status,
                        message=(
                            f"Unhandled server error ({status}) on {location.path}"
                        ),
                        check_names=[_SERVER_ERROR_CHECK],
                        repro=repro,
                        response=response_raw,
                    )
                )

            # 2. Unauthenticated access -> access-control severity + observed status.
            if _IGNORED_AUTH_CHECK in failed:
                findings.append(
                    _build_finding(
                        scanner_name=scanner_name,
                        kind=_KIND_IGNORED_AUTH,
                        location=location,
                        status=status,
                        message=(
                            f"Operation answered {status} without authentication "
                            f"on {location.path}"
                        ),
                        check_names=[_IGNORED_AUTH_CHECK],
                        repro=repro,
                        response=response_raw,
                    )
                )

            # 3. Schema conformance -> ONE finding enumerating every violated element.
            violated = [name for name in _SCHEMA_CHECK_ORDER if name in failed]
            if violated:
                elements = ", ".join(_ELEMENT_LABELS[name] for name in violated)
                findings.append(
                    _build_finding(
                        scanner_name=scanner_name,
                        kind=_KIND_SCHEMA_VIOLATION,
                        location=location,
                        status=status,
                        message=(
                            f"Response violates the declared contract on "
                            f"{location.path}: {elements}"
                        ),
                        check_names=violated,
                        repro=repro,
                        response=response_raw,
                    )
                )

        return findings


# --------------------------------------------------------------------------- #
# Helpers for scan() (impure orchestration support)
# --------------------------------------------------------------------------- #
@contextlib.contextmanager
def _augmented_environ(overrides: Mapping[str, str]) -> Iterator[None]:
    """Temporarily add ``overrides`` to ``os.environ``, restoring on exit.

    ``run_scanner`` inherits the process environment, so proxy variables are
    exported around the subprocess call and reverted afterwards — the child sees
    them, the parent process is left unchanged.
    """
    if not overrides:
        yield
        return
    saved: dict[str, str | None] = {key: os.environ.get(key) for key in overrides}
    try:
        os.environ.update(overrides)
        yield
    finally:
        for key, previous in saved.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous


def _decode_report(text: str) -> Any:
    """Decode the machine-readable report file, tolerating an absent/empty report.

    A hard failure (schema unavailable, target unreachable) can leave the report
    empty or unwritten; returning ``None`` lets :meth:`SchemathesisAdapter.parse`
    yield no findings while the caller classifies the run from the exit code and
    run statistics instead.
    """
    stripped = (text or "").strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def _load_report(text: str) -> Any:
    """Load the report file, accepting either a VCR cassette or a plain report.

    The pinned Schemathesis CLI emits a **VCR cassette** (YAML) via
    ``--cassette-path`` — a list of ``http_interactions``, each carrying the
    ``request``, ``response`` and the per-case ``checks``. When the file is a
    cassette it is translated into the flat ``{"cases": [...]}`` shape
    :meth:`SchemathesisAdapter.parse` consumes. Any other JSON/YAML mapping is
    returned unchanged, so a report already in parse()'s shape (e.g. a test fixture)
    passes straight through and an absent/empty file yields ``None``.
    """
    stripped = (text or "").strip()
    if not stripped:
        return None
    data: Any = None
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        try:
            data = yaml.safe_load(stripped)
        except yaml.YAMLError:
            return None
    if isinstance(data, Mapping) and "http_interactions" in data:
        return _cassette_to_report(data)
    return data


def _cassette_to_report(cassette: Mapping[str, Any]) -> dict[str, Any]:
    """Translate a Schemathesis VCR cassette into a parse()-shaped report.

    Each ``http_interaction`` becomes a *case* carrying its ``request``, a
    ``response`` with a flat ``status_code`` (the cassette nests it as
    ``response.status.code``), and its ``checks`` list. A synthetic ``statistics``
    block is attached so :func:`_run_statistics` reads request evidence from the
    number of interactions actually recorded (never a generated-case count): an
    interaction that reached the target has a response; one without is a transport
    error.
    """
    interactions = cassette.get("http_interactions") or []
    cases: list[dict[str, Any]] = []
    errors = 0
    for interaction in interactions:
        if not isinstance(interaction, Mapping):
            continue
        response = interaction.get("response")
        status_code: Any = None
        if isinstance(response, Mapping):
            status = response.get("status")
            if isinstance(status, Mapping):
                status_code = status.get("code")
            else:
                status_code = response.get("status_code", status)
        else:
            errors += 1
        cases.append(
            {
                "request": interaction.get("request"),
                "response": {"status_code": status_code},
                "checks": interaction.get("checks"),
            }
        )
    return {
        "cases": cases,
        "statistics": {
            "requests_made": len(cases),
            "request_errors": errors,
        },
    }


def _run_statistics(report: Any, diagnostics: str) -> tuple[int | None, int | None, int | None]:
    """Read ``(requests_made, request_errors, timeouts)`` from Schemathesis's stats.

    Reads from Schemathesis's OWN run statistics — requests that actually reached
    the target — and NEVER from the generated-case count (Req 11.4). Prefers the
    machine-readable stats block in the report; falls back to the end-of-run summary
    text only when the report carries no stats. ``requests_made`` is left ``None``
    when no honest count is available so ``_assess_activity`` treats a finding-less
    run as unverified rather than clean.
    """
    stats = _locate_stats(report)
    requests_made = _stat_int(stats, _STATS_REQUEST_KEYS)
    request_errors = _stat_int(stats, _STATS_ERROR_KEYS)
    timeouts = _stat_int(stats, _STATS_TIMEOUT_KEYS)

    if requests_made is None:
        requests_made = _extract_last_int(_TEXT_REQUESTS, diagnostics)
    if request_errors is None:
        request_errors = _extract_last_int(_TEXT_ERRORS, diagnostics)
    if timeouts is None:
        hits = len(_TIMEOUT_HINT.findall(diagnostics or ""))
        timeouts = hits or None

    return requests_made, request_errors, timeouts


def _locate_stats(report: Any) -> Mapping[str, Any]:
    """Find the statistics mapping within a decoded report, or an empty mapping.

    Accepts a dedicated stats block under any of :data:`_STATS_BLOCK_KEYS`, or the
    report top-level itself when it carries the recognised count keys directly.
    """
    if not isinstance(report, Mapping):
        return {}
    for key in _STATS_BLOCK_KEYS:
        block = report.get(key)
        if isinstance(block, Mapping):
            return block
    recognised = _STATS_REQUEST_KEYS + _STATS_ERROR_KEYS + _STATS_TIMEOUT_KEYS
    if any(key in report for key in recognised):
        return report
    return {}


def _stat_int(stats: Mapping[str, Any], keys: Sequence[str]) -> int | None:
    """Return the first of ``keys`` present in ``stats`` coerced to a non-negative int."""
    for key in keys:
        if key in stats:
            raw = stats[key]
            try:
                value = int(raw)
            except (TypeError, ValueError):
                continue
            if value >= 0:
                return value
    return None


def _extract_last_int(pattern: re.Pattern[str], text: str) -> int | None:
    """Pull the LAST integer matched by ``pattern`` from ``text`` (final totals)."""
    matches = pattern.findall(text or "")
    if not matches:
        return None
    try:
        return int(matches[-1])
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


def _hard_failure_reason(
    result: Any, requests_made: int | None, request_errors: int | None
) -> str:
    """Build a diagnostic reason for a non-zero exit that never reached the target.

    Carries the failure-path evidence (exit code, requests made, request errors) so
    the ``incomplete`` coverage entry is diagnostic even though the scan aborted
    before landing a request (Req 12.4).
    """
    detail = (getattr(result, "stderr", "") or "").strip()[:500]
    exit_code = getattr(result, "returncode", None)
    evidence = f"requests_made={requests_made or 0}, request_errors={request_errors or 0}"
    reason = (
        f"exited {exit_code} before any request reached the target "
        f"({evidence}) — schema unavailable/invalid or target unreachable"
    )
    if detail:
        reason = f"{reason}: {detail}"
    return reason


# --------------------------------------------------------------------------- #
# Helpers (pure)
# --------------------------------------------------------------------------- #
def _build_finding(
    *,
    scanner_name: str,
    kind: str,
    location: Any,
    status: str,
    message: str,
    check_names: Sequence[str],
    repro: dict[str, Any],
    response: dict[str, Any],
) -> Finding:
    """Assemble one ``Finding``, keeping ``rule_id`` and ``raw`` shape consistent.

    ``rule_id`` is ``{kind}:{METHOD path}:{status}`` (e.g.
    ``server_error:GET /api/users/{id}:500``). Because ``location.path`` is the
    method-prefixed *templatised* path (host- and id-independent), the id is stable
    across runs that reach the same endpoint with differing segment values (Req 5.4,
    9.1, 9.2).
    """
    return Finding(
        scanner=scanner_name,
        rule_id=f"{kind}:{location.path}:{status}",
        location=location,
        severity=_KIND_SEVERITY[kind],
        message=message,
        raw={
            "reproducing_request": repro,
            "response": response,
            "checks": list(check_names),
        },
        category=DEFAULT_CATEGORY,
    )


def _iter_cases(report: Any) -> list[Mapping[str, Any]]:
    """Normalise a Schemathesis report into a flat list of *case* mappings.

    A *case* carries a ``request``, a ``response``, and the ``checks`` that ran
    against it. Reports are accepted in a few shapes so the parser is robust to the
    exact serialisation pinned by the CLI-driving task:

    * ``{"results": [ {method, path, cases: [case, ...]}, ... ]}`` — grouped per
      operation, each operation holding several generated cases;
    * ``{"results": [ case, ... ]}`` — each result *is* a case (carries ``checks``);
    * ``{"cases": [case, ...]}`` or a bare ``[case, ...]`` list.

    Operation-level ``method``/``path`` are pushed down onto each case as fallbacks
    so a case that omits them can still be located.
    """
    if isinstance(report, Mapping):
        results = report.get("results")
        if isinstance(results, Sequence) and not isinstance(results, (str, bytes)):
            cases: list[Mapping[str, Any]] = []
            for result in results:
                if not isinstance(result, Mapping):
                    continue
                op_method = result.get("method")
                op_path = result.get("path") or result.get("verbose_name")
                nested = result.get("cases")
                if isinstance(nested, Sequence) and not isinstance(
                    nested, (str, bytes)
                ):
                    for case in nested:
                        if isinstance(case, Mapping):
                            cases.append(_with_operation(case, op_method, op_path))
                else:
                    cases.append(_with_operation(result, op_method, op_path))
            return cases

        nested = report.get("cases")
        if isinstance(nested, Sequence) and not isinstance(nested, (str, bytes)):
            return [case for case in nested if isinstance(case, Mapping)]
        # A single bare case.
        return [report]

    if isinstance(report, Sequence) and not isinstance(report, (str, bytes)):
        return [case for case in report if isinstance(case, Mapping)]

    return []


def _with_operation(
    case: Mapping[str, Any], method: Any, path: Any
) -> Mapping[str, Any]:
    """Return ``case`` with operation-level ``method``/``path`` filled in as fallbacks."""
    if case.get("method") and case.get("path"):
        return case
    merged = dict(case)
    merged.setdefault("method", method)
    merged.setdefault("path", path)
    return merged


def _failed_checks(case: Mapping[str, Any]) -> set[str]:
    """Return the set of check names that failed for ``case``.

    A check dict counts as failed when its status/value/outcome field is one of
    ``failure``/``failed``/``error`` — or, when it carries no such field, on the
    assumption that the report lists only failing checks. Reports that expose
    failures as a flat list of names (``"failures": ["not_a_server_error"]``) are
    also honoured.
    """
    failed: set[str] = set()

    checks = case.get("checks")
    if isinstance(checks, Sequence) and not isinstance(checks, (str, bytes)):
        for check in checks:
            if not isinstance(check, Mapping):
                continue
            name = check.get("name")
            if name and _is_failed_check(check):
                failed.add(str(name))

    for key in ("failures", "failed_checks"):
        names = case.get(key)
        if isinstance(names, Sequence) and not isinstance(names, (str, bytes)):
            failed.update(str(name) for name in names if name)

    return failed


def _is_failed_check(check: Mapping[str, Any]) -> bool:
    """True when a check-result mapping indicates a failure (or is un-annotated)."""
    for key in ("status", "value", "outcome", "result"):
        raw = check.get(key)
        if raw is not None:
            return str(raw).strip().lower() in _FAILURE_VALUES
    # No status annotation -> the report is a list of failures.
    return True


def _request_info(case: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """The reproducing request mapping for a case, or ``None`` when uncapturable."""
    request = case.get("request")
    if isinstance(request, Mapping) and request:
        return request
    return None


def _case_method(case: Mapping[str, Any], request: Mapping[str, Any] | None) -> str | None:
    """HTTP method for the case, preferring the captured request."""
    method = (request or {}).get("method") or case.get("method")
    return str(method) if method else None


def _case_url(case: Mapping[str, Any], request: Mapping[str, Any] | None) -> str:
    """A URL (or bare path) for the case, used to derive the endpoint identity."""
    if request:
        candidate = (
            request.get("uri")
            or request.get("url")
            or request.get("path")
            or case.get("path")
        )
    else:
        candidate = case.get("path")
    return str(candidate or "")


def _response_status(case: Mapping[str, Any]) -> str:
    """The observed response status code as a string, or ``"unknown"``."""
    response = case.get("response")
    if isinstance(response, Mapping):
        status = response.get("status_code", response.get("status"))
        if status is not None:
            return str(status)
    return "unknown"


def _reproducing_request(request: Mapping[str, Any] | None) -> dict[str, Any]:
    """Build the ``reproducing_request`` block carried in ``Finding.raw``.

    Records the method, the path *including* query string, every header sent (the
    auth header among them when present), and the body — with an explicit empty
    value when the request carried no body (Req 8.2-8.4). When no request could be
    captured, an explicit ``{"unavailable": True}`` marker is returned instead of a
    request with missing detail (Req 8.5).
    """
    if not request:
        return {"unavailable": True}

    body = request.get("body")
    headers = request.get("headers")
    return {
        "method": str(request.get("method") or "").upper(),
        "path": _path_with_query(request),
        "headers": dict(headers) if isinstance(headers, Mapping) else {},
        # Explicit empty value when absent, never omitted (Req 8.3).
        "body": "" if body is None else body,
    }


def _path_with_query(request: Mapping[str, Any]) -> str:
    """Extract the request path including any query string (Req 8.2)."""
    uri = request.get("uri") or request.get("url")
    if uri:
        parts = urlsplit(str(uri))
        path = parts.path or "/"
        if parts.query:
            path = f"{path}?{parts.query}"
        return path
    return str(request.get("path") or "")
