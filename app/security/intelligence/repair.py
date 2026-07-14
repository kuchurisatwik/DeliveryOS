"""Layer 3 AI Repair — propose candidate patches for findings (Requirement 10).

Like :mod:`app.security.intelligence.triage`, this module has two clearly
separated halves, following the design's "pure core, impure shell" principle:

* :class:`LLMRepairAdapter` — the **impure shell**. A concrete
  :class:`~app.security.protocols.AIRepairAdapter` implementation that follows the
  existing :class:`~app.agents.repair.agent.RepairAgent` pattern (a structured
  failure summary, previous-attempt history, and a full-file-aware rewrite) and
  reuses the shared :class:`~app.services.llm_service.LLMService`
  (``generate_structured_json`` + prompt-hash caching) to produce a
  :class:`~app.security.models.CandidatePatch` for a single
  :class:`~app.security.models.Normalized_Finding` (Requirement 10.1). It returns
  ``None`` when it cannot propose a safe patch (Requirement 10.4). The LLM call is
  fully isolated here.

* :func:`select_repairs` — the **pure core**. Given a set of findings and an
  injected repair adapter, it deterministically decides which findings are
  eligible for repair (scanner-confirmed and not labeled a likely false positive),
  requests a patch for exactly those (Requirement 10.1), associates each produced
  patch with the finding it targets via ``target_finding_id`` (Requirement 10.2),
  treats the patch as a proposal only — it never merges anything (Requirement 10.3),
  and marks a finding ``unresolved`` with a recorded ``unresolved_reason`` whenever
  no patch is produced (Requirement 10.4). Because :class:`Normalized_Finding` and
  :class:`CandidatePatch` are frozen, new instances are produced via
  :func:`dataclasses.replace`.

The adapter is injectable, so :func:`select_repairs` is deterministic with respect
to the adapter's outputs and can be property-tested (design Properties 13 & 14)
with an in-memory fake/mock adapter — no network required.

## What "scanner-confirmed" means here

A :class:`Normalized_Finding` records its originating scanners in the ``scanners``
set. Normalization only ever runs on findings emitted by a real scanner, so in
practice that set is non-empty. We therefore define **scanner-confirmed** as
"originated from at least one scanner", i.e. ``len(finding.scanners) > 0`` — this
distinguishes genuine scanner output from any synthetic/placeholder finding that
carries no scanner provenance. There is no separate ``synthetic`` flag on the
model, so this is the consistent, documented interpretation. A finding is
**repair-eligible** when it is scanner-confirmed AND not labeled a likely false
positive (Requirement 10.1); false-positive-labeled findings are retained for human
review but skipped for repair.
"""

from __future__ import annotations

import os
from dataclasses import replace
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.security.models import (
    CandidatePatch,
    FindingStatus,
    Normalized_Finding,
)
from app.services.llm_service import LLMService
from app.utils.logger import logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.security.protocols import AIRepairAdapter
    from app.schemas.repository import RepositoryContext as RepoContext


# Recorded reason when the adapter yields no patch (Requirement 10.4).
NO_PATCH_REASON = "AI_Repair produced no candidate patch for this finding."
REPAIR_ERROR_REASON = "AI_Repair failed to produce a candidate patch (adapter error)."


# ---------------------------------------------------------------------------
# LLM structured-output schema
# ---------------------------------------------------------------------------


class RepairResponseSchema(BaseModel):
    """Structured JSON the LLM must return for a single finding's repair.

    ``can_produce_patch`` lets the model decline safely (mapped onto ``None`` so the
    finding is marked ``unresolved``); ``diff`` carries the proposal-only unified
    diff when a patch is produced.
    """

    can_produce_patch: bool = Field(
        description="True only when a concrete, safe secure fix can be proposed for this finding."
    )
    diff: str = Field(
        default="",
        description="Unified (git-style) diff applying the secure fix. Empty when no patch.",
    )
    reason: str = Field(
        default="",
        description="Why no patch was produced (when declining), else a one-line fix summary.",
    )


# ---------------------------------------------------------------------------
# Impure shell — the concrete LLM-backed adapter
# ---------------------------------------------------------------------------


