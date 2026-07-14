"""Property 20: No automatic merge (security-pipeline).

*For any* pipeline run and any resulting ``Merge_Confidence`` value (including
the maximum), no merge action is ever invoked — candidate patches are committed
to the PR branch only and the final merge decision is left to a human.

The report/PR flow is driven through the real workflow stages with the impure
boundaries mocked:

* :class:`~app.workflows.stages.CommitStage` and
  :class:`~app.workflows.stages.PushBranchStage` run against a mock
  :class:`~app.services.git_service.GitService` — this is how candidate patches
  reach the PR *branch* (commit + push), and nothing here can merge.
* :class:`~app.workflows.stages.CreatePullRequestStage` runs against a mock
  :class:`~app.services.github_service.GitHubService` — this opens the PR.

Across the whole confidence range (generated from arbitrary
``MergeConfidenceInputs`` via the deterministic ``compute_merge_confidence`` and
explicitly including the maximum score of 100) we assert the flow opens a PR but
never invokes anything resembling a merge, and that :class:`GitHubService`
exposes no merge surface at all.

Validates: Requirements 10.3, 13.3, 14.5
"""

from __future__ import annotations

from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from app.security.governance.merge_confidence import (
    SCORE_MAX,
    compute_merge_confidence,
)
from app.security.models import Merge_Confidence, MergeConfidenceInputs
from app.services.git_service import GitService
from app.services.github_service import GitHubService
from app.workflows.context import WorkflowContext
from app.workflows.stages import (
    CommitStage,
    CreatePullRequestStage,
    PushBranchStage,
)
from tests.security.strategies import merge_confidence_inputs


@st.composite
def merge_confidences(draw: st.DrawFn) -> Merge_Confidence:
    """A ``Merge_Confidence`` spanning the full advisory range.

    Two thirds of the time the value is derived deterministically from arbitrary
    :class:`MergeConfidenceInputs` (covering the natural distribution); the
    remaining third forces a boundary score, guaranteeing the *maximum* (100)
    and *minimum* (0) confidences are exercised — Property 20 must hold even at
    maximum confidence.
    """
    inputs = draw(merge_confidence_inputs())
    boundary = draw(st.sampled_from([None, SCORE_MAX, 0.0, SCORE_MAX]))
    if boundary is None:
        return compute_merge_confidence(inputs)
    return Merge_Confidence(score=boundary, inputs=inputs, advisory=True)


def _context(confidence: Merge_Confidence) -> WorkflowContext:
    """A minimal WorkflowContext carrying the generated merge confidence."""
    return WorkflowContext(
        repository="octo/example",
        repo_name="example",
        clone_url="https://github.com/octo/example.git",
        branch="main",
        commit_sha="abc1234def5678",
        workspace="/tmp/workspace/example",
        ai_branch_name="ai-sde/review-abc1234-20240101000000",
        security_merge_confidence=confidence,
    )


# Feature: security-pipeline, Property 20: For any pipeline run and any resulting Merge_Confidence value (including the maximum), no merge action is ever invoked — candidate patches are committed to the PR branch only and the final merge decision is left to a human.
@settings(max_examples=100)
@given(confidence=merge_confidences())
def test_property_20_flow_opens_pr_but_never_merges(
    confidence: Merge_Confidence,
) -> None:
    git_service = MagicMock(spec=GitService)
    github_service = MagicMock(spec=GitHubService)
    github_service.open_pull_request.return_value = (
        "https://github.com/octo/example/pull/1"
    )

    context = _context(confidence)

    # Drive the real report/PR flow: patches are committed to the PR *branch*
    # (commit + push), then the PR is opened. No stage performs a merge.
    CommitStage(git_service).execute(context)
    PushBranchStage(git_service).execute(context)
    CreatePullRequestStage(github_service).execute(context)

    # A PR is created (the human-review surface exists) regardless of confidence.
    github_service.open_pull_request.assert_called_once()
    assert context.pr_url == "https://github.com/octo/example/pull/1"

    # Candidate patches reached the PR branch only: committed and pushed.
    git_service.commit_changes.assert_called_once()
    git_service.push_branch.assert_called_once()

    # No merge-like interaction was recorded on EITHER service mock — even at
    # maximum confidence the flow never auto-merges (Requirements 13.3, 14.5).
    all_calls = list(github_service.mock_calls) + list(git_service.mock_calls)
    merge_calls = [c for c in all_calls if "merge" in str(c).lower()]
    assert merge_calls == []

    # The GitHub service's only invoked method is opening the PR.
    called_methods = {c[0] for c in github_service.method_calls}
    assert called_methods == {"open_pull_request"}


# Feature: security-pipeline, Property 20: For any pipeline run and any resulting Merge_Confidence value (including the maximum), no merge action is ever invoked — candidate patches are committed to the PR branch only and the final merge decision is left to a human.
@settings(max_examples=100)
@given(confidence=merge_confidences())
def test_property_20_github_service_exposes_no_merge_surface(
    confidence: Merge_Confidence,
) -> None:
    # The advisory confidence never grants a merge capability: GitHubService has
    # no merge method at all, so no run — at any score, including the maximum —
    # could reach one (Requirements 10.3, 13.3, 14.5).
    assert 0.0 <= confidence.score <= SCORE_MAX
    assert confidence.advisory is True
    assert not hasattr(GitHubService, "merge_pull_request")
    assert not any(
        "merge" in name for name in dir(GitHubService) if not name.startswith("_")
    )
