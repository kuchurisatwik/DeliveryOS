"""Layer 3 AI Triage — attach AI assessment to findings (Requirement 9).

This module has two clearly-separated halves, following the design's
"pure core, impure shell" principle:

* :class:`LLMTriageAdapter` — the **impure shell**. A concrete
  :class:`~app.security.protocols.AITriageAdapter` implementation that reuses the
  existing :class:`~app.services.llm_service.LLMService` (exactly as the
  engineering/repair agents do: build a prompt, call
  :meth:`LLMService.generate_structured_json` with a Pydantic schema, benefit from
  its prompt-hash caching) to produce an :class:`~app.security.models.AITriage`
  (explanation, priority, suggested fix approach, likely-false-positive flag) for a
  :class:`~app.security.models.Normalized_Finding` plus repository context
  (Requirement 9.1). The LLM call is fully isolated here.

* :func:`attach_triage` — the **pure core**. Given a set of findings and an injected
  triage adapter, it attaches each finding's triage WITHOUT dropping any finding
  (Requirement 9.2), labels a finding a likely false positive exactly when its triage
  says so while RETAINING it for human review (Requirement 9.2), and attaches the
  triage WITHOUT altering the deterministic ``risk_score`` (Requirement 9.3). Because
  :class:`Normalized_Finding` is frozen, new instances are produced via
  :func:`dataclasses.replace`, which copies every unspecified field (including
  ``risk_score``) unchanged — this is what guarantees non-mutation of the score.

The adapter is injectable, so :func:`attach_triage` is deterministic with respect to
the adapter's outputs and can be property-tested (design Property 12) with an
in-memory fake/mock adapter — no network required.
"""

from __future__ import annotations

import os
from dataclasses import replace
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.security.models import AITriage, Normalized_Finding, Priority
from app.services.llm_service import LLMService
from app.utils.logger import logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.security.protocols import AITriageAdapter
    from app.schemas.repository import RepositoryContext as RepoContext


# ---------------------------------------------------------------------------
# LLM structured-output schema
# ---------------------------------------------------------------------------


class TriageResponseSchema(BaseModel):
    """Structured JSON the LLM must return for a single finding's triage.

    Mirrors :class:`~app.security.models.AITriage` but uses primitive types the
    LLM can emit reliably; ``priority`` is an integer ``0..3`` mapped onto the
    :class:`~app.security.models.Priority` enum (P0..P3).
    """

    explanation: str = Field(
        description="Developer-facing explanation of the finding and why it matters."
    )
    priority: int = Field(
        ge=0,
        le=3,
        description="Remediation priority: 0=P0 (critical) .. 3=P3 (low).",
    )
    suggested_fix: str = Field(
        description="Concrete secure fix approach (guidance, not a full patch)."
    )
    likely_false_positive: bool = Field(
        default=False,
        description="True only when repo context makes over-reporting highly likely.",
    )


def _priority_from_int(value: int) -> Priority:
    """Map an integer ``0..3`` onto :class:`Priority`, clamping out-of-range values."""
    clamped = max(0, min(3, int(value)))
    return Priority(clamped)


# ---------------------------------------------------------------------------
# Impure shell — the concrete LLM-backed adapter
# ---------------------------------------------------------------------------


