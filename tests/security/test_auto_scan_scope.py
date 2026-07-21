"""Tests for the 'auto' scan scope: first repo scan = full, then commit-scoped."""

from __future__ import annotations

import types

import pytest

from app.security.detection import runner as runner_mod
from app.security.detection.runner import derive_scan_scope, resolve_scope_mode
from app.security.state.repo_scan_state import JsonFileRepoScanState


class _Ctx:
    """Minimal stand-in for WorkflowContext for scope resolution."""

    def __init__(self, repository, changed_files=None):
        self.repository = repository
        self.changed_files = changed_files or []
        self.retrieved_knowledge = None
        self.tasks = []
        self.commit_sha = "deadbeef"
        self.security_scan_scope_mode = None


def _set_mode(monkeypatch, mode):
    from app.config import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "SECURITY_SCAN_SCOPE", mode, raising=False)


# --------------------------------------------------------------------------- #
# State store
# --------------------------------------------------------------------------- #
def test_state_first_scan_then_marked(tmp_path):
    state = JsonFileRepoScanState(str(tmp_path / "state" / "scanned.json"))
    assert state.is_first_scan("owner/repo") is True
    state.mark_scanned("owner/repo", "abc123")
    assert state.is_first_scan("owner/repo") is False
    # A different repo is still unseen.
    assert state.is_first_scan("owner/other") is True


def test_state_missing_file_is_first_scan(tmp_path):
    state = JsonFileRepoScanState(str(tmp_path / "does_not_exist.json"))
    assert state.is_first_scan("owner/repo") is True


# --------------------------------------------------------------------------- #
# Mode resolution
# --------------------------------------------------------------------------- #
def test_explicit_full_and_commit(monkeypatch):
    ctx = _Ctx("owner/repo")
    _set_mode(monkeypatch, "full")
    assert resolve_scope_mode(ctx) == "full"
    _set_mode(monkeypatch, "commit")
    assert resolve_scope_mode(ctx) == "commit"


def test_auto_first_scan_is_full_then_commit(monkeypatch, tmp_path):
    _set_mode(monkeypatch, "auto")
    state = JsonFileRepoScanState(str(tmp_path / "scanned.json"))
    monkeypatch.setattr(runner_mod, "resolve_scope_mode", runner_mod.resolve_scope_mode)
    # Point the default state at our tmp store.
    import app.security.state.repo_scan_state as st_mod
    monkeypatch.setattr(st_mod, "get_default_state", lambda: state)

    ctx = _Ctx("owner/repo")
    assert resolve_scope_mode(ctx) == "full"  # first sight → full

    state.mark_scanned("owner/repo", "abc")
    assert resolve_scope_mode(ctx) == "commit"  # subsequently → commit


def test_auto_full_scope_scans_whole_repo(monkeypatch, tmp_path):
    _set_mode(monkeypatch, "auto")
    state = JsonFileRepoScanState(str(tmp_path / "scanned.json"))
    import app.security.state.repo_scan_state as st_mod
    monkeypatch.setattr(st_mod, "get_default_state", lambda: state)

    ctx = _Ctx("owner/repo", changed_files=["a.py", "b.py"])
    scope = derive_scan_scope(ctx)
    assert scope.paths == (".",)  # whole-repo on first scan
    assert ctx.security_scan_scope_mode == "full"


def test_auto_after_onboard_is_commit_scoped(monkeypatch, tmp_path):
    _set_mode(monkeypatch, "auto")
    state = JsonFileRepoScanState(str(tmp_path / "scanned.json"))
    state.mark_scanned("owner/repo", "old")
    import app.security.state.repo_scan_state as st_mod
    monkeypatch.setattr(st_mod, "get_default_state", lambda: state)

    ctx = _Ctx("owner/repo", changed_files=["a.py", "b.py"])
    scope = derive_scan_scope(ctx)
    assert scope.paths == ("a.py", "b.py")  # commit-scoped
    assert ctx.security_scan_scope_mode == "commit"
