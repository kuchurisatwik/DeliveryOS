"""The extraction orchestrator: :class:`EndpointExtractor`.

The per-language extractors (:mod:`dast.endpoints.languages`) each recognise one
framework's Route_Declarations, and the pure leaf functions
(:func:`~dast.endpoints.normalize.normalize_route_path`,
:func:`~dast.endpoints.dedup.deduplicate`) turn raw declarations into a canonical,
deduplicated shape. This module is what walks a real repository on disk, hands each
file to the right extractors under strict safety and traversal bounds, and assembles
the result into one :class:`~dast.endpoints.models.ExtractionResult`.

**Static only.** The orchestrator *reads* files as text and passes that text to the
extractors; it never executes, imports, evaluates, or invokes any target code
(Req 1.5-1.8). It performs no network I/O (Req 1.2).

**Fails soft, once.** Every per-file problem — a file outside the root, an oversized
file, an unreadable/undecodable file, a file no extractor claims, or an extractor that
raises while parsing — degrades to *skipping that one file and continuing* (Req 1.4,
2.3, 9.7, 10.1). The single condition that has no inventory to return is a bad root: a
path that does not exist or is not a directory raises :class:`ExtractionError`
(Req 10.2). That is the only raising path.

**Deterministic.** Directory and file names are walked in sorted order, and the final
inventory is sorted by :func:`~dast.endpoints.dedup.deduplicate`, so two runs over an
unchanged repository return inventories with an identical set of endpoints (Req 1.9).

Requirements traced: 1.1, 1.2, 1.3, 1.4, 1.9, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5,
9.3, 9.4, 9.7, 10.1, 10.2, 10.3, 10.4, 11.1.
"""

from __future__ import annotations

import fnmatch
import os
from typing import Sequence

from dast.config import DastSettings, dast_settings
from dast.endpoints.base import LanguageExtractor, RawRoute
from dast.endpoints.dedup import deduplicate
from dast.endpoints.models import (
    SUPPORTED_METHODS,
    EndpointInventory,
    EndpointParameter,
    ExtractedEndpoint,
    ExtractionActivity,
    ExtractionError,
    ExtractionResult,
    ParameterKind,
)
from dast.endpoints.normalize import normalize_route_path
from dast.endpoints.registry import default_language_extractors

__all__ = ["EndpointExtractor"]


def _to_posix(path: str) -> str:
    """Return ``path`` with the OS separator rewritten to ``/``.

    Source_File locations are recorded as repository-relative POSIX-style paths so
    the inventory — and therefore dedup's ordering and the activity record — is
    identical whether the walk ran on Windows or POSIX (Req 1.9, 5.3).
    """
    return path.replace(os.sep, "/")


def _is_excluded(rel_path: str, patterns: Sequence[str]) -> bool:
    """Return ``True`` when a repo-relative path matches an Exclusion_Pattern.

    A pattern matches when it globs either the entry's basename (so a bare
    ``node_modules`` prunes that directory wherever it appears) or the full
    repo-relative path (so a ``/``-bearing pattern like ``src/gen`` can target a
    specific location). Matching is via :func:`fnmatch.fnmatch` (Req 9.3).
    """
    basename = rel_path.rsplit("/", 1)[-1]
    for pattern in patterns:
        if fnmatch.fnmatch(basename, pattern) or fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def _within_root(root_real: str, candidate_real: str) -> bool:
    """Return ``True`` when ``candidate_real`` lies inside ``root_real``.

    Both arguments are already fully resolved (symlinks and ``..`` collapsed). The
    comparison is case-normalised so it holds on case-insensitive filesystems, and
    a child must sit under ``root_real`` + separator so that a sibling directory
    sharing a name prefix is never mistaken for a descendant (Req 1.3, 1.4).
    """
    root_norm = os.path.normcase(root_real)
    candidate_norm = os.path.normcase(candidate_real)
    if candidate_norm == root_norm:
        return True
    return candidate_norm.startswith(root_norm + os.sep)


