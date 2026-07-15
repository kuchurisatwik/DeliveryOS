"""Layer 3 Batch Triage — the production-grade, low-call-count AI strategy.

The per-finding triage/repair loop makes ~2N LLM calls (one triage + one repair
for every finding). That does not scale: a commit with 100 findings makes ~200
calls and — with verification on — hundreds of scanner re-runs.

This module implements the approach real security tools use:

1. **Deterministic grouping** (0 LLM calls) — collapse findings that share a
   ``rule_identity`` into a single :class:`RuleGroup`. Eight ``b608`` SQL-injection
   hits become one group with a count of 8, because the *fix* for a rule is the
   same regardless of which line it occurs on.
2. **Severity gating** (0 LLM calls) — only HIGH/CRITICAL rule-groups are sent to
   the LLM. Lower-severity groups are reported deterministically (no AI cost).
3. **Batched analysis** (1–N LLM calls, capped) — all escalated groups are packed
   into a single structured-JSON request; the model returns one explanation +
   remediation per rule. Batches are chunked at ``batch_size`` and capped at
   ``max_calls`` so a run makes at most a handful of calls.

The output is a mapping ``rule_identity -> RuleAnalysis`` (explanation, priority,
remediation, false-positive flag). The Stage attaches it back to every finding of
that rule, and the report renders a per-rule remediation guide for the dev team.

Everything except :meth:`LLMBatchTriage.analyze` is pure and unit-testable.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Sequence

from pydantic import BaseModel, Field

from app.security.models import Normalized_Finding, Priority, Severity
from app.services.llm_service import LLMService
from app.utils.logger import logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.schemas.repository import RepositoryContext as RepoContext


# ---------------------------------------------------------------------------
# Pure grouping + selection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuleGroup:
    """All findings sharing one ``rule_identity``, collapsed for the dev team."""

    rule_identity: str
    severity: Severity          # the max severity seen for this rule
    category: str
    count: int                  # how many occurrences across the commit
    scanners: tuple[str, ...]   # every scanner that reported this rule
    locations: tuple[str, ...]  # up to a few "path:line" examples
    sample_message: str         # a representative scanner message


@dataclass(frozen=True)
class RuleAnalysis:
    """The AI's per-rule assessment attached back to every finding of that rule."""

    explanation: str
    priority: Priority
    remediation: str
    likely_false_positive: bool


_MAX_LOCATIONS_PER_GROUP = 5


def group_findings(findings: Sequence[Normalized_Finding]) -> list[RuleGroup]:
    """Collapse findings into per-``rule_identity`` groups (pure, 0 LLM calls).

    Groups are returned ordered by max severity (desc) then occurrence count
    (desc), so the most important rules lead. Deterministic for a given input.
    """
    buckets: dict[str, list[Normalized_Finding]] = {}
    for f in findings:
        buckets.setdefault(f.rule_identity, []).append(f)

    groups: list[RuleGroup] = []
    for rule_identity, items in buckets.items():
        severity = max((f.severity for f in items), key=lambda s: s.value)
        scanners = sorted({s for f in items for s in f.scanners})
        locations = tuple(
            f"{f.location.path}:{f.location.start_line}"
            for f in items[:_MAX_LOCATIONS_PER_GROUP]
        )
        groups.append(
            RuleGroup(
                rule_identity=rule_identity,
                severity=severity,
                category=items[0].category,
                count=len(items),
                scanners=tuple(scanners),
                locations=locations,
                sample_message=items[0].message,
            )
        )

    groups.sort(key=lambda g: (g.severity.value, g.count), reverse=True)
    return groups


def select_for_ai(
    groups: Sequence[RuleGroup], severities: frozenset[Severity]
) -> tuple[list[RuleGroup], list[RuleGroup]]:
    """Split groups into (escalated to AI, reported deterministically).

    ``severities`` are the levels that warrant an AI remediation. Everything else
    is returned as the second list to be listed in the report without an AI call.
    Pure.
    """
    escalate = [g for g in groups if g.severity in severities]
    rest = [g for g in groups if g.severity not in severities]
    return escalate, rest


def parse_severities(raw: str) -> frozenset[Severity]:
    """Parse ``"HIGH,CRITICAL"`` into a set of :class:`Severity` (pure)."""
    out: set[Severity] = set()
    for token in (raw or "").split(","):
        name = token.strip().upper()
        if not name:
            continue
        try:
            out.add(Severity[name])
        except KeyError:
            logger.warning("Unknown severity '%s' in SECURITY_AI_SEVERITIES", name)
    return frozenset(out or {Severity.HIGH, Severity.CRITICAL})


def _priority_for(severity: Severity) -> Priority:
    """Map a severity onto a remediation priority (pure, deterministic)."""
    return {
        Severity.CRITICAL: Priority.P0,
        Severity.HIGH: Priority.P1,
        Severity.MEDIUM: Priority.P2,
    }.get(severity, Priority.P3)


# ---------------------------------------------------------------------------
# LLM structured-output schema
# ---------------------------------------------------------------------------


class _BatchItemSchema(BaseModel):
    rule_identity: str = Field(description="Echo the exact rule_identity given for this group.")
    explanation: str = Field(description="Why this class of finding is dangerous, in context.")
    remediation: str = Field(description="Concrete, actionable fix guidance for the dev team.")
    likely_false_positive: bool = Field(
        default=False, description="True only when the repo context makes this a likely non-issue."
    )


