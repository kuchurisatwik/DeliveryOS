"""Integration tests for Layer 4 governance: SonarQube fetch + GitHub reporting.

Deterministic example/integration tests (NOT property-based). They exercise the
two impure Layer 4 boundaries with mocks so no real network or GitHub API is hit:

* **SonarQube metrics fetch (Requirement 12.1)** — the ``httpx`` client used by
  :class:`~app.security.governance.sonar_client.HttpSonarClient` is monkeypatched
  to return a canned ``api/measures/component`` payload. The test asserts the
  payload maps into an immutable :class:`~app.security.models.SonarMetrics`
  correctly: ``coverage`` → ``coverage_percent``, ``code_smells``,
  ``sqale_index`` → ``technical_debt_minutes``, ``security_hotspots``, and
  ``sqale_rating`` (numeric 1..5) → a maintainability letter grade (A..E).

* **GitHub reporting (Requirement 14.1)** — :class:`GitHubService` is replaced by
  a mock (built with ``spec=GitHubService``) and driven through the real
  :class:`~app.workflows.stages.CreatePullRequestStage`. The test asserts the PR
  is opened for the run's ``Commit_SHA`` (the short SHA appears in the PR title),
  ``pr_url`` is recorded on the context, and — crucially — **no merge call is ever
  made** (reinforces design Property 20: no automatic merge). Because the service
  mock is spec'd to the real class, no merge method exists to call, and we further
  assert nothing resembling a merge was invoked.

Requirements: 12.1, 14.1
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.security.governance import sonar_client as sonar_client_module
from app.security.governance.sonar_client import HttpSonarClient
from app.security.models import SonarMetrics
from app.services.github_service import GitHubService
from app.workflows.context import WorkflowContext
from app.workflows.stages import CreatePullRequestStage


# --------------------------------------------------------------------------- #
# SonarQube metrics fetch (Requirement 12.1) — mocked httpx client.
# --------------------------------------------------------------------------- #

# A representative SonarQube ``api/measures/component`` payload. The five metric
# families the adapter requests are present; ``sqale_rating`` is Sonar's numeric
# maintainability rating ("1.0" == grade A).
SONAR_MEASURES_PAYLOAD = {
    "component": {
        "key": "my-project",
        "measures": [
            {"metric": "coverage", "value": "93.5"},
            {"metric": "code_smells", "value": "7"},
            {"metric": "sqale_index", "value": "120"},
            {"metric": "security_hotspots", "value": "2"},
            {"metric": "sqale_rating", "value": "1.0"},
        ],
    }
}


class _FakeResponse:
    """Minimal stand-in for an ``httpx.Response`` (only what the adapter uses)."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.raise_for_status_called = False

    def raise_for_status(self) -> None:
        self.raise_for_status_called = True

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    """Context-manager fake for ``httpx.Client`` that records the GET it received.

    Records the constructor kwargs (timeout/auth) and the ``get`` call so the test
    can assert the adapter queried the SonarQube measures endpoint. Returns a
    canned :class:`_FakeResponse` regardless of URL.
    """

    last_instance: "_FakeClient | None" = None

    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.init_kwargs: dict | None = None
        self.get_url: str | None = None
        self.get_params: dict | None = None
        type(self).last_instance = self

    def __call__(self, *args, **kwargs) -> "_FakeClient":
        # ``httpx.Client(...)`` — capture how the adapter constructed the client.
        self.init_kwargs = kwargs
        return self

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def get(self, url: str, params: dict | None = None) -> _FakeResponse:
        self.get_url = url
        self.get_params = params
        return _FakeResponse(self._payload)


def test_fetch_metrics_maps_sonar_payload_into_sonar_metrics(monkeypatch):
    """Req 12.1: a canned measures payload maps cleanly into ``SonarMetrics``."""
    fake_client = _FakeClient(SONAR_MEASURES_PAYLOAD)
    # Replace ``httpx.Client`` as referenced inside the adapter module.
    monkeypatch.setattr(sonar_client_module.httpx, "Client", fake_client)

    client = HttpSonarClient(
        base_url="https://sonar.example.com",
        token="tok-123",
        project_key="my-project",
    )

    metrics = client.fetch_metrics("abc1234")

    assert isinstance(metrics, SonarMetrics)
    # Metric mapping (12.1).
    assert metrics.coverage_percent == 93.5
    assert metrics.code_smells == 7
    assert metrics.technical_debt_minutes == 120  # sqale_index (minutes)
    assert metrics.security_hotspots == 2
    assert metrics.maintainability_rating == "A"  # sqale_rating 1.0 -> A

    # The adapter actually queried the SonarQube measures endpoint for the project.
    assert fake_client.get_url == "https://sonar.example.com/api/measures/component"
    assert fake_client.get_params["component"] == "my-project"
    assert fake_client.get_params["pullRequest"] == "abc1234"
    # Requested exactly the five metric families the gate consumes.
    requested = fake_client.get_params["metricKeys"].split(",")
    assert set(requested) == {
        "coverage",
        "code_smells",
        "sqale_index",
        "security_hotspots",
        "sqale_rating",
    }


