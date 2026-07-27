"""Tests for CodeQL per-commit DB cache path resolution + validity + pruning."""

from __future__ import annotations

import os

from app.security.detection.adapters.codeql_adapter import CodeQLAdapter, _is_valid_db


def _make_db(path: str) -> None:
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "codeql-database.yml"), "w", encoding="utf-8") as fh:
        fh.write("primaryLanguage: python\n")


def test_is_valid_db_requires_marker(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert _is_valid_db(str(empty)) is False
    _make_db(str(tmp_path / "db"))
    assert _is_valid_db(str(tmp_path / "db")) is True


def test_no_cache_uses_temp_and_never_hits(tmp_path):
    # No commit_sha/cache_dir → temp path, never a cache hit (original behavior).
    adapter = CodeQLAdapter(language="python")
    db_dir, cached = adapter._resolve_db_dir("python")
    assert cached is False
    assert "codeql-db-python" in db_dir


def test_cache_miss_then_hit(tmp_path):
    cache = str(tmp_path / "cache")
    adapter = CodeQLAdapter(commit_sha="a5415f36cadb", cache_dir=cache)
    db_dir, cached = adapter._resolve_db_dir("python")
    assert cached is False               # nothing cached yet
    assert "a5415f36cadb" in db_dir      # SHA-keyed path

    _make_db(db_dir)                     # simulate a completed build
    _, cached2 = adapter._resolve_db_dir("python")
    assert cached2 is True               # same SHA → cache hit


def test_prune_keeps_only_current_sha(tmp_path):
    cache = str(tmp_path / "cache")
    os.makedirs(cache, exist_ok=True)
    # An old DB for a different commit + the current one.
    old = os.path.join(cache, "codeql-db-python-oldsha000000")
    _make_db(old)
    adapter = CodeQLAdapter(commit_sha="newsha111111", cache_dir=cache)
    new_dir, _ = adapter._resolve_db_dir("python")
    _make_db(new_dir)

    adapter._prune_old_dbs("python", keep=new_dir)
    assert not os.path.exists(old)       # stale DB pruned
    assert os.path.exists(new_dir)       # current DB kept


def test_explicit_database_override_wins(tmp_path):
    adapter = CodeQLAdapter(database=str(tmp_path / "fixed-db"), commit_sha="x", cache_dir=str(tmp_path))
    db_dir, cached = adapter._resolve_db_dir("python")
    assert db_dir == str(tmp_path / "fixed-db")
    assert cached is False