class _BatchResponseSchema(BaseModel):
    items: list[_BatchItemSchema] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Impure shell — the batched LLM adapter
# ---------------------------------------------------------------------------


class LLMBatchTriage:
    """Produces per-rule :class:`RuleAnalysis` in 1–``max_calls`` batched calls."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
        *,
        batch_size: int = 30,
        max_calls: int = 5,
    ) -> None:
        self.llm_service = llm_service or LLMService()
        self.batch_size = max(1, batch_size)
        self.max_calls = max(1, max_calls)

    def analyze(
        self, groups: Sequence[RuleGroup], ctx: "RepoContext | None"
    ) -> dict[str, RuleAnalysis]:
        """Return ``{rule_identity: RuleAnalysis}`` for the escalated ``groups``.

        Chunks ``groups`` into ``batch_size`` slices and issues one LLM call per
        chunk, up to ``max_calls``. Any groups beyond the cap (or from a failed
        call) still receive a deterministic fallback analysis so nothing is
        dropped from the report. The LLM outage/quota case is handled gracefully.
        """
        if not groups:
            return {}

        results: dict[str, RuleAnalysis] = {}
        chunks = [
            list(groups[i : i + self.batch_size])
            for i in range(0, len(groups), self.batch_size)
        ]
        for idx, chunk in enumerate(chunks):
            if idx >= self.max_calls:
                # Beyond the call budget: deterministic fallback, no LLM call.
                for g in chunk:
                    results[g.rule_identity] = self._fallback(g, capped=True)
                continue
            try:
                results.update(self._analyze_chunk(chunk, ctx))
            except Exception as exc:  # noqa: BLE001 - AI augments; never a hard dep
                logger.warning(
                    "Batch triage LLM call %d/%d failed (%s); using deterministic "
                    "fallback for %d rule-group(s).",
                    idx + 1,
                    len(chunks),
                    exc,
                    len(chunk),
                )
                for g in chunk:
                    results.setdefault(g.rule_identity, self._fallback(g))
        return results

    def _analyze_chunk(
        self, chunk: Sequence[RuleGroup], ctx: "RepoContext | None"
    ) -> dict[str, RuleAnalysis]:
        prompt = self._build_prompt(chunk, ctx)
        logger.info(
            "Batch triage: analyzing %d rule-group(s) in one LLM call; prompt %d chars",
            len(chunk),
            len(prompt),
        )
        response: _BatchResponseSchema = self.llm_service.generate_structured_json(
            prompt=prompt, schema=_BatchResponseSchema
        )
        by_rule = {item.rule_identity: item for item in response.items}
        out: dict[str, RuleAnalysis] = {}
        for g in chunk:
            item = by_rule.get(g.rule_identity)
            if item is None:
                out[g.rule_identity] = self._fallback(g)
                continue
            out[g.rule_identity] = RuleAnalysis(
                explanation=item.explanation.strip() or self._fallback(g).explanation,
                priority=_priority_for(g.severity),
                remediation=item.remediation.strip() or "Review and remediate per secure-coding guidance.",
                likely_false_positive=item.likely_false_positive,
            )
        return out

    @staticmethod
    def _fallback(group: RuleGroup, *, capped: bool = False) -> RuleAnalysis:
        """Deterministic analysis when the LLM is unavailable or over budget."""
        note = (
            " (beyond AI call budget — manual review recommended)"
            if capped
            else " (AI unavailable — manual review recommended)"
        )
        return RuleAnalysis(
            explanation=f"{group.sample_message}{note}",
            priority=_priority_for(group.severity),
            remediation="Review this rule against secure-coding guidance and remediate.",
            likely_false_positive=False,
        )

    @staticmethod
    def _build_prompt(chunk: Sequence[RuleGroup], ctx: "RepoContext | None") -> str:
        lines: list[str] = [
            "You are a senior application-security engineer writing a remediation "
            "guide for a development team. You are given a list of DISTINCT security "
            "rule-groups found in a code change. For EACH group, return a concise, "
            "actionable analysis. Group findings are already deduplicated by rule; "
            "write one remediation per rule that applies to all its occurrences.",
            "",
            "Return strictly a JSON object: {\"items\": [ {rule_identity, explanation, "
            "remediation, likely_false_positive}, ... ]}. Echo each rule_identity "
            "EXACTLY as given so it can be matched back.",
            "",
            "=== SECURITY RULE-GROUPS ===",
        ]
        for i, g in enumerate(chunk, 1):
            locs = ", ".join(g.locations) if g.locations else "n/a"
            lines.append(
                f"{i}. rule_identity={g.rule_identity!r} | severity={g.severity.name} "
                f"| category={g.category} | occurrences={g.count} "
                f"| scanners={','.join(g.scanners)}"
            )
            lines.append(f"   message: {g.sample_message}")
            lines.append(f"   locations: {locs}")

        # Light repo context (best-effort, token-friendly).
        target = getattr(ctx, "target_symbols", None) or [] if ctx else []
        if target:
            lines.append("")
            lines.append("=== CHANGED SYMBOLS (context) ===")
            for s in target[:20]:
                lines.append(f"  - {getattr(s, 'type', '')} {getattr(s, 'name', '')} ({getattr(s, 'file_path', '')})")
        return "\n".join(lines)
