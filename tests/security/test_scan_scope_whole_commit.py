"""Regression tests for whole-commit scan scoping (security-pipeline).

These pin down the fix for the multi-feature under-scoping gap: the security
:class:`~app.security.models.ScanScope` derived by
:func:`app.security.detection.runner.derive_scan_scope` must cover the *union of
every file changed by the commit*, never just the last processed
``EngineeringTask``'s feature.

Background: ``context.retrieved_knowledge`` is per-task and is overwritten on each
engineering-loop iteration, so after the loop it holds only the last task's
``changed_feature``. Detection must not inherit that narrowing — the whole commit
is the source of truth for the scanned paths, and the per-task context is used
only additively (it can add paths / related symbols, never remove them).

These are deterministic example tests (NOT property-based).
"""

from __future__ import annotations

from app.schemas.repository import ChangedFeature, RelatedSymbol, RepositoryContext
from app.security.detection.runner import derive_scan_scope
from app.workflows.context import EngineeringTask, WorkflowContext


def _context(**overrides) -> WorkflowContext:
    params = dict(
        repository="octo/example",
        repo_name="example",
        clone_url="https://github.com/octo/example.git",
        branch="main",
        commit_sha="abc1234",
    )
    params.update(overrides)
    return WorkflowContext(**params)


def test_scope_covers_whole_commit_not_just_last_task_feature():
    """The regression case: a multi-feature commit must scan every changed file.

    A payment + auth commit whose ``retrieved_knowledge`` (last task) only names
    the auth files must still yield a scope containing the payment files.
    """
    changed_files = [
        "app/payment_service.py",
        "tests/test_payment.py",
        "app/auth.py",
        "app/auth_service.py",
    ]
    # retrieved_knowledge reflects ONLY the last processed task ("auth").
    last_task_ctx = RepositoryContext(
        changed_feature=ChangedFeature(
            files=["app/auth.py", "app/auth_service.py"],
        )
    )
    context = _context(
        changed_files=changed_files,
        tasks=[
            EngineeringTask(
                feature_name="payment",
                related_files=["app/payment_service.py", "tests/test_payment.py"],
            ),
            EngineeringTask(
                feature_name="auth",
                related_files=["app/auth.py", "app/auth_service.py"],
            ),
        ],
        retrieved_knowledge=last_task_ctx,
    )

    scope = derive_scan_scope(context)

    # Every changed file across BOTH features is in scope (the payment files, which
    # the old logic dropped, are present).
    for path in changed_files:
        assert path in scope.paths, f"{path} was under-scoped out of the security scan"


def test_task_related_files_are_unioned_even_if_missing_from_changed_files():
    """Files named only by task decomposition are still scanned."""
    context = _context(
        changed_files=["app/a.py"],
        tasks=[
            EngineeringTask(feature_name="a", related_files=["app/a.py"]),
            EngineeringTask(feature_name="b", related_files=["app/b.py"]),
        ],
    )

    scope = derive_scan_scope(context)

    assert "app/a.py" in scope.paths
    assert "app/b.py" in scope.paths


def test_retrieved_context_is_additive_only_and_enriches_related_symbols():
    """Changed_Feature files/symbols add to the scope; related symbols surface."""
    context = _context(
        changed_files=["app/core.py"],
        retrieved_knowledge=RepositoryContext(
            changed_feature=ChangedFeature(
                files=["app/extra.py"],  # additive: not in changed_files
                related_symbols=[
                    RelatedSymbol(name="helper", type="function", relation="callee")
                ],
            ),
            related_symbols=[
                RelatedSymbol(name="top_level_dep", type="function", relation="imported")
            ],
        ),
    )

    scope = derive_scan_scope(context)

    # Whole-commit file plus the additive Changed_Feature file.
    assert "app/core.py" in scope.paths
    assert "app/extra.py" in scope.paths
    # Related symbols from both the changed feature and the top-level context.
    assert "helper" in scope.related_symbols
    assert "top_level_dep" in scope.related_symbols


def test_scope_paths_are_deduplicated():
    """Overlap between changed_files, tasks, and changed_feature collapses cleanly."""
    context = _context(
        changed_files=["app/dup.py"],
        tasks=[EngineeringTask(feature_name="dup", related_files=["app/dup.py"])],
        retrieved_knowledge=RepositoryContext(
            changed_feature=ChangedFeature(files=["app/dup.py"]),
        ),
    )

    scope = derive_scan_scope(context)

    assert list(scope.paths).count("app/dup.py") == 1


def test_no_tasks_and_no_context_falls_back_to_changed_files():
    """With no tasks and no retrieved context, the raw changed files are the scope."""
    context = _context(changed_files=["app/only.py"])

    scope = derive_scan_scope(context)

    assert scope.paths == ("app/only.py",)
    assert scope.related_symbols == ()
