"""Property 4: Scanner scoping (security-pipeline).

Exercises the Layer 2 :class:`~app.security.detection.runner.DetectionStage`: it
must derive **one** :class:`ScanScope` from the repository context and share that
*same* scope with every scanner adapter.

The test injects a set of in-memory *recording* ``ScannerAdapter`` fakes that
capture the ``ScanScope`` instance they receive, builds a ``WorkflowContext``
whose ``retrieved_knowledge`` is a generated ``RepositoryContext`` (varied
``changed_feature.files`` / ``related_symbols`` and top-level ``related_symbols``),
and also covers the fallback where ``changed_feature`` is ``None`` and only
``context.changed_files`` is populated. After running the stage, every fake must
have received the identical scope, and that scope must equal the one produced by
``DetectionStage._derive_scope(context)``.

Validates: Requirements 3.2
"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from app.schemas.repository import ChangedFeature, RelatedSymbol, RepositoryContext
from app.security.detection.runner import DetectionStage
from app.security.models import Finding, ScanScope
from app.workflows.context import WorkflowContext

# ---------------------------------------------------------------------------
# Recording scanner adapter (in-memory fake).
# ---------------------------------------------------------------------------


class RecordingScannerAdapter:
    """A ``ScannerAdapter`` fake that records every ``ScanScope`` it is given."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.received_scopes: list[ScanScope] = []

    def scan(self, scope: ScanScope) -> list[Finding]:
        self.received_scopes.append(scope)
        return []


# ---------------------------------------------------------------------------
# Generators for repository context / changed files.
# ---------------------------------------------------------------------------

#: Identifiers: mix of ASCII and non-ASCII to stress scope derivation.
_names = st.one_of(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz_0123456789", min_size=1, max_size=15),
    st.text(alphabet="ñüéçΩ字符测试λμ", min_size=1, max_size=8),
)

#: Relative source paths (may include duplicates so we exercise dedup ordering).
_paths = st.builds(
    lambda stem: f"{stem}.py",
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz_/", min_size=1, max_size=20),
)


@st.composite
def related_symbols(draw: st.DrawFn) -> RelatedSymbol:
    return RelatedSymbol(
        name=draw(_names),
        type=draw(st.sampled_from(("function", "class", "unknown"))),
        relation=draw(st.sampled_from(("caller", "callee", "imported"))),
    )


@st.composite
def workflow_contexts(draw: st.DrawFn) -> WorkflowContext:
    """Build a WorkflowContext with a varied RepositoryContext.

    Half the time the context carries a ``changed_feature`` (files + related
    symbols); otherwise ``changed_feature`` is ``None`` and only
    ``changed_files`` is populated (the fallback path in ``_derive_scope``).
    Top-level ``related_symbols`` on the repo context are also varied so both
    contributors to the derived scope are exercised.
    """

    changed_files = draw(st.lists(_paths, max_size=6))
    top_level_related = draw(st.lists(related_symbols(), max_size=5))

    use_changed_feature = draw(st.booleans())
    if use_changed_feature:
        feature_files = draw(st.lists(_paths, max_size=6))
        feature_related = draw(st.lists(related_symbols(), max_size=5))
        changed_feature: ChangedFeature | None = ChangedFeature(
            files=feature_files,
            related_symbols=feature_related,
        )
    else:
        changed_feature = None

    repo_ctx = RepositoryContext(
        related_symbols=top_level_related,
        changed_feature=changed_feature,
    )

    return WorkflowContext(
        repository="owner/repo",
        repo_name="repo",
        clone_url="https://example.com/owner/repo.git",
        branch="main",
        commit_sha="deadbeef",
        changed_files=changed_files,
        retrieved_knowledge=repo_ctx,
    )


# Feature: security-pipeline, Property 4: For any RepoContext, the ScanScope passed to every scanner adapter equals the scope derived from that context (the changed feature's paths plus related symbols) — all adapters receive the same derived scope.
@settings(max_examples=100, deadline=None)
@given(context=workflow_contexts())
def test_property_04_scanner_scoping(context: WorkflowContext) -> None:
    fakes = [RecordingScannerAdapter(name) for name in ("s1", "s2", "s3", "s4", "s5", "s6")]
    stage = DetectionStage(adapters=fakes)

    expected_scope = stage._derive_scope(context)

    stage.execute(context)

    # Every adapter must have been invoked exactly once...
    for fake in fakes:
        assert len(fake.received_scopes) == 1, (
            f"adapter {fake.name!r} was scanned {len(fake.received_scopes)} time(s), expected 1"
        )

    received = [fake.received_scopes[0] for fake in fakes]

    # ...with a scope equal to the one derived from the RepoContext...
    for fake, scope in zip(fakes, received):
        assert scope == expected_scope, (
            f"adapter {fake.name!r} received scope {scope!r}, expected {expected_scope!r}"
        )

    # ...and all adapters must have received the same derived scope.
    first = received[0]
    for scope in received[1:]:
        assert scope == first, "adapters received differing scopes"

    # The derived scope is a proper ScanScope (paths/related_symbols tuples).
    assert isinstance(expected_scope, ScanScope)
    assert isinstance(expected_scope.paths, tuple)
    assert isinstance(expected_scope.related_symbols, tuple)
