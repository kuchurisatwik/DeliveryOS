"""Layer 2 Detection — the parallel scanner runner Stage.

:class:`DetectionStage` is the net-new Layer 2 workflow stage (subclassing the
existing :class:`app.workflows.stages.Stage`). It:

* derives **one** :class:`ScanScope` from the extended repository context (the
  Changed_Feature's paths plus related symbols) and shares that *same* scope with
  every scanner adapter (Requirement 3.2);
* runs the six :class:`~app.security.protocols.ScannerAdapter` instances
  **concurrently** with :mod:`concurrent.futures` (Requirement 3.1) and, once all
  complete, aggregates every :class:`Finding` as a **multiset union** of the
  per-scanner lists (Requirement 3.3);
* **isolates per-scanner failures** — a :class:`ScannerError`, unexpected
  exception, or timeout from any adapter is caught, recorded as a
  :class:`ScannerCoverage` entry with ``status = "incomplete"`` and a ``reason``,
  and the other scanners' findings are retained; completed scanners get
  ``status = "complete"`` (Requirement 3.4, design "Fail-open on scanner errors");
* preserves each :class:`Finding`'s provenance (scanner/location/severity are set
  by the adapters and never mutated here) (Requirement 3.5);
* produces a :class:`DetectionResult` and writes it onto the shared
  :class:`WorkflowContext` (``context.detection_result``).

The set of adapters is injectable via the constructor so tests can supply
in-memory fakes; when omitted, the six real adapters are constructed at execution
time (scoped to the cloned ``workspace``).
"""

from __future__ import annotations

import concurrent.futures
from typing import Any, Iterable, Optional, Sequence

from app.security.detection.adapters import (
    BanditAdapter,
    CheckovAdapter,
    CodeQLAdapter,
    GitleaksAdapter,
    ScannerError,
    SemgrepAdapter,
    TrivyAdapter,
)
from app.security.models import (
    DetectionResult,
    Finding,
    ScannerCoverage,
    ScanScope,
)
from app.security.protocols import ScannerAdapter
from app.workflows.context import WorkflowContext
from app.workflows.stages import Stage
from app.utils.logger import logger


