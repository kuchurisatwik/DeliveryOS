"""Example tests for Layer 1 call/dependency graph construction (security-pipeline).

These are deterministic example tests (NOT property-based) exercised over a small,
hand-written fixture repository written into pytest's ``tmp_path``. They pin down
the exact nodes and edges the extended Repository Intelligence must produce:

  * the recursive AST indexer captures classes, methods, and nested functions
    (each with a dotted ``qualified_name``) in the ``symbols`` table;
  * the call graph (``calls`` table) records the expected caller -> callee edges;
  * the dependency graph (``dependencies`` table) records resolved ``import_path``;
  * the retriever resolves callers/callees/imports into ``related_symbols`` with the
    correct ``relation``, and produces sensible per-symbol reachability inputs.

Requirements: 2.2, 2.4, 2.5
"""

from __future__ import annotations

import pytest

from app.services.repository.db import RepositoryDB
from app.services.repository.indexer import RepositoryIndexer
from app.services.repository.retriever import ContextRetrievalEngine


# --------------------------------------------------------------------------- #
# Hand-written fixture modules (fixed, not generated).
# --------------------------------------------------------------------------- #

# A module with a class + methods + a nested function, plus module-level
# functions that call each other and call imported names.
SERVICE_PY = '''\
import os
from helpers import sanitize


class Processor:
    def process(self, data):
        cleaned = sanitize(data)
        return self.finalize(cleaned)

    def finalize(self, value):
        def inner_normalize(x):
            return os.path.basename(x)

        return inner_normalize(value)


def run(payload):
    p = Processor()
    return p.process(payload)


def main():
    run("input")
'''

# A second module providing a symbol that ``service.py`` imports and calls, so
# that callee resolution across files can be asserted.
HELPERS_PY = '''\
def sanitize(data):
    return data.strip()
'''


@pytest.fixture
def indexed_repo(tmp_path):
    """Write the fixture repo into tmp_path and run the extended indexer."""
    (tmp_path / "service.py").write_text(SERVICE_PY, encoding="utf-8")
    (tmp_path / "helpers.py").write_text(HELPERS_PY, encoding="utf-8")

    indexer = RepositoryIndexer(str(tmp_path))
    indexer.index_repository()
    return tmp_path


def _connect(workspace):
    return RepositoryDB(str(workspace)).get_connection()


# --------------------------------------------------------------------------- #
# Indexer: symbols (classes, methods, nested defs) with qualified names
# --------------------------------------------------------------------------- #

def test_indexer_captures_methods_and_nested_symbols(indexed_repo):
    with _connect(indexed_repo) as conn:
        rows = conn.execute(
            """
            SELECT s.name, s.type, s.qualified_name
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            WHERE f.path = 'service.py'
            """
        ).fetchall()

    got = {(r["name"], r["type"], r["qualified_name"]) for r in rows}
    expected = {
        ("Processor", "class", "Processor"),
        ("Processor.process", "method", "Processor.process"),
        ("Processor.finalize", "method", "Processor.finalize"),
        (
            "Processor.finalize.inner_normalize",
            "function",
            "Processor.finalize.inner_normalize",
        ),
        ("run", "function", "run"),
        ("main", "function", "main"),
    }
    assert got == expected


# --------------------------------------------------------------------------- #
# Indexer: call graph edges (caller -> callee)
# --------------------------------------------------------------------------- #

def test_indexer_builds_expected_call_graph_edges(indexed_repo):
    with _connect(indexed_repo) as conn:
        rows = conn.execute(
            """
            SELECT s.qualified_name AS caller, c.callee_name AS callee
            FROM calls c
            JOIN symbols s ON c.caller_symbol_id = s.id
            JOIN files f ON c.file_id = f.id
            WHERE f.path = 'service.py'
            """
        ).fetchall()

    edges = {(r["caller"], r["callee"]) for r in rows}
    expected = {
        ("Processor.process", "sanitize"),
        ("Processor.process", "self.finalize"),
        ("Processor.finalize", "inner_normalize"),
        ("Processor.finalize.inner_normalize", "os.path.basename"),
        ("run", "Processor"),
        ("run", "p.process"),
        ("main", "run"),
    }
    assert edges == expected


