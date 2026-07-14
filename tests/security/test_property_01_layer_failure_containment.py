"""Property 1: Layer-failure containment (security-pipeline).

Exercises the orchestration-level containment guarantee: when a single security
layer raises an unrecoverable error, the Pipeline stops all subsequent layers
(they are never invoked) and still records which layer failed so a diagnostic
``Pull_Request_Report`` can be produced whose ``failed_layer`` names exactly the
failing layer (Requirement 1.4).

The test drives the real
:func:`app.security.pipeline.run_security_pipeline_with_containment` over a list
of FAKE :class:`~app.workflows.stages.Stage` subclasses. Each fake stage:

* has a distinct mapped layer name (via the ``layer_names`` mapping keyed by its
  class name, mirroring :data:`DEFAULT_SECURITY_LAYER_NAMES`), and
* appends its index to a shared *run recorder* the moment it is invoked.

Hypothesis picks which single stage index (if any) raises. Because the
orchestrator stops on the first failure, the recorder proves that:

* no stage after the failing index was ever invoked,
* every stage before the failing index ran, and
* ``context.failed_layer`` equals the failing stage's mapped layer name.

The all-success case (no chosen failing stage) asserts ``failed_layer`` stays
``None``. The pure decision helper
:func:`app.security.pipeline.determine_failed_layer` is also tested directly for
the index -> layer-name mapping.

Validates: Requirements 1.4
"""

from __future__ import annotations

from typing import List, Optional

from hypothesis import given, settings
from hypothesis import strategies as st

from app.security.pipeline import (
    determine_failed_layer,
    run_security_pipeline_with_containment,
)
from app.workflows.context import WorkflowContext
from app.workflows.orchestrator import WorkflowOrchestrator
from app.workflows.stages import Stage


def _make_context() -> WorkflowContext:
    """A minimal valid WorkflowContext (only the required identity fields)."""

    return WorkflowContext(
        repository="acme/widgets",
        repo_name="widgets",
        clone_url="https://example.invalid/acme/widgets.git",
        branch="main",
        commit_sha="0123456789abcdef0123456789abcdef01234567",
    )


def _make_fake_stage(index: int, layer_name: str, recorder: List[int], raises: bool) -> Stage:
    """Build a distinct Stage subclass that records invocation (and maybe raises).

    A fresh subclass per stage gives each stage a unique ``__name__`` so it can be
    mapped to its own layer name via the ``layer_names`` mapping (exactly the way
    the production code keys :data:`DEFAULT_SECURITY_LAYER_NAMES` by class name).
    """

    def execute(self: Stage, context: WorkflowContext) -> None:  # noqa: ANN001
        # Record invocation FIRST so a stage that is reached always appears in the
        # recorder, even if it goes on to raise. This is what proves that stages
        # *after* the failing one were never invoked.
        recorder.append(index)
        if raises:
            raise RuntimeError(f"unrecoverable error in {layer_name}")

    cls = type(f"FakeStage_{layer_name}", (Stage,), {"execute": execute})
    return cls()


@st.composite
def _stage_plans(draw: st.DrawFn):
    """A plan: number of stages, their distinct layer names, and the failing index.

    ``fail_index`` is ``None`` for the all-success case, otherwise an index in
    ``[0, n)`` identifying the single stage that raises.
    """

    n = draw(st.integers(min_value=1, max_value=6))
    layer_names = [f"Layer{i}" for i in range(n)]
    fail_index = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=n - 1)))
    return n, layer_names, fail_index


# Feature: security-pipeline, Property 1: For any choice of a single layer that raises an unrecoverable error, the Pipeline stops all subsequent layers (they are never invoked) and still produces a Pull_Request_Report whose failed_layer names exactly the failing layer.
@settings(max_examples=100)
@given(plan=_stage_plans())
def test_property_01_layer_failure_containment(plan) -> None:
    n, layer_names, fail_index = plan

    recorder: List[int] = []
    stages: List[Stage] = [
        _make_fake_stage(i, layer_names[i], recorder, raises=(i == fail_index))
        for i in range(n)
    ]
    # layer_names mapping keyed by each stage's class name -> its distinct layer.
    layer_name_map = {type(stage).__name__: layer_names[i] for i, stage in enumerate(stages)}

    orchestrator = WorkflowOrchestrator()
    context = _make_context()

    result = run_security_pipeline_with_containment(
        orchestrator, context, stages, layer_names=layer_name_map
    )

    if fail_index is None:
        # All-success case: every stage ran, in order, and no layer is recorded
        # as failed.
        assert result.status == "SUCCESS"
        assert recorder == list(range(n))
        assert context.failed_layer is None
        assert len(result.completed_stages) == n
    else:
        # Containment: the pipeline stops on the first failure.
        assert result.status == "FAILED"
        # Every stage BEFORE the failing index ran; the failing stage was invoked;
        # NO stage AFTER the failing index was ever invoked (recorder proves it).
        assert recorder == list(range(fail_index + 1))
        # Stages strictly before the failing one completed successfully.
        assert len(result.completed_stages) == fail_index
        # failed_layer names EXACTLY the failing layer.
        assert context.failed_layer == layer_names[fail_index]


# Feature: security-pipeline, Property 1: For any choice of a single layer that raises an unrecoverable error, the Pipeline stops all subsequent layers (they are never invoked) and still produces a Pull_Request_Report whose failed_layer names exactly the failing layer.
@settings(max_examples=100)
@given(data=st.data())
def test_property_01_determine_failed_layer_mapping(data: st.DataObject) -> None:
    """The pure decision maps the count of completed stages to the failing layer.

    The failing stage is the one at index ``completed_count`` (the orchestrator
    stops on the first failure, so all earlier stages completed and none later ran);
    once every stage has completed the result is ``None``.
    """

    n = data.draw(st.integers(min_value=1, max_value=6))
    layer_names = [f"Layer{i}" for i in range(n)]
    recorder: List[int] = []
    stages: List[Stage] = [
        _make_fake_stage(i, layer_names[i], recorder, raises=False) for i in range(n)
    ]
    layer_name_map = {type(stage).__name__: layer_names[i] for i, stage in enumerate(stages)}

    # For every possible number of completed stages (0..n) the mapping holds.
    completed_count = data.draw(st.integers(min_value=0, max_value=n))
    expected: Optional[str] = None if completed_count >= n else layer_names[completed_count]

    assert determine_failed_layer(stages, completed_count, layer_name_map) == expected
