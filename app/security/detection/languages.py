"""Language detection for multi-language security scanning.

The SAST scanners (Semgrep, CodeQL) are the only language-coupled tools in the
pipeline — Gitleaks/Checkov/Trivy are language-agnostic, and Bandit is Python by
design. This module is the single, **pure** place that decides *which programming
languages a scan scope contains*, so the language-aware adapters can self-configure
their rule packs / query suites instead of being pinned to Python.

Detection is intentionally simple and dependency-free: it maps file extensions
(and a scoped directory walk for full-repo audits) to canonical language names.
Everything here is import-safe and side-effect free apart from the bounded,
read-only directory walk in :func:`detect_languages`.

Design goals:

* **Non-breaking.** When nothing is detected (empty scope, unknown extensions),
  helpers fall back to the pre-existing Python-centric defaults, so the pipeline
  behaves exactly as before on Python-only repositories.
* **Fail-open.** The walk skips vendored/build directories and is bounded, so a
  huge tree never stalls detection.
"""

from __future__ import annotations

import os
from typing import Iterable

# --------------------------------------------------------------------------- #
# Canonical language names keyed by file extension (lower-case, incl. dot).
# --------------------------------------------------------------------------- #
_EXT_LANG: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".sh": "bash",
    ".bash": "bash",
    ".rs": "rust",
    ".scala": "scala",
    ".swift": "swift",
}

#: Directories skipped during a full-repo walk — vendored deps, build output, and
#: VCS/tooling metadata never contain first-party source worth language-detecting.
_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "venv",
        ".venv",
        "env",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".hypothesis",
        "dist",
        "build",
        "target",
        "vendor",
        ".idea",
        ".vscode",
        ".gradle",
        ".deliveryos",
    }
)

#: Upper bound on files inspected during a walk so detection stays fast on very
#: large repositories (we only need to observe *which* languages are present).
_WALK_FILE_CAP = 50_000


# --------------------------------------------------------------------------- #
# Semgrep: canonical language -> registry rule pack.
# `p/security-audit` is always added separately (broad, multi-language); these
# add language-focused depth. Only well-known registry packs are listed so a
# bad `--config` can never break the Semgrep run.
# --------------------------------------------------------------------------- #
_SEMGREP_PACKS: dict[str, str] = {
    "python": "p/python",
    "javascript": "p/javascript",
    "typescript": "p/typescript",
    "java": "p/java",
    "kotlin": "p/kotlin",
    "go": "p/golang",
    "ruby": "p/ruby",
    "php": "p/php",
    "csharp": "p/csharp",
    "bash": "p/bash",
}

#: Semgrep configs used when no language is detected (preserves prior behavior).
DEFAULT_SEMGREP_CONFIGS: tuple[str, ...] = ("p/security-audit", "p/python")


# --------------------------------------------------------------------------- #
# CodeQL: canonical language -> codeql language id.
# Note CodeQL folds some languages together: TypeScript is analysed by the
# `javascript` extractor, Kotlin by `java`, and C by `cpp`.
# --------------------------------------------------------------------------- #
_CODEQL_LANG_ID: dict[str, str] = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "javascript",
    "java": "java",
    "kotlin": "java",
    "csharp": "csharp",
    "go": "go",
    "c": "cpp",
    "cpp": "cpp",
    "ruby": "ruby",
    "swift": "swift",
}

#: CodeQL language ids that require a build during database creation. These are
#: the highest-risk (autobuild can fail); callers isolate per-language failures.
CODEQL_COMPILED_LANGUAGES: frozenset[str] = frozenset({"java", "csharp", "cpp", "go"})


def language_for_file(path: str) -> str | None:
    """Return the canonical language for a file path, or ``None`` if unknown."""
    _, ext = os.path.splitext(path)
    return _EXT_LANG.get(ext.lower())