class LLMRepairAdapter:
    """Concrete :class:`AIRepairAdapter` backed by :class:`LLMService`.

    Mirrors the :class:`~app.agents.repair.agent.RepairAgent` structure: it builds a
    structured summary of the finding to repair, folds in any previous failed
    repair attempts, includes the affected source when available, and requests a
    full, precise rewrite as a unified diff. All side effects (prompt assembly +
    network call) are confined to :meth:`repair`; the returned
    :class:`CandidatePatch` (or ``None``) is a plain immutable value the pure core
    consumes.
    """

    def __init__(
        self,
        llm_service: LLMService | None = None,
        prompt_path: str | None = None,
    ) -> None:
        self.llm_service = llm_service or LLMService()
        self.prompt_template = ""
        path = prompt_path or os.path.join(
            os.getcwd(), "app", "prompts", "security_repair.md"
        )
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.prompt_template = f.read()

    def _build_prompt(self, f: Normalized_Finding, ctx: "RepoContext") -> str:
        """Assemble the repair prompt: structured finding summary + context + source."""
        lines: list[str] = [self.prompt_template]

        # Structured failure summary (mirrors RepairAgent._extract_failure_summary).
        lines.append("\n=== SECURITY FINDING TO REPAIR (STRUCTURED) ===")
        lines.append(f"Finding id: {f.finding_id}")
        lines.append(f"Rule identity: {f.rule_identity}")
        lines.append(f"Category: {f.category}")
        lines.append(f"Severity: {f.severity.name}")
        lines.append(f"Reported by scanners: {', '.join(sorted(f.scanners))}")
        loc = f.location
        symbol = f" (symbol: {loc.symbol})" if loc.symbol else ""
        lines.append(f"Location: {loc.path}:{loc.start_line}-{loc.end_line}{symbol}")
        lines.append(f"Message: {f.message}")
        if f.exposure is not None:
            lines.append(f"Exposure: {f.exposure.value}")
        if f.auth_context is not None:
            lines.append(f"Auth context: {f.auth_context.value}")
        if f.risk_score is not None:
            lines.append(f"Risk score: {f.risk_score}")

        # AI triage guidance, when present (suggested fix approach).
        if f.triage is not None:
            lines.append("\n=== AI TRIAGE GUIDANCE ===")
            lines.append(f"Priority: {f.triage.priority.name}")
            lines.append(f"Explanation: {f.triage.explanation}")
            lines.append(f"Suggested fix approach: {f.triage.suggested_fix}")

        lines.append("\n=== REPOSITORY CONTEXT ===")
        lines.append(self._format_context(ctx))

        # Affected source code (full-file-aware rewrite, mirroring RepairAgent).
        source = self._read_affected_source(f, ctx)
        if source:
            lines.append("\n=== AFFECTED SOURCE ===")
            lines.append(source)

        lines.append("\n=== REMINDER ===")
        lines.append(
            "Fix the root cause. Preserve behavior. The patch is a PROPOSAL ONLY and "
            "is never merged automatically. If you cannot safely fix it, set "
            "can_produce_patch=false and explain why. Return strictly valid JSON."
        )
        return "\n".join(lines)

    @staticmethod
    def _format_context(ctx: "RepoContext") -> str:
        """Render a concise, token-friendly view of the repository context."""
        if ctx is None:
            return "No repository context available."
        parts: list[str] = []
        target = getattr(ctx, "target_symbols", None) or []
        if target:
            parts.append("Directly changed symbols:")
            for s in target:
                parts.append(f"  - {s.type} {s.name} ({s.file_path})")
        related = getattr(ctx, "related_symbols", None) or []
        if related:
            parts.append("Related symbols (call/dependency graph):")
            for r in related:
                parts.append(f"  - {r.relation}: {r.name} ({r.file_path})")
        return "\n".join(parts) if parts else "No structural context available."

    @staticmethod
    def _read_affected_source(f: Normalized_Finding, ctx: "RepoContext") -> str:
        """Best-effort inclusion of the affected symbol body / file source.

        Prefers a symbol body already carried on the repository context (no I/O);
        falls back to reading the file from a workspace root when one is available.
        Failures are swallowed — source is supplementary, not required.
        """
        # 1. Reuse a symbol body already present in the context (matches by path).
        target = getattr(ctx, "target_symbols", None) or []
        for s in target:
            if getattr(s, "file_path", None) == f.location.path and getattr(s, "body", None):
                return f"--- {f.location.path} ---\n{s.body}"

        # 2. Optionally read the file from a workspace root exposed on the context.
        workspace = getattr(ctx, "workspace", None)
        if workspace:
            full_path = os.path.join(workspace, f.location.path)
            if os.path.exists(full_path):
                try:
                    with open(full_path, "r", encoding="utf-8") as fh:
                        return f"--- {f.location.path} ---\n{fh.read()}"
                except Exception:  # pragma: no cover - defensive I/O guard
                    return ""
        return ""

    def repair(
        self, f: Normalized_Finding, ctx: "RepoContext"
    ) -> CandidatePatch | None:
        """Produce a proposal-only :class:`CandidatePatch` for ``f`` (Requirement 10.1).

        Isolates the LLM call: builds the prompt, requests structured JSON via the
        shared :class:`LLMService`, and maps the response onto an immutable
        :class:`CandidatePatch` associated with ``f`` by ``target_finding_id``. Returns
        ``None`` when the model declines or yields no usable diff, so the pure core can
        mark the finding ``unresolved`` (Requirement 10.4).
        """
        prompt = self._build_prompt(f, ctx)
        logger.info(
            f"AI repair for finding {f.finding_id} "
            f"({f.rule_identity}); prompt size: {len(prompt)} chars"
        )
        response: RepairResponseSchema = self.llm_service.generate_structured_json(
            prompt=prompt,
            schema=RepairResponseSchema,
            skip_cache=True,  # never cache repair proposals (mirrors RepairAgent)
        )
        if not response.can_produce_patch or not response.diff.strip():
            logger.info(
                f"AI repair declined for finding {f.finding_id}: {response.reason!r}"
            )
            return None
        return CandidatePatch(target_finding_id=f.finding_id, diff=response.diff)