def _dedup_preserving_order(items: Iterable[str]) -> list[str]:
    """Return ``items`` with duplicates removed, keeping first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item is not None and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def derive_scan_scope(context: WorkflowContext) -> ScanScope:
    """Derive a single :class:`ScanScope` covering the WHOLE commit (Requirement 3.2).

    Security detection must scan the *union of every file changed by the commit* —
    the opposite of the test pipeline's per-feature narrowing. The commit's changed
    files are therefore the source of truth for the scanned ``paths``:

    * every path in ``context.changed_files`` (the full commit), plus
    * every file belonging to each planned ``EngineeringTask`` (``related_files``),
      so the scope is correct even when the task decomposition names files the raw
      changed-file list somehow missed.

    The per-task ``context.retrieved_knowledge`` (which is overwritten each loop
    iteration and, after the loop, holds only the *last* task's context) is used
    **only additively**: its Changed_Feature files and graph-related symbols enrich
    the scope, but they can never narrow it. This prevents the previous gap where a
    multi-feature commit was scanned against only the last processed feature's
    files, silently under-scoping detection.

    Shared by the Layer 2 :class:`DetectionStage` and the Layer 3 verification
    re-run so both scan the *same* derived scope.
    """
    repo_ctx: Any = context.retrieved_knowledge
    paths: list[str] = []
    related: list[str] = []

    # 1. Whole-commit file set is the source of truth (never narrowed).
    paths.extend(context.changed_files or [])

    # 2. Union in every planned task's files, in case decomposition surfaced paths
    #    not present in the raw changed-file list.
    for task in getattr(context, "tasks", None) or []:
        paths.extend(getattr(task, "related_files", None) or [])

    # 3. Additively fold in the Changed_Feature files / related symbols from the
    #    (last) retrieved context — enrichment only, this can only ADD paths.
    changed_feature = getattr(repo_ctx, "changed_feature", None) if repo_ctx else None
    if changed_feature is not None:
        paths.extend(getattr(changed_feature, "files", None) or [])
        for sym in getattr(changed_feature, "related_symbols", None) or []:
            name = getattr(sym, "name", None)
            if name:
                related.append(name)

    # 4. Fold in any top-level related symbols carried on the repo context.
    if repo_ctx is not None:
        for sym in getattr(repo_ctx, "related_symbols", None) or []:
            name = getattr(sym, "name", None)
            if name:
                related.append(name)

    return ScanScope(
        paths=tuple(_dedup_preserving_order(paths)),
        related_symbols=tuple(_dedup_preserving_order(related)),
    )


class DetectionStage(Stage):
    """Runs the six scanner adapters in parallel over one shared ScanScope."""

    def __init__(
        self,
        adapters: Optional[Sequence[ScannerAdapter]] = None,
        *,
        max_workers: Optional[int] = None,
        adapter_timeout: Optional[float] = None,
    ) -> None:
        """Create the stage.

        Args:
            adapters: Explicit scanner adapters (used by tests to inject fakes).
                When ``None`` the six real adapters are constructed at execution
                time, scoped to the cloned ``workspace``.
            max_workers: Thread-pool size; defaults to the number of adapters.
            adapter_timeout: Optional wall-clock timeout (seconds) applied while
                awaiting each adapter's result. A timeout is isolated exactly like
                any other per-scanner failure. ``None`` (default) waits for the
                adapter's own internal timeout to surface as a ``ScannerError``.
        """
        self._adapters: Optional[list[ScannerAdapter]] = (
            list(adapters) if adapters is not None else None
        )
        self._max_workers = max_workers
        self._adapter_timeout = adapter_timeout

    # ------------------------------------------------------------------ #
    # Stage entry point
    # ------------------------------------------------------------------ #

    def execute(self, context: WorkflowContext) -> None:
        adapters = (
            self._adapters
            if self._adapters is not None
            else self._default_adapters(context)
        )
        scope = self._derive_scope(context)
        logger.info(
            "DetectionStage: scanning %d path(s) with %d scanner(s)",
            len(scope.paths),
            len(adapters),
        )
        context.detection_result = self._run(adapters, scope)

    def run_on_scope(
        self, scope: ScanScope, context: Optional[WorkflowContext] = None
    ) -> DetectionResult:
        """Run the configured adapters over an explicit ``scope``.

        Public entry point for callers (e.g. the Layer 3 verification re-run) that
        already hold a derived :class:`ScanScope` and want the same parallel
        execution + aggregation + per-scanner failure isolation as
        :meth:`execute`, without deriving the scope from a context. When adapters
        were not injected at construction time the six real adapters are built from
        ``context`` (whose ``workspace`` scopes them); injected adapters need no
        context.
        """
        adapters = (
            self._adapters
            if self._adapters is not None
            else self._default_adapters(context)
        )
        return self._run(adapters, scope)

    # ------------------------------------------------------------------ #
    # Adapter construction
    # ------------------------------------------------------------------ #

    @staticmethod
    def _default_adapters(context: WorkflowContext) -> list[ScannerAdapter]:
        """Construct the six real scanner adapters scoped to the workspace."""
        cwd = context.workspace
        return [
            BanditAdapter(cwd=cwd),
            SemgrepAdapter(cwd=cwd),
            CodeQLAdapter(cwd=cwd),
            GitleaksAdapter(cwd=cwd),
            CheckovAdapter(cwd=cwd),
            TrivyAdapter(cwd=cwd),
        ]

    # ------------------------------------------------------------------ #
    # Scope derivation (Requirement 3.2)
    # ------------------------------------------------------------------ #

    def _derive_scope(self, context: WorkflowContext) -> ScanScope:
        """Derive a single ScanScope from the repository context.

        Delegates to the shared :func:`derive_scan_scope` so Layer 2 detection and
        Layer 3 verification scope identically (Requirement 3.2).
        """
        return derive_scan_scope(context)

    # ------------------------------------------------------------------ #
    # Parallel execution + aggregation (Requirements 3.1, 3.3, 3.4, 3.5)
    # ------------------------------------------------------------------ #

    def _run(self, adapters: Sequence[ScannerAdapter], scope: ScanScope) -> DetectionResult:
        """Run every adapter concurrently and aggregate findings + coverage.

        Each adapter receives the *same* ``scope`` instance (Requirement 3.2).
        Results are collected as futures complete, then aggregated in adapter
        order for deterministic output; the aggregated findings are the multiset
        union of the per-scanner lists (Requirement 3.3). A failing scanner yields
        one ``incomplete`` coverage entry while the others' findings are retained
        (Requirement 3.4).
        """
        if not adapters:
            return DetectionResult(findings=(), coverage=())

        # scanner name -> ("ok", findings) | ("error", reason)
        outcomes: dict[str, tuple[str, Any]] = {}
        max_workers = self._max_workers or max(1, len(adapters))

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_adapter = {
                executor.submit(adapter.scan, scope): adapter for adapter in adapters
            }
            for future in concurrent.futures.as_completed(future_to_adapter):
                adapter = future_to_adapter[future]
                try:
                    scanner_findings = future.result(timeout=self._adapter_timeout)
                    outcomes[adapter.name] = ("ok", list(scanner_findings))
                except ScannerError as exc:
                    logger.warning("Scanner '%s' failed: %s", adapter.name, exc.reason)
                    outcomes[adapter.name] = ("error", exc.reason)
                except concurrent.futures.TimeoutError:
                    logger.warning("Scanner '%s' timed out", adapter.name)
                    outcomes[adapter.name] = (
                        "error",
                        f"timed out after {self._adapter_timeout}s",
                    )
                except Exception as exc:  # noqa: BLE001 - fail-open per-scanner isolation
                    logger.warning(
                        "Scanner '%s' raised an unexpected error: %s", adapter.name, exc
                    )
                    outcomes[adapter.name] = ("error", f"unexpected error: {exc}")

        findings: list[Finding] = []
        coverage: list[ScannerCoverage] = []
        # Iterate adapters in their given order for deterministic aggregation.
        for adapter in adapters:
            status, payload = outcomes[adapter.name]
            if status == "ok":
                findings.extend(payload)
                coverage.append(
                    ScannerCoverage(scanner=adapter.name, status="complete")
                )
            else:
                coverage.append(
                    ScannerCoverage(
                        scanner=adapter.name, status="incomplete", reason=payload
                    )
                )

        return DetectionResult(findings=tuple(findings), coverage=tuple(coverage))