def test_fetch_metrics_maps_lower_maintainability_rating(monkeypatch):
    """A non-A ``sqale_rating`` (e.g. 3.0) maps to the matching letter (C)."""
    payload = {
        "component": {
            "measures": [
                {"metric": "coverage", "value": "80.0"},
                {"metric": "code_smells", "value": "42"},
                {"metric": "sqale_index", "value": "999"},
                {"metric": "security_hotspots", "value": "5"},
                {"metric": "sqale_rating", "value": "3.0"},
            ]
        }
    }
    fake_client = _FakeClient(payload)
    monkeypatch.setattr(sonar_client_module.httpx, "Client", fake_client)

    metrics = HttpSonarClient(
        base_url="https://sonar.example.com/",
        token="tok",
        project_key="proj",
    ).fetch_metrics("deadbee")

    assert metrics.maintainability_rating == "C"
    assert metrics.code_smells == 42
    assert metrics.security_hotspots == 5


def test_fetch_metrics_missing_project_key_fails_loud(monkeypatch):
    """Req 12.1: a missing project key surfaces a clear error (fail-loud)."""
    # No httpx call should be attempted; make it explode if it is.
    monkeypatch.setattr(sonar_client_module.httpx, "Client", MagicMock(side_effect=AssertionError))

    client = HttpSonarClient(base_url="https://sonar.example.com", token="t", project_key="")

    with pytest.raises(ValueError, match="SONARQUBE_PROJECT_KEY"):
        client.fetch_metrics("abc1234")


# --------------------------------------------------------------------------- #
# GitHub reporting (Requirement 14.1) — mocked GitHubService, no merge ever.
# --------------------------------------------------------------------------- #


def _context() -> WorkflowContext:
    """A minimal WorkflowContext ready for the CreatePullRequestStage."""
    return WorkflowContext(
        repository="octo/example",
        repo_name="example",
        clone_url="https://github.com/octo/example.git",
        branch="main",
        commit_sha="abc1234def5678",
        ai_branch_name="ai-sde/review-abc1234-20240101000000",
    )


def test_create_pr_stage_opens_pr_for_commit_and_records_url():
    """Req 14.1: the PR is opened for the Commit_SHA and ``pr_url`` is recorded."""
    github_service = MagicMock(spec=GitHubService)
    github_service.open_pull_request.return_value = "https://github.com/octo/example/pull/1"

    context = _context()
    CreatePullRequestStage(github_service).execute(context)

    github_service.open_pull_request.assert_called_once()
    _, kwargs = github_service.open_pull_request.call_args
    assert kwargs["repo_full_name"] == "octo/example"
    assert kwargs["head_branch"] == context.ai_branch_name
    assert kwargs["base_branch"] == "main"
    # The report/PR is attached for the triggering commit (short SHA in the title).
    assert context.commit_sha[:7] in kwargs["title"]

    # The stage records the PR URL on the shared context.
    assert context.pr_url == "https://github.com/octo/example/pull/1"


def test_create_pr_stage_never_invokes_a_merge():
    """Property 20: no merge action is ever invoked by the reporting flow.

    The service is spec'd to the real :class:`GitHubService`, which exposes no
    merge method at all — so a merge could not be called even accidentally. We
    additionally assert that across every interaction the mock recorded, nothing
    resembling a merge (or any write beyond opening the PR) was invoked.
    """
    github_service = MagicMock(spec=GitHubService)
    github_service.open_pull_request.return_value = "https://github.com/octo/example/pull/2"

    context = _context()
    CreatePullRequestStage(github_service).execute(context)

    # The real GitHubService has no merge surface for the stage to reach.
    assert not hasattr(GitHubService, "merge_pull_request")
    assert not any("merge" in name for name in dir(GitHubService) if not name.startswith("_"))

    # No merge-like interaction was recorded on the mock during the flow.
    merge_calls = [c for c in github_service.mock_calls if "merge" in str(c).lower()]
    assert merge_calls == []

    # The only service method the flow calls is open_pull_request.
    called_methods = {
        c[0] for c in github_service.method_calls
    }
    assert called_methods == {"open_pull_request"}
