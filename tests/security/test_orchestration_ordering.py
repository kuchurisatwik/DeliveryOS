"""Example tests for security-pipeline orchestration ordering and missing inputs.

Deterministic example/unit tests (NOT property-based). They pin down two
orchestration guarantees from Requirement 1:

* **Strict layer order (Requirements 1.2, 1.5)** — the security stage sequence is
  ``SecurityConfigResolutionStage → DetectionStage → IntelligenceStage →
  GovernanceStage`` and config resolution always precedes detection. This is
  asserted two ways: (1) statically, over the class order returned by
  :func:`~app.security.pipeline.build_security_stages`, and (2) dynamically, by
  running recorder fakes through the real
  :class:`~app.workflows.orchestrator.WorkflowOrchestrator` and capturing the
  observed execution order.

* **Missing-input guard (Requirement 1.3)** — :func:`ensure_security_inputs`
  raises :class:`~app.security.pipeline.MissingPipelineInputError` naming exactly
  the missing input(s) (``Commit_SHA`` / ``Git_Diff``) for every present/absent
  combination. Git_Diff is considered present when a structured diff *or*
  ``changed_files`` is set.

Requirements: 1.2, 1.3, 1.5
"""

from __future__ import annotations

from typing import List
from unittest.mock import MagicMock

import pytest

from app.security.pipeline import (
    DEFAULT_SECURITY_LAYER_NAMES,
    GovernanceStage,
    MissingPipelineInputError,
    SecurityConfigResolutionStage,
    build_security_stages,
    ensure_security_inputs,
)
from app.security.detection.runner import DetectionStage
from app.security.intelligence.stage import IntelligenceStage
from app.workflows.context import WorkflowContext
from app.workflows.orchestrator import WorkflowOrchestrator
from app.workflows.stages import Stage


# --------------------------------------------------------------------------- #
# Helpers / fakes
# --------------------------------------------------------------------------- #


class RecorderStage(Stage):
    """A no-op stage that appends its label to a shared recorder on execute.

    Lets a test capture the *observed* execution order the orchestrator produces
    without running any real scanners, LLM calls, or network I/O.
    """

    def __init__(self, label: str, recorder: List[str]) -> None:
        self._label = label
        self._recorder = recorder

    @property
    def name(self) -> str:  # keep orchestrator logging meaningful
        return self._label

    def execute(self, context: WorkflowContext) -> None:
        self._recorder.append(self._label)


def _context(**overrides) -> WorkflowContext:
    """Minimal WorkflowContext with sensible defaults for these tests."""
    params = dict(
        repository="octo/example",
        repo_name="example",
        clone_url="https://github.com/octo/example.git",
        branch="main",
        commit_sha="abc1234def5678",
    )
    params.update(overrides)
    return WorkflowContext(**params)


# --------------------------------------------------------------------------- #
# Strict layer order (Requirements 1.2, 1.5)
# --------------------------------------------------------------------------- #


def test_build_security_stages_returns_strict_layer_order():
    """Req 1.2/1.5: the composed stage list is config → detection → intel → gov."""
    stages = build_security_stages(MagicMock())

    stage_types = [type(stage) for stage in stages]
    assert stage_types == [
        SecurityConfigResolutionStage,
        DetectionStage,
        IntelligenceStage,
        GovernanceStage,
    ]


def test_build_security_stages_places_config_before_detection():
    """Req 1.5: config resolution strictly precedes detection in the sequence."""
    stages = build_security_stages(MagicMock())

    config_index = next(
        i for i, s in enumerate(stages) if isinstance(s, SecurityConfigResolutionStage)
    )
    detection_index = next(
        i for i, s in enumerate(stages) if isinstance(s, DetectionStage)
    )
    assert config_index < detection_index


