"""Property 3: Unparseable-file handling (security-pipeline).

Drives the extended Layer 1 ``RepositoryIndexer`` (task 2.1) against a synthetic
repository written into a temp directory. Each file is either valid Python (with
a known top-level symbol) or intentionally malformed (a syntax error). Hypothesis
chooses which arbitrary subset is malformed, covering the empty-subset (all
parseable) and all-malformed edge cases.

After indexing, the persisted SQLite state is queried directly (via
``RepositoryDB.get_connection``) to assert:

- the set of files recorded with ``unparseable = 1`` equals exactly the generated
  malformed subset, and
- every remaining (parseable) file is still analyzed: present with
  ``unparseable = 0`` and with its known symbol(s) indexed in ``symbols``.

Validates: Requirements 2.6
"""

from __future__ import annotations

import ast
import os
import shutil
import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.repository.indexer import RepositoryIndexer


def _valid_source(index: int) -> tuple[str, str]:
    """Valid Python source with a single known top-level symbol.

    Returns (source, symbol_name).
    """

    symbol = f"known_symbol_{index}"
    source = f"def {symbol}():\n    return {index}\n"
    return source, symbol


def _malformed_source(index: int) -> str:
    """Source that cannot be parsed into an AST (guaranteed SyntaxError)."""

    return f"def broken_symbol_{index}(:\n    return\n"


# Sanity: confirm our fixtures behave as intended so the property is meaningful.
def test_fixtures_parse_as_expected() -> None:
    src, _ = _valid_source(0)
    ast.parse(src)  # must not raise

    malformed = _malformed_source(0)
    try:
        ast.parse(malformed)
    except SyntaxError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("malformed fixture unexpectedly parsed cleanly")


# Feature: security-pipeline, Property 3: For any set of changed files containing an arbitrary subset that cannot be parsed into an AST, the recorded unparseable set equals exactly that unparseable subset and every remaining (parseable) file is still analyzed.
@settings(max_examples=100, deadline=None)
@given(malformed_flags=st.lists(st.booleans(), min_size=1, max_size=6))
def test_property_03_unparseable_file_handling(malformed_flags: list[bool]) -> None:
    workspace = tempfile.mkdtemp(prefix="secpipe_prop03_")
    try:
        expected_unparseable: set[str] = set()
        expected_parseable_symbols: dict[str, str] = {}

        # Materialize the synthetic repo: one .py file per flag.
        for i, is_malformed in enumerate(malformed_flags):
            rel_path = f"mod_{i}.py"
            full_path = os.path.join(workspace, rel_path)
            if is_malformed:
                content = _malformed_source(i)
                expected_unparseable.add(rel_path)
            else:
                content, symbol = _valid_source(i)
                expected_parseable_symbols[rel_path] = symbol
            with open(full_path, "w", encoding="utf-8") as fh:
                fh.write(content)

        indexer = RepositoryIndexer(workspace)
        indexer.index_repository()

        # Read back the persisted state.
        with indexer.db.get_connection() as conn:
            file_rows = conn.execute(
                "SELECT id, path, unparseable FROM files"
            ).fetchall()
            recorded = {row["path"]: row for row in file_rows}

            symbol_counts: dict[int, int] = {}
            symbol_names: dict[int, set[str]] = {}
            for row in conn.execute(
                "SELECT file_id, name FROM symbols"
            ).fetchall():
                symbol_counts[row["file_id"]] = symbol_counts.get(row["file_id"], 0) + 1
                symbol_names.setdefault(row["file_id"], set()).add(row["name"])

        # 1) The recorded unparseable set equals exactly the malformed subset.
        recorded_unparseable = {
            path for path, row in recorded.items() if row["unparseable"] == 1
        }
        assert recorded_unparseable == expected_unparseable, (
            f"recorded unparseable {recorded_unparseable} != "
            f"expected {expected_unparseable}"
        )

        # 2) Every parseable file is still analyzed: present, marked parseable,
        #    and its known symbol was indexed.
        for rel_path, symbol in expected_parseable_symbols.items():
            assert rel_path in recorded, f"parseable file {rel_path} was not recorded"
            row = recorded[rel_path]
            assert row["unparseable"] == 0, (
                f"parseable file {rel_path} was wrongly marked unparseable"
            )
            file_id = row["id"]
            assert symbol_counts.get(file_id, 0) >= 1, (
                f"no symbols indexed for parseable file {rel_path}"
            )
            assert symbol in symbol_names.get(file_id, set()), (
                f"known symbol {symbol} missing for {rel_path}"
            )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
