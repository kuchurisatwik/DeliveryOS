"""Tests for the PIPELINE_MODE switch (security / testing / both).

The switch selects which pipeline(s) run on a push. These deterministic example
tests cover the mode-resolution helper and assert the workflow gates the testing
and security phases on the resolved mode, while always running shared setup and
the final report/commit/PR stages.
"""

from __future__ import annotations

from unittest.mock import patch

import app.github.routes as routes
from app.github.routes import resolve_pipeline_mode


# --------------------------------------------------------------------------- #
# resolve_pipeline_mode
# --------------------------------------------------------------------------- #


def test_resolve_mode_accepts_valid_values():
    for value in ("security", "testing", "both"):
        with patch.object(routes.settings, "PIPELINE_MODE", value):
            assert resolve_pipeline_mode() == value


def test_resolve_mode_normalizes_case_and_whitespace():
    with patch.object(routes.settings, "PIPELINE_MODE", "  SecUrity  "):
        assert resolve_pipeline_mode() == "security"


def test_resolve_mode_falls_back_to_both_on_unknown():
    with patch.object(routes.settings, "PIPELINE_MODE", "nonsense"):
        assert resolve_pipeline_mode() == "both"


def test_resolve_mode_falls_back_to_both_on_empty():
    with patch.object(routes.settings, "PIPELINE_MODE", ""):
        assert resolve_pipeline_mode() == "both"


# --------------------------------------------------------------------------- #
# run_ai_sde_workflow gating
# --------------------------------------------------------------------------- #


class _PushEvent:
    """Minimal stand-in for PushEventSchema (only the fields the workflow reads)."""

    class _Repo:
        full_name = "octo/example"
        name = "example"
        clone_url = "https://github.com/octo/example.git"

    def __init__(self) -> None:
        self.ref = "refs/heads/main"
        self.after = "abc1234def5678"
        self.repository = self._Repo()


def _run_with_mode(mode: str):
    """Run the workflow under a given mode with all real stages/services mocked out.

    Returns (testing_called, security_called, post_ran) so the test can assert
    which phases executed. Setup pre-stages and post stages are stubbed to no-ops
    via a mocked orchestrator so nothing touches git/network/LLM.
    """
    calls = {"testing": False, "security": False, "post_runs": 0}

    class _FakeResult:
        status = "SUCCESS"
        errors = []
        completed_stages = []

    class _FakeOrchestrator:
        def run_pipeline(self, context, stages):
            # The workflow runs pre-stages first and post-stages last through the
            # orchestrator; count invocations so we can confirm post-stages ran.
            calls["post_runs"] += 1
            return _FakeResult()

    def _fake_testing(*args, **kwargs):
        calls["testing"] = True
        return None

    def _fake_security(*args, **kwargs):
        calls["security"] = True

    with patch.object(routes.settings, "PIPELINE_MODE", mode), \
        patch.object(routes, "WorkflowOrchestrator", _FakeOrchestrator), \
        patch.object(routes, "GitService"), \
        patch.object(routes, "GitHubService"), \
        patch.object(routes, "LLMService"), \
        patch.object(routes, "EngineeringAgent"), \
        patch.object(routes, "ValidationEngine"), \
        patch.object(routes, "RepairAgent"), \
        patch.object(routes, "WorkspaceWriterService"), \
        patch.object(routes, "_run_testing_pipeline", _fake_testing), \
        patch.object(routes, "_run_security_pipeline", _fake_security):
        routes.run_ai_sde_workflow(_PushEvent())

    return calls


def test_security_only_mode_runs_security_not_testing():
    calls = _run_with_mode("security")
    assert calls["security"] is True
    assert calls["testing"] is False
    # Pre-stages + post-stages still ran through the orchestrator.
    assert calls["post_runs"] >= 2


def test_testing_only_mode_runs_testing_not_security():
    calls = _run_with_mode("testing")
    assert calls["testing"] is True
    assert calls["security"] is False
    assert calls["post_runs"] >= 2


def test_both_mode_runs_both_pipelines():
    calls = _run_with_mode("both")
    assert calls["testing"] is True
    assert calls["security"] is True