def test_indexer_records_no_module_level_calls_for_service(indexed_repo):
    # The fixture has no top-level (module-scope) calls, so every call edge must
    # be attributed to an enclosing symbol.
    with _connect(indexed_repo) as conn:
        n = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM calls c
            JOIN files f ON c.file_id = f.id
            WHERE f.path = 'service.py' AND c.caller_symbol_id IS NULL
            """
        ).fetchone()["n"]
    assert n == 0


# --------------------------------------------------------------------------- #
# Indexer: dependency graph with resolved import_path
# --------------------------------------------------------------------------- #

def test_indexer_records_resolved_import_paths(indexed_repo):
    with _connect(indexed_repo) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT d.target_symbol_name, d.import_path
            FROM dependencies d
            JOIN symbols s ON d.source_symbol_id = s.id
            JOIN files f ON s.file_id = f.id
            WHERE f.path = 'service.py'
            """
        ).fetchall()

    pairs = {(r["target_symbol_name"], r["import_path"]) for r in rows}
    assert ("os", "os") in pairs
    assert ("sanitize", "helpers.sanitize") in pairs
    # Every dependency edge carries a resolved (non-empty) import_path.
    assert all(r["import_path"] for r in rows)


# --------------------------------------------------------------------------- #
# Retriever: related-symbol resolution (callers / callees / imports)
# --------------------------------------------------------------------------- #

def test_retriever_resolves_related_symbols(indexed_repo):
    engine = ContextRetrievalEngine(str(indexed_repo))
    ctx = engine.retrieve(["service.py"])
    related = ctx.related_symbols

    # Imported modules surface with relation="imported" and a resolved import_path.
    imported = {(r.name, r.import_path) for r in related if r.relation == "imported"}
    assert ("os", "os") in imported
    assert ("sanitize", "helpers.sanitize") in imported

    # Callers are resolved from incoming call edges.
    callers = {r.name for r in related if r.relation == "caller"}
    assert {"run", "Processor.process", "Processor.finalize", "main"} <= callers

    # Callees that resolve to defined symbols carry the correct file_path.
    callee_pairs = {
        (r.name, r.file_path) for r in related if r.relation == "callee"
    }
    assert ("Processor", "service.py") in callee_pairs  # class resolved in-file
    assert ("run", "service.py") in callee_pairs         # function resolved in-file
    assert ("sanitize", "helpers.py") in callee_pairs    # resolved cross-file


def test_retriever_changed_feature_maps_symbols(indexed_repo):
    engine = ContextRetrievalEngine(str(indexed_repo))
    ctx = engine.retrieve(["service.py"])

    assert ctx.changed_feature is not None
    cf = ctx.changed_feature
    assert "service.py" in cf.files

    class_names = {c.name for c in cf.classes}
    func_names = {fn.name for fn in cf.functions}
    assert class_names == {"Processor"}
    # Functions + methods + nested defs all classified as function/method symbols.
    assert {
        "Processor.process",
        "Processor.finalize",
        "Processor.finalize.inner_normalize",
        "run",
        "main",
    } <= func_names


# --------------------------------------------------------------------------- #
# Retriever: reachability inputs derived from the call graph
# --------------------------------------------------------------------------- #

def test_retriever_computes_reachability_inputs(indexed_repo):
    engine = ContextRetrievalEngine(str(indexed_repo))
    ctx = engine.retrieve(["service.py"])
    by_name = {r.symbol_name: r for r in ctx.reachability}

    # main() is an entrypoint: nothing calls it, it calls run(), and it is
    # (trivially) reachable from an entrypoint (itself).
    main_r = by_name["main"]
    assert main_r.caller_count == 0
    assert main_r.callee_count == 1
    assert main_r.has_callers is False
    assert main_r.reachable_from_entrypoint is True

    # Processor.process is called (via p.process) and makes two calls.
    proc = by_name["Processor.process"]
    assert proc.caller_count == 1
    assert proc.callee_count == 2
    assert proc.has_callers is True
    assert proc.reachable_from_entrypoint is True

    # run() is called by main and calls Processor + p.process.
    run_r = by_name["run"]
    assert run_r.caller_count == 1
    assert run_r.callee_count == 2
    assert run_r.has_callers is True
    assert run_r.reachable_from_entrypoint is True
