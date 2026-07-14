"""Property 2: Change coverage (security-pipeline).

Exercises the Layer 1 Repository Intelligence pipeline end-to-end over a small
synthetic Python repository: a set of ``.py`` files, each containing a known set
of top-level functions and classes, is written into a temp workspace, indexed by
``RepositoryIndexer``, and then queried by
``ContextRetrievalEngine.retrieve(changed_files, structured_diff)``. The resulting
``RepositoryContext.changed_feature`` must cover every changed path and every
changed function/class definition.

Validates: Requirements 2.1
"""

from __future__ import annotations

import keyword
import os
import shutil
import tempfile
from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.services.repository.indexer import RepositoryIndexer
from app.services.repository.retriever import ContextRetrievalEngine

# ---------------------------------------------------------------------------
# Generators for a small synthetic Python repository.
# ---------------------------------------------------------------------------

#: Valid, non-keyword Python identifiers used for module stems and symbol names.
_identifiers = st.from_regex(r"[a-z][a-z0-9_]{0,9}", fullmatch=True).filter(
    lambda s: not keyword.iskeyword(s) and not keyword.issoftkeyword(s)
)


@st.composite
def synthetic_repos(draw: st.DrawFn) -> dict[str, Any]:
    """Generate a synthetic repo spec plus the subset of files marked changed.

    Returns a dict with:
    - ``files``: mapping of relative ``.py`` path -> {"functions": [...],
      "classes": [...]} where the function/class names are unique within the
      file (so the ``UNIQUE(file_id, name)`` index never collapses them),
    - ``changed``: the subset of paths passed to ``retrieve`` as changed files.

    Keeping definitions top-level (no methods/nesting) means the indexer stores
    each symbol under its simple name, so coverage can be asserted by name.
    """

    n_files = draw(st.integers(min_value=1, max_value=4))
    file_stems = draw(
        st.lists(_identifiers, min_size=n_files, max_size=n_files, unique=True)
    )

    files: dict[str, Any] = {}
    for stem in file_stems:
        path = f"mod_{stem}.py"
        # Draw a set of names unique within this file, then split into
        # functions and classes (a name is never both, avoiding collisions).
        names = draw(st.lists(_identifiers, min_size=0, max_size=6, unique=True))
        kinds = [draw(st.sampled_from(("function", "class"))) for _ in names]
        functions = [n for n, k in zip(names, kinds) if k == "function"]
        classes = [n for n, k in zip(names, kinds) if k == "class"]
        files[path] = {"functions": functions, "classes": classes}

    # Choose at least one changed file so the property has something to cover.
    all_paths = list(files)
    changed = draw(
        st.lists(st.sampled_from(all_paths), min_size=1, max_size=len(all_paths), unique=True)
    )
    return {"files": files, "changed": changed}


def _render_source(spec: dict[str, Any]) -> str:
    """Render a ``.py`` module defining the spec's top-level functions/classes."""

    lines: list[str] = []
    for fn in spec["functions"]:
        lines.append(f"def {fn}():")
        lines.append("    return None")
        lines.append("")
    for cls in spec["classes"]:
        lines.append(f"class {cls}:")
        lines.append("    pass")
        lines.append("")
    return "\n".join(lines) if lines else "# empty module\n"


# Feature: security-pipeline, Property 2: For any Git_Diff over parseable files, every changed path appears in Changed_Feature.files, and every changed function/class definition appears in Changed_Feature.functions/classes.
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(repo=synthetic_repos())
def test_property_02_change_coverage(repo: dict[str, Any]) -> None:
    workspace = tempfile.mkdtemp(prefix="sec_prop02_")
    try:
        # Materialize the synthetic repo on disk.
        for rel_path, spec in repo["files"].items():
            full_path = os.path.join(workspace, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(_render_source(spec))

        # Index the workspace, then retrieve context for the changed files.
        RepositoryIndexer(workspace).index_repository()

        changed_files = repo["changed"]
        # A structured diff that names the same changed paths (added).
        structured_diff = {
            "added": [{"path": p} for p in changed_files],
            "modified": [],
        }
        context = ContextRetrievalEngine(workspace).retrieve(
            changed_files, structured_diff
        )

        changed_feature = context.changed_feature
        assert changed_feature is not None, "retrieve must populate changed_feature"

        # (a) Every changed path appears in Changed_Feature.files.
        for path in changed_files:
            assert path in changed_feature.files, (
                f"changed path {path!r} missing from Changed_Feature.files"
            )

        # (b) Every changed function/class defined in the changed files appears
        # in Changed_Feature.functions / classes (matched by symbol name).
        covered_function_names = {s.name for s in changed_feature.functions}
        covered_class_names = {s.name for s in changed_feature.classes}

        for path in changed_files:
            spec = repo["files"][path]
            for fn in spec["functions"]:
                assert fn in covered_function_names, (
                    f"changed function {fn!r} in {path!r} missing from "
                    f"Changed_Feature.functions"
                )
            for cls in spec["classes"]:
                assert cls in covered_class_names, (
                    f"changed class {cls!r} in {path!r} missing from "
                    f"Changed_Feature.classes"
                )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
