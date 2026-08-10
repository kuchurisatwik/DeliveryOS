"""Preflight — three assertions that must hold before any tool runs.

SAST never needed this: a git checkout is either there or it isn't. A DAST scan
can fail in ways that still look successful, and all three of these produce a
green, empty, entirely meaningless report if we skip them:

1. **Is the target up?** A scan launched while the app is still booting connects to
   nothing and finds nothing.
2. **Is it the build we meant to scan?** When deploys and scans are decoupled,
   scanning yesterday's build while reading today's diff costs a day of confusion.
3. **Does authentication work?** An unauthenticated scanner tests the login page
   and reports that the login page is fine.

Preflight also fetches the OpenAPI spec, which later stages use both to seed
scanners and to templatise URLs into stable endpoint identities.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import httpx

from app.utils.logger import logger
from dast.config import dast_settings


class PreflightError(RuntimeError):
    """Raised when the target is not in a state worth scanning."""


@dataclass(frozen=True)
class PreflightResult:
    """What preflight established about the target."""

    reachable: bool
    waited_seconds: float
    reported_sha: str | None = None
    sha_matched: bool | None = None
    auth_verified: bool | None = None
    #: Path templates from the target's OpenAPI spec, e.g. ``/api/users/{user_id}``.
    spec_paths: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "reachable": self.reachable,
            "waited_seconds": round(self.waited_seconds, 2),
            "reported_sha": self.reported_sha,
            "sha_matched": self.sha_matched,
            "auth_verified": self.auth_verified,
            "spec_endpoint_count": len(self.spec_paths),
        }


def run_preflight(
    target_url: str,
    *,
    commit_sha: str = "",
    auth_header: str | None = None,
    poll_interval: float = 2.0,
) -> PreflightResult:
    """Verify the target is up, is the right build, and accepts our credentials.

    Raises:
        PreflightError: when the target never becomes reachable, is running a
            different commit than requested (and a match is required), or rejects
            the configured credentials.
    """
    base = target_url.rstrip("/") + "/"
    health_url = urljoin(base, dast_settings.DAST_HEALTH_PATH.lstrip("/"))
    deadline = time.monotonic() + dast_settings.DAST_HEALTH_TIMEOUT
    started = time.monotonic()

    payload = _wait_for_health(health_url, deadline, poll_interval)
    waited = time.monotonic() - started
    logger.info("Preflight: target reachable after %.1fs (%s)", waited, health_url)

    reported_sha = _reported_sha(payload)
    sha_matched: bool | None = None
    if commit_sha and reported_sha:
        sha_matched = reported_sha.startswith(commit_sha[:7]) or commit_sha.startswith(
            reported_sha[:7]
        )
        if not sha_matched and dast_settings.DAST_REQUIRE_SHA_MATCH:
            raise PreflightError(
                f"target is running commit '{reported_sha}' but the scan was "
                f"requested for '{commit_sha}'"
            )
        if not sha_matched:
            logger.warning(
                "Preflight: target reports commit '%s', scan requested '%s' — "
                "scanning anyway (DAST_REQUIRE_SHA_MATCH is off)",
                reported_sha,
                commit_sha,
            )

    auth_verified = _verify_auth(health_url, auth_header)
    spec_paths = _fetch_spec_paths(base, auth_header)

    return PreflightResult(
        reachable=True,
        waited_seconds=waited,
        reported_sha=reported_sha,
        sha_matched=sha_matched,
        auth_verified=auth_verified,
        spec_paths=spec_paths,
    )


def _wait_for_health(url: str, deadline: float, poll_interval: float) -> dict[str, Any]:
    """Poll the health endpoint until it answers, or give up at ``deadline``."""
    last_error = "no attempt made"
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=10.0, follow_redirects=True)
            if response.status_code < 500:
                try:
                    return response.json() if response.content else {}
                except ValueError:
                    return {}
            last_error = f"HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        time.sleep(poll_interval)
    raise PreflightError(
        f"target never became reachable at {url} within "
        f"{dast_settings.DAST_HEALTH_TIMEOUT}s (last error: {last_error})"
    )


def _reported_sha(payload: dict[str, Any]) -> str | None:
    """Read the deployed commit SHA out of the health payload, if it exposes one."""
    value = payload.get(dast_settings.DAST_SHA_FIELD)
    return str(value) if value else None


def _verify_auth(health_url: str, auth_header: str | None) -> bool | None:
    """Confirm the configured credentials are accepted.

    Returns ``None`` when no credentials are configured (nothing to verify). A
    ``401``/``403`` means the token is missing, malformed, or expired — worth
    failing on, because every subsequent tool would silently scan as an anonymous
    user and report a suspiciously clean application.
    """
    if not auth_header:
        return None
    try:
        response = httpx.get(
            health_url,
            headers={"Authorization": auth_header},
            timeout=10.0,
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        raise PreflightError(f"could not verify credentials: {exc}") from exc
    if response.status_code in (401, 403):
        raise PreflightError(
            f"target rejected the configured credentials (HTTP {response.status_code}); "
            "scanning would only test the unauthenticated surface"
        )
    return True


def _fetch_spec_paths(base_url: str, auth_header: str | None) -> tuple[str, ...]:
    """Fetch the OpenAPI spec and return its path templates.

    Best-effort: a target without a spec is still scannable, we just fall back to
    heuristics when templatising URLs.
    """
    url = urljoin(base_url, dast_settings.DAST_OPENAPI_PATH.lstrip("/"))
    headers = {"Authorization": auth_header} if auth_header else {}
    try:
        response = httpx.get(url, headers=headers, timeout=15.0, follow_redirects=True)
        if response.status_code != 200:
            logger.warning(
                "Preflight: no OpenAPI spec at %s (HTTP %s); URL templatising will "
                "fall back to heuristics",
                url,
                response.status_code,
            )
            return ()
        paths = (response.json() or {}).get("paths") or {}
        spec_paths = tuple(str(p) for p in paths)
        logger.info("Preflight: loaded %d endpoint(s) from the OpenAPI spec", len(spec_paths))
        return spec_paths
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Preflight: could not read the OpenAPI spec at %s: %s", url, exc)
        return ()