# ---------------------------------------------------------------------------
# Pure core — select findings for repair and associate patches
# ---------------------------------------------------------------------------


def is_scanner_confirmed(finding: Normalized_Finding) -> bool:
    """Whether a finding originated from at least one scanner (see module docstring).

    There is no separate ``synthetic`` flag on :class:`Normalized_Finding`; a finding
    is scanner-confirmed exactly when it carries scanner provenance, i.e. its
    ``scanners`` set is non-empty.
    """
    return len(finding.scanners) > 0


def is_repair_eligible(finding: Normalized_Finding) -> bool:
    """Whether AI_Repair should be attempted for ``finding`` (Requirement 10.1).

    Eligible iff the finding is scanner-confirmed and NOT labeled a likely false
    positive. False-positive-labeled findings are retained (never dropped) but are
    skipped for repair.
    """
    return is_scanner_confirmed(finding) and not finding.likely_false_positive


def select_repairs(
    findings: list[Normalized_Finding],
    adapter: "AIRepairAdapter",
    ctx: "RepoContext",
) -> list[Normalized_Finding]:
    """Attempt repair for eligible findings, associating patches and marking unresolved.

    Pure orchestration, deterministic with respect to the injected ``adapter`` (so it
    can be property-tested with a fake/mock adapter). For each input finding, in order:

    * **Not repair-eligible** (not scanner-confirmed, or labeled a likely false
      positive): returned unchanged — never repaired, never marked unresolved, never
      dropped (false positives remain for human review).
    * **Eligible, patch produced**: the finding gets a :class:`CandidatePatch` attached
      via ``candidate_patch``. The patch's ``target_finding_id`` is re-bound to the
      finding's ``finding_id`` so the association holds by construction (Requirement
      10.2), regardless of what the adapter set. The patch is a proposal only — this
      function never applies or merges it (Requirement 10.3); ``status`` stays as-is
      (deterministic verification decides ``fixed`` later).
    * **Eligible, no patch** (adapter returns ``None`` or raises): the finding is marked
      :attr:`FindingStatus.UNRESOLVED` with a recorded ``unresolved_reason``
      (Requirement 10.4).

    Args:
        findings: The triaged/scored :class:`Normalized_Finding`s to consider.
        adapter: An injected :class:`AIRepairAdapter` producing a
            :class:`CandidatePatch` or ``None`` per finding (real LLM adapter in
            production, fake in tests).
        ctx: The Layer 1 repository context passed through to the adapter.

    Returns:
        A new list of findings in the same order, each either unchanged, carrying an
        associated candidate patch, or marked unresolved with a reason.
    """
    result: list[Normalized_Finding] = []
    for finding in findings:
        if not is_repair_eligible(finding):
            result.append(finding)
            continue

        patch: CandidatePatch | None
        reason = NO_PATCH_REASON
        try:
            patch = adapter.repair(finding, ctx)
        except Exception as exc:  # design: adapter may return None *or* raise (10.4)
            logger.warning(
                f"AI repair adapter raised for finding {finding.finding_id}: {exc}"
            )
            patch = None
            reason = REPAIR_ERROR_REASON

        if patch is None:
            result.append(
                replace(
                    finding,
                    status=FindingStatus.UNRESOLVED,
                    unresolved_reason=reason,
                )
            )
        else:
            # Guarantee the association property by binding the patch to this finding.
            associated = replace(patch, target_finding_id=finding.finding_id)
            result.append(replace(finding, candidate_patch=associated))
    return result
