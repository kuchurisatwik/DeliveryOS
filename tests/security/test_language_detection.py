"""Tests for multi-language detection and language-aware SAST configuration.

Covers the pure detection/mapping functions in
``app.security.detection.languages`` and the language-aware config selection in
the Semgrep and CodeQL adapters. No live scanner subprocess is spawned — the
adapters' ``scan()`` is not called here; we assert on the resolution logic that
picks rule packs / query suites from a scope.
"""

from __future__ import annotations

import os

import pytest

from app.security.detection import languages as lang
from app.security.detection.adapters.codeql_adapter import CodeQLAdapter
from app.security.detection.adapters.semgrep_adapter import SemgrepAdapter
from app.security.models import ScanScope


# --------------------------------------------------------------------------- #
# Pure detection
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "path,expected",
    [
        ("app/main.py", "python"),
        ("src/index.js", "javascript"),
        ("src/app.ts", "typescript"),
        ("Main.java", "java"),
        ("cmd/server.go", "go"),
        ("lib/foo.rb", "ruby"),
        ("index.php", "php"),
        ("Program.cs", "csharp"),
        ("kernel.cpp", "cpp"),
        ("deploy.sh", "bash"),
        ("README.md", None),
        ("noext", None),
    ],
)
def test_language_for_file(path, expected):
    assert lang.language_for_file(path) == expected


def test_detect_languages_from_file_list():
    paths = ("app/main.py", "web/app.ts", "web/app.js", "svc/main.go", "docs/readme.md")
    assert lang.detect_languages(paths) == frozenset(
        {"python", "typescript", "javascript", "go"}
    )


def test_detect_languages_empty_when_unknown():
    assert lang.detect_languages(("a.md", "b.txt", "LICENSE")) == frozenset()


def test_detect_languages_walks_directories(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "pkg" / "b.rb").write_text("x = 1\n", encoding="utf-8")
    # A skipped dir must not contribute.
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("var x=1\n", encoding="utf-8")

    detected = lang.detect_languages((".",), cwd=str(tmp_path))
    assert detected == frozenset({"python", "ruby"})


# --------------------------------------------------------------------------- #
# Semgrep config mapping
# --------------------------------------------------------------------------- #
def test_semgrep_configs_default_when_no_language():
    assert lang.semgrep_configs_for(frozenset()) == lang.DEFAULT_SEMGREP_CONFIGS


def test_semgrep_configs_include_security_audit_and_language_packs():
    configs = lang.semgrep_configs_for({"python", "javascript", "go"})
    assert configs[0] == "p/security-audit"
    assert "p/python" in configs
    assert "p/javascript" in configs
    assert "p/golang" in configs


def test_semgrep_adapter_auto_selects_from_scope(tmp_path):
    (tmp_path / "app.go").write_text("package main\n", encoding="utf-8")
    adapter = SemgrepAdapter(cwd=str(tmp_path))
    configs = adapter._resolve_configs(ScanScope(paths=("app.go",)))
    assert "p/golang" in configs
    assert "p/security-audit" in configs


def test_semgrep_adapter_explicit_config_disables_detection():
    adapter = SemgrepAdapter(config="p/ci")
    configs = adapter._resolve_configs(ScanScope(paths=("app.go",)))
    assert configs == ("p/ci",)


# --------------------------------------------------------------------------- #
# CodeQL target mapping
# --------------------------------------------------------------------------- #
def test_codeql_targets_dedup_javascript_typescript():
    targets = lang.codeql_targets_for({"javascript", "typescript"})
    # TypeScript collapses into the javascript extractor → a single target,
    # using the security-extended suite.
    assert targets == (("javascript", lang.codeql_suite_for("javascript")),)


def test_codeql_suite_is_security_extended():
    suite = lang.codeql_suite_for("python")
    assert "security-extended" in suite
    assert suite.startswith("codeql/python-queries")


def test_codeql_targets_empty_when_unsupported():
    assert lang.codeql_targets_for({"bash", "rust"}) == ()


def test_codeql_adapter_pinned_language_back_compat():
    # A pinned language analyses exactly that language, security-extended suite.
    adapter = CodeQLAdapter(language="python")
    targets = adapter._resolve_targets(ScanScope(paths=("a.py",)))
    assert targets == (("python", lang.codeql_suite_for("python")),)


def test_codeql_adapter_auto_detects_interpreted(tmp_path, monkeypatch):
    monkeypatch.setattr(lang, "codeql_compiled_enabled", lambda: False)
    monkeypatch.setattr(lang, "configured_language_override", lambda: None)
    (tmp_path / "app.rb").write_text("x = 1\n", encoding="utf-8")
    adapter = CodeQLAdapter(cwd=str(tmp_path))
    targets = adapter._resolve_targets(ScanScope(paths=("app.rb",)))
    assert ("ruby", lang.codeql_suite_for("ruby")) in targets


def test_codeql_adapter_drops_compiled_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(lang, "codeql_compiled_enabled", lambda: False)
    monkeypatch.setattr(lang, "configured_language_override", lambda: None)
    (tmp_path / "Main.java").write_text("class Main {}\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    adapter = CodeQLAdapter(cwd=str(tmp_path))
    targets = adapter._resolve_targets(ScanScope(paths=(".",)))
    ids = {t[0] for t in targets}
    assert "java" not in ids  # compiled dropped
    assert "python" in ids


def test_codeql_adapter_keeps_compiled_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(lang, "codeql_compiled_enabled", lambda: True)
    monkeypatch.setattr(lang, "configured_language_override", lambda: None)
    (tmp_path / "Main.java").write_text("class Main {}\n", encoding="utf-8")
    adapter = CodeQLAdapter(cwd=str(tmp_path))
    targets = adapter._resolve_targets(ScanScope(paths=(".",)))
    ids = {t[0] for t in targets}
    assert "java" in ids


def test_language_override_forces_languages(monkeypatch):
    monkeypatch.setattr(
        lang, "configured_language_override", lambda: frozenset({"go"})
    )
    # Detection is bypassed; the override wins regardless of the paths given.
    assert lang.effective_languages(("whatever.py",)) == frozenset({"go"})