class EndpointExtractor:
    """Walk a repository and produce one inventory plus its evidence record.

    The extractor is constructed with the set of :class:`LanguageExtractor`\\ s to
    apply and the :class:`~dast.config.DastSettings` that bound traversal (the
    exclusion patterns and the maximum file size). Both default to the registered
    set and the process-wide ``dast_settings`` so ``EndpointExtractor().extract(root)``
    works out of the box, while tests can inject a bespoke registry or settings.
    """

    def __init__(
        self,
        extractors: Sequence[LanguageExtractor] | None = None,
        *,
        settings: DastSettings = dast_settings,
    ) -> None:
        # Resolve the default registry lazily so each extractor instance gets a
        # fresh list, mirroring how the DAST runner resolves default_adapters.
        self._extractors: tuple[LanguageExtractor, ...] = tuple(
            default_language_extractors() if extractors is None else extractors
        )
        self._settings = settings

    def extract(self, repo_root: str) -> ExtractionResult:
        """Walk ``repo_root`` and return its inventory and Extraction_Activity.

        Raises :class:`ExtractionError` only when ``repo_root`` does not exist or is
        not a directory (Req 10.2). Every other failure degrades to skipping the
        offending file and continuing (Req 1.4, 2.3, 9.7, 10.1). No network I/O is
        performed (Req 1.2), and two runs over an unchanged repository return
        inventories with an identical set of endpoints (Req 1.9).
        """
        # --- Step 1: root check (Req 10.2) -------------------------------------
        # Resolve first so a symlinked root is honoured, then insist it is a real
        # directory. A missing path or a file-as-root has no inventory to return.
        root_real = os.path.realpath(repo_root)
        if not os.path.isdir(root_real):
            raise ExtractionError(
                f"Target_Repository root path is not an existing directory: {repo_root!r}"
            )

        patterns = self._settings.dast_extract_exclude_patterns
        max_bytes = self._settings.DAST_EXTRACT_MAX_FILE_BYTES

        endpoints: list[ExtractedEndpoint] = []
        files_read = 0
        languages: set[str] = set()

        # --- Step 2: bounded traversal (Req 9.3, 9.4) --------------------------
        # os.walk with followlinks=False never descends symlinked directories, and
        # in-place dirnames[:] pruning removes an excluded directory's entire
        # subtree before it is ever entered. Sorting both lists makes the walk
        # order deterministic (Req 1.9).
        for dirpath, dirnames, filenames in os.walk(root_real, followlinks=False):
            rel_dir = _to_posix(os.path.relpath(dirpath, root_real))

            kept_dirs: list[str] = []
            for name in sorted(dirnames):
                rel_child = name if rel_dir == "." else f"{rel_dir}/{name}"
                if not _is_excluded(rel_child, patterns):
                    kept_dirs.append(name)
            dirnames[:] = kept_dirs

            for name in sorted(filenames):
                rel_file = name if rel_dir == "." else f"{rel_dir}/{name}"
                # Excluded files are skipped just like excluded directories (Req 9.3).
                if _is_excluded(rel_file, patterns):
                    continue

                abs_path = os.path.join(dirpath, name)

                # --- Step 3: path confinement (Req 1.3, 1.4) ------------------
                # Resolve symlinks and relative segments; a file whose real path
                # escapes the root is skipped without raising.
                if not _within_root(root_real, os.path.realpath(abs_path)):
                    continue

                # --- Step 5 (dispatch selection, Req 2.2-2.4) -----------------
                # Collect every extractor that claims the file by path alone. No
                # match means skip with no error (Req 2.3).
                matching = [ex for ex in self._extractors if ex.matches(abs_path)]
                if not matching:
                    continue

                # --- Step 4: size bound (Req 9.7) -----------------------------
                # Check size before reading; a file strictly larger than the
                # configured maximum is skipped unread.
                try:
                    if os.path.getsize(abs_path) > max_bytes:
                        continue
                except OSError:
                    continue

                # --- Step 6: read/parse resilience (Req 10.1) -----------------
                try:
                    with open(abs_path, "r", encoding="utf-8") as handle:
                        source_text = handle.read()
                except (OSError, UnicodeDecodeError):
                    continue

                try:
                    discovered: list[tuple[str, RawRoute]] = []
                    for extractor in matching:
                        for raw in extractor.discover(
                            source_text, source_path=abs_path
                        ):
                            discovered.append((extractor.language, raw))
                except Exception:
                    # Any extractor failure skips this one file and continues the
                    # walk (Req 10.1); the rest of the repository is unaffected.
                    continue

                # The file was successfully read and dispatched (Req 11.1).
                files_read += 1

                # --- Step 7: route -> endpoints (Req 3) -----------------------
                for language, raw in discovered:
                    produced = self._endpoints_for_route(raw, rel_file)
                    if produced:
                        endpoints.extend(produced)
                        # A language counts once it yields >= 1 recorded endpoint.
                        languages.add(language)

        # --- Step 8: dedup (Req 5) ----------------------------------------------
        inventory = EndpointInventory(endpoints=deduplicate(endpoints))

        # --- Step 9: activity (Req 11.1) ----------------------------------------
        activity = ExtractionActivity(
            files_read=files_read,
            endpoints_found=len(inventory.endpoints),
            languages=frozenset(languages),
        )
        return ExtractionResult(inventory=inventory, activity=activity)

    @staticmethod
    def _endpoints_for_route(
        raw: RawRoute, source_file: str
    ) -> list[ExtractedEndpoint]:
        """Expand one :class:`RawRoute` into its :class:`ExtractedEndpoint`\\ s.

        Normalises the path to the shared ``{id}`` template and derives the
        path-kind parameters from the declared segment names (Req 3.4, 4). Query
        parameters the extractor read become query-kind parameters. One endpoint is
        produced per method: an empty ``methods`` tuple defaults to ``GET`` (Req 3.3),
        and any verb outside :data:`SUPPORTED_METHODS` is dropped without suppressing
        the declaration's supported verbs (Req 3.5).
        """
        path_template, param_names = normalize_route_path(raw.raw_path)

        parameters = {
            EndpointParameter(name=name, kind=ParameterKind.PATH)
            for name in param_names
        }
        parameters.update(
            EndpointParameter(name=name, kind=ParameterKind.QUERY)
            for name in raw.query_parameters
        )
        frozen_parameters = frozenset(parameters)

        # No explicit method -> exactly one GET endpoint (Req 3.3). Otherwise
        # uppercase each declared verb and keep only the supported ones (Req 3.5).
        if raw.methods:
            methods = [
                method
                for method in (verb.upper() for verb in raw.methods)
                if method in SUPPORTED_METHODS
            ]
        else:
            methods = ["GET"]

        return [
            ExtractedEndpoint(
                method=method,
                path=path_template,
                parameters=frozen_parameters,
                source_file=source_file,
                source_line=raw.line,
            )
            for method in methods
        ]