class LLMTriageAdapter:
    """Concrete :class:`AITriageAdapter` backed by :class:`LLMService`.

    Reuses the shared LLM service (and its prompt-hash caching) exactly as the
    engineering/repair agents do. All side effects (prompt assembly + network
    call) are confined to :meth:`triage`; the returned :class:`AITriage` is a
    plain immutable value the pure core can attach.
    """

    def __init__(
        self,
        llm_service: LLMService | None = None,
        prompt_path: str | None = None,
    ) -> None:
        self.llm_service = llm_service or LLMService()
        self.prompt_template = ""
        path = prompt_path or os.path.join(
            os.getcwd(), "app", "prompts", "security_triage.md"
        )
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.prompt_template = f.read()

    def _build_prompt(self, f: Normalized_Finding, ctx: "RepoContext") -> str:
        """Assemble the triage prompt from the template, finding, and repo context."""
        lines: list[str] = [self.prompt_template, "\n=== SECURITY FINDING ==="]
        lines.append(f"Rule identity: {f.rule_identity}")
        lines.append(f"Category: {f.category}")
        lines.append(f"Severity: {f.severity.name}")
        lines.append(f"Reported by scanners: {', '.join(sorted(f.scanners))}")
        loc = f.location
        symbol = f" (symbol: {loc.symbol})" if loc.symbol else ""
        lines.append(
            f"Location: {loc.path}:{loc.start_line}-{loc.end_line}{symbol}"
        )
        lines.append(f"Message: {f.message}")
        if f.exposure is not None:
            lines.append(f"Exposure: {f.exposure.value}")
        if f.auth_context is not None:
            lines.append(f"Auth context: {f.auth_context.value}")

        lines.append("\n=== REPOSITORY CONTEXT ===")
        lines.append(self._format_context(ctx))
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

    def triage(self, f: Normalized_Finding, ctx: "RepoContext") -> AITriage:
        """Produce an :class:`AITriage` for ``f`` in ``ctx`` (Requirement 9.1).

        Isolates the LLM call: builds the prompt, requests structured JSON via the
        shared :class:`LLMService`, and maps the response onto the immutable
        :class:`AITriage` value object.
        """
        prompt = self._build_prompt(f, ctx)
        logger.info(
            f"AI triage for finding {f.finding_id} "
            f"({f.rule_identity}); prompt size: {len(prompt)} chars"
        )
        response: TriageResponseSchema = self.llm_service.generate_structured_json(
            prompt=prompt,
            schema=TriageResponseSchema,
        )
        return AITriage(
            explanation=response.explanation,
            priority=_priority_from_int(response.priority),
            suggested_fix=response.suggested_fix,
            likely_false_positive=response.likely_false_positive,
        )


# ---------------------------------------------------------------------------
# Pure core — attach triage to findings
# ---------------------------------------------------------------------------


def attach_triage(
    findings: list[Normalized_Finding],
    adapter: "AITriageAdapter",
    ctx: "RepoContext",
) -> list[Normalized_Finding]:
    """Attach AI triage to every finding, retaining all and preserving risk scores.

    Pure orchestration: for each finding it obtains an :class:`AITriage` from the
    injected ``adapter`` and returns a NEW finding with the triage attached. The
    behavior is deterministic with respect to the adapter's outputs, so it can be
    property-tested with a fake/mock adapter.

    Guarantees (Requirement 9.2, 9.3):

    * **Retention** — the output has exactly one finding per input finding, in the
      same order; nothing is dropped, even when triage flags a likely false positive.
    * **False-positive labeling** — ``likely_false_positive`` on each output finding
      equals its triage's ``likely_false_positive`` flag.
    * **Risk-score non-mutation** — the triage is attached via
      :func:`dataclasses.replace`, which only sets ``triage`` and
      ``likely_false_positive`` and copies every other field (including
      ``risk_score``) unchanged from the original frozen instance.

    Args:
        findings: The scored :class:`Normalized_Finding`s to triage.
        adapter: An injected :class:`AITriageAdapter` producing an
            :class:`AITriage` per finding (real LLM adapter in production, fake in tests).
        ctx: The Layer 1 repository context passed through to the adapter.

    Returns:
        A new list of findings, each with ``triage`` and ``likely_false_positive``
        populated and every other field (notably ``risk_score``) unchanged.
    """
    triaged: list[Normalized_Finding] = []
    for finding in findings:
        try:
            assessment = adapter.triage(finding, ctx)
        except Exception as exc:  # noqa: BLE001 - AI augments, never a hard dep
            # AI triage is an augmentation, not a hard dependency (design: "AI
            # augments the deterministic scanners; it never replaces them"). If
            # the LLM is unavailable (e.g. quota/outage), RETAIN the finding
            # untriaged rather than dropping it or failing the pipeline — the
            # deterministic finding still matters.
            logger.warning(
                "AI triage unavailable for finding %s (%s); retaining untriaged.",
                finding.finding_id,
                exc,
            )
            triaged.append(finding)
            continue
        triaged.append(
            replace(
                finding,
                triage=assessment,
                likely_false_positive=assessment.likely_false_positive,
            )
        )
    return triaged
