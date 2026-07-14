"""SonarQube adapter — the impure shell for Quality Gate metrics (Req 12.1).

This module isolates the only side-effecting part of the Quality Gate: fetching
project metrics from a SonarQube / SonarCloud instance over HTTP. Keeping the
network call here means :func:`app.security.governance.quality_gate.evaluate_quality_gate`
stays a pure, deterministic function of ``(metrics, findings, thresholds)``.

:class:`HttpSonarClient` implements the injectable
:class:`app.security.protocols.SonarClient` protocol. It reuses the project's
existing HTTP conventions — ``httpx`` (already a dependency, as used by
``app/services/llm_service.py``) with a bounded timeout and ``raise_for_status``
— and the project token from ``app.config.settings``.

The SonarQube ``api/measures/component`` endpoint returns the metrics that back
the gate. This adapter requests exactly the five metric families the design
enumerates (maintainability, code smells, technical debt, security hotspots,
coverage) and maps them into an immutable :class:`~app.security.models.SonarMetrics`.
"""

from __future__ import annotations

import httpx

from app.config.settings import settings
from app.security.models import SonarMetrics
from app.utils.logger import logger

# SonarQube metric keys requested from ``api/measures/component``.
# https://docs.sonarsource.com/ — ``sqale_index`` is the technical-debt measure
# (in minutes); ``sqale_rating`` is the maintainability rating (1..5 → A..E).
_METRIC_KEYS = (
    "coverage",
    "code_smells",
    "sqale_index",
    "security_hotspots",
    "sqale_rating",
)

_MEASURES_PATH = "/api/measures/component"

# SonarQube encodes maintainability as a numeric rating 1.0..5.0 (A..E).
_RATING_NUMBER_TO_LETTER = {1: "A", 2: "B", 3: "C", 4: "D", 5: "E"}


def _rating_to_letter(raw: str) -> str:
    """Convert a Sonar ``sqale_rating`` (e.g. ``"1.0"``) to a letter grade."""
    try:
        return _RATING_NUMBER_TO_LETTER.get(int(float(raw)), raw)
    except (TypeError, ValueError):
        return raw


class HttpSonarClient:
    """Fetches SonarQube metrics into :class:`SonarMetrics` over HTTP (Req 12.1).

    Implements :class:`app.security.protocols.SonarClient`. The SonarQube token is
    supplied as the HTTP Basic auth *username* with an empty password, which is
    SonarQube's documented token-authentication scheme.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        project_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or settings.SONARQUBE_URL).rstrip("/")
        self.token = token or settings.SONARQUBE_TOKEN
        self.project_key = project_key or settings.SONARQUBE_PROJECT_KEY
        self.timeout = timeout

    def fetch_metrics(self, commit_sha: str) -> SonarMetrics:
        """Fetch and map SonarQube metrics for ``commit_sha`` into ``SonarMetrics``.

        Raises :class:`ValueError` when the SonarQube configuration is missing or
        the API call fails, mirroring the fail-loud behaviour of the existing
        HTTP services in the project.
        """
        if not self.project_key:
            raise ValueError("SONARQUBE_PROJECT_KEY is not configured")

        params = {
            "component": self.project_key,
            "metricKeys": ",".join(_METRIC_KEYS),
        }
        # ``pullRequest`` / analysis association is keyed by the triggering commit
        # where the CI has published the analysis under that identifier.
        if commit_sha:
            params["pullRequest"] = commit_sha

        # Token auth: token as username, empty password (SonarQube convention).
        auth = httpx.BasicAuth(self.token, "") if self.token else None

        logger.info(
            "Fetching SonarQube metrics for project '%s' (commit %s)",
            self.project_key,
            commit_sha,
        )
        try:
            with httpx.Client(timeout=self.timeout, auth=auth) as client:
                response = client.get(f"{self.base_url}{_MEASURES_PATH}", params=params)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # noqa: BLE001 - surface a clear adapter error
            logger.error("SonarQube metrics fetch failed: %s", exc)
            raise ValueError(f"SonarQube metrics fetch failed: {exc}") from exc

        return self._map_measures(data)

    @staticmethod
    def _map_measures(data: dict) -> SonarMetrics:
        """Map a SonarQube ``measures/component`` payload into ``SonarMetrics``."""
        measures = {
            m.get("metric"): m.get("value")
            for m in data.get("component", {}).get("measures", [])
        }

        def _num(key: str, default: float = 0.0) -> float:
            try:
                return float(measures.get(key, default))
            except (TypeError, ValueError):
                return default

        return SonarMetrics(
            coverage_percent=_num("coverage"),
            code_smells=int(_num("code_smells")),
            technical_debt_minutes=int(_num("sqale_index")),
            security_hotspots=int(_num("security_hotspots")),
            maintainability_rating=_rating_to_letter(measures.get("sqale_rating", "")),
        )