def detect_languages(paths: Iterable[str], cwd: str | None = None) -> frozenset[str]:
    """Detect the set of programming languages present in ``paths`` (pure-ish).

    ``paths`` are the scan-scope paths (relative to ``cwd`` when given). A path
    that is a directory — or the ``"."`` whole-repo sentinel — triggers a bounded,
    read-only walk that skips vendored/build directories. Individual files are
    mapped by extension. Unknown extensions are ignored.

    Returns a (possibly empty) frozenset of canonical language names. Emptiness is
    meaningful: callers fall back to their language-agnostic defaults.
    """
    found: set[str] = set()
    files_seen = 0

    def _resolve(p: str) -> str:
        return os.path.join(cwd, p) if cwd and not os.path.isabs(p) else p

    for raw in paths or ():
        if raw is None:
            continue
        abs_path = _resolve(raw)

        # A concrete file: map by extension directly (no filesystem access needed
        # when the extension is recognisable).
        if not (raw == "." or os.path.isdir(abs_path)):
            lang = language_for_file(raw)
            if lang:
                found.add(lang)
            continue

        # A directory (or the whole-repo '.'): walk it, bounded and read-only.
        for root, dirs, files in os.walk(abs_path):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for fname in files:
                files_seen += 1
                if files_seen > _WALK_FILE_CAP:
                    return frozenset(found)
                lang = language_for_file(fname)
                if lang:
                    found.add(lang)

    return frozenset(found)


def semgrep_configs_for(languages: Iterable[str]) -> tuple[str, ...]:
    """Return Semgrep ``--config`` packs for the detected ``languages``.

    Always includes the broad multi-language ``p/security-audit`` pack, then adds
    a language-focused pack for each detected language that has one. When nothing
    is detected, returns :data:`DEFAULT_SEMGREP_CONFIGS` so behavior is unchanged
    on Python-only / unknown scopes.
    """
    langs = {l for l in (languages or ()) if l}
    if not langs:
        return DEFAULT_SEMGREP_CONFIGS

    configs: list[str] = ["p/security-audit"]
    for lang in sorted(langs):
        pack = _SEMGREP_PACKS.get(lang)
        if pack and pack not in configs:
            configs.append(pack)
    return tuple(configs)


def codeql_suite_for(language_id: str) -> str:
    """Return the CodeQL query-suite spec for a CodeQL ``language_id``.

    Uses the **security-extended** well-known suite shipped inside each language's
    query pack, which adds precision-adjusted security queries (more injection /
    taint-flow coverage) on top of the default suite. Falls back gracefully at
    runtime: if the suite cannot be resolved, the per-language analysis fails in
    isolation and the other languages still run.
    """
    return f"codeql/{language_id}-queries:codeql-suites/{language_id}-security-extended.qls"


def codeql_targets_for(languages: Iterable[str]) -> tuple[tuple[str, str], ...]:
    """Map detected ``languages`` to unique CodeQL ``(language_id, query_suite)``.

    Deduplicates on the CodeQL language id (e.g. Python + JavaScript + TypeScript
    collapse TS into the ``javascript`` extractor). Returns an ordered tuple for
    deterministic execution. Empty when no CodeQL-supported language is present.
    """
    targets: list[tuple[str, str]] = []
    seen: set[str] = set()
    for lang in sorted({l for l in (languages or ()) if l}):
        lid = _CODEQL_LANG_ID.get(lang)
        if lid and lid not in seen:
            seen.add(lid)
            targets.append((lid, codeql_suite_for(lid)))
    return tuple(targets)


# --------------------------------------------------------------------------- #
# Settings-aware helpers (NOT pure — read global settings). Kept separate from
# the pure detection/mapping functions above so those stay property-testable.
# --------------------------------------------------------------------------- #
def configured_language_override() -> frozenset[str] | None:
    """Return an explicit language allow-list from ``SECURITY_LANGUAGES``.

    Returns ``None`` when the setting is ``'auto'`` (the default) or unreadable, in
    which case callers detect languages from the scope instead.
    """
    try:
        from app.config.settings import settings

        raw = (getattr(settings, "SECURITY_LANGUAGES", "auto") or "auto").strip()
    except Exception:  # noqa: BLE001 - settings must never break scanning
        return None
    if not raw or raw.lower() == "auto":
        return None
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())


def codeql_compiled_enabled() -> bool:
    """Whether CodeQL should analyse compiled languages (``SECURITY_CODEQL_COMPILED``)."""
    try:
        from app.config.settings import settings

        return bool(getattr(settings, "SECURITY_CODEQL_COMPILED", False))
    except Exception:  # noqa: BLE001 - settings must never break scanning
        return False


def effective_languages(paths: Iterable[str], cwd: str | None = None) -> frozenset[str]:
    """Languages to scan: the ``SECURITY_LANGUAGES`` override, else scope detection."""
    override = configured_language_override()
    if override is not None:
        return override
    return detect_languages(paths, cwd=cwd)