def test_orchestrator_executes_security_layers_in_declared_order():
    """Req 1.2/1.5: running the sequence yields config → detection → intel → gov.

    Recorder fakes are injected so no real scanners/LLM/network run; the
    orchestrator's observed execution order is captured and asserted.
    """
    recorder: List[str] = []
    config = RecorderStage("Configuration", recorder)
    detection = RecorderStage("Detection", recorder)
    intelligence = RecorderStage("Intelligence", recorder)
    governance = RecorderStage("Governance", recorder)

    stages = build_security_stages(
        MagicMock(),
        config_stage=config,
        detection_stage=detection,
        intelligence_stage=intelligence,
        governance_stage=governance,
    )

    context = _context(changed_files=["app/service.py"])
    result = WorkflowOrchestrator().run_pipeline(context, stages)

    assert result.status == "SUCCESS"
    assert recorder == ["Configuration", "Detection", "Intelligence", "Governance"]
    # Config resolution precedes detection (Req 1.5).
    assert recorder.index("Configuration") < recorder.index("Detection")


def test_default_layer_names_cover_the_four_security_stages():
    """The layer-name mapping labels each security stage class (Req 1.2/1.4)."""
    for stage_cls in (
        SecurityConfigResolutionStage,
        DetectionStage,
        IntelligenceStage,
        GovernanceStage,
    ):
        assert stage_cls.__name__ in DEFAULT_SECURITY_LAYER_NAMES


# --------------------------------------------------------------------------- #
# Missing-input guard (Requirement 1.3)
# --------------------------------------------------------------------------- #


def test_ensure_security_inputs_passes_when_both_present_via_changed_files():
    """Req 1.3: both inputs present (Git_Diff via changed_files) -> no error."""
    context = _context(changed_files=["app/service.py"])
    # Should not raise.
    ensure_security_inputs(context)


def test_ensure_security_inputs_passes_when_git_diff_via_structured_diff():
    """Req 1.3: Git_Diff considered present when the structured diff is set."""
    context = _context(
        structured_diff={"added": ["app/new.py"], "modified": [], "deleted": [], "renamed": []}
    )
    # Should not raise.
    ensure_security_inputs(context)


def test_ensure_security_inputs_raises_naming_commit_sha_when_missing():
    """Req 1.3: missing Commit_SHA -> diagnostic names exactly Commit_SHA."""
    context = _context(commit_sha="", changed_files=["app/service.py"])

    with pytest.raises(MissingPipelineInputError) as exc_info:
        ensure_security_inputs(context)

    message = str(exc_info.value)
    assert "Commit_SHA" in message
    assert "Git_Diff" not in message


def test_ensure_security_inputs_raises_naming_git_diff_when_missing():
    """Req 1.3: missing Git_Diff -> diagnostic names exactly Git_Diff."""
    context = _context(commit_sha="abc1234")  # no changed_files, empty structured diff

    with pytest.raises(MissingPipelineInputError) as exc_info:
        ensure_security_inputs(context)

    message = str(exc_info.value)
    assert "Git_Diff" in message
    assert "Commit_SHA" not in message


def test_ensure_security_inputs_raises_naming_both_when_both_missing():
    """Req 1.3: both inputs missing -> diagnostic names both Commit_SHA and Git_Diff."""
    context = _context(commit_sha="")

    with pytest.raises(MissingPipelineInputError) as exc_info:
        ensure_security_inputs(context)

    message = str(exc_info.value)
    assert "Commit_SHA" in message
    assert "Git_Diff" in message


@pytest.mark.parametrize(
    "commit_sha, changed_files, expected_missing, expected_present",
    [
        ("abc1234", ["app/service.py"], [], ["Commit_SHA", "Git_Diff"]),
        ("", ["app/service.py"], ["Commit_SHA"], ["Git_Diff"]),
        ("abc1234", [], ["Git_Diff"], ["Commit_SHA"]),
        ("", [], ["Commit_SHA", "Git_Diff"], []),
    ],
)
def test_ensure_security_inputs_names_exactly_the_missing_inputs(
    commit_sha, changed_files, expected_missing, expected_present
):
    """Req 1.3: across every present/absent combination the diagnostic names
    exactly the missing input(s) and omits the present one(s)."""
    context = _context(commit_sha=commit_sha, changed_files=changed_files)

    if not expected_missing:
        # Both present -> no error raised.
        ensure_security_inputs(context)
        return

    with pytest.raises(MissingPipelineInputError) as exc_info:
        ensure_security_inputs(context)

    message = str(exc_info.value)
    for name in expected_missing:
        assert name in message
    for name in expected_present:
        assert name not in message
