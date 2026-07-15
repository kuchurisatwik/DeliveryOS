"""Tests for the batch-triage strategy (low LLM-call-count remediation guide)."""

from __future__ import annotations

from app.security.intelligence.batch_triage import (
    LLMBatchTriage,
    RuleAnalysis,
    group_findings,
    parse_severities,
    select_for_ai,
)
from app.security.models import Location, Normalized_Finding, Severity


def _f(rule: str, sev: Severity, path: str, line: int, scanner: str = "bandit") -> Normalized_Finding:
    return Normalized_Finding(
        finding_id=f"{rule}-{path}-{line}",
        rule_identity=rule,
        location=Location(path=path, start_line=line, end_line=line),
        severity=sev,
        scanners=frozenset({scanner}),
        category="code",
        message=f"{rule} issue",
    )


def test_grouping_collapses_repeats_by_rule():
    findings = [
        _f("b608", Severity.HIGH, "a.py", 1),
        _f("b608", Severity.HIGH, "b.py", 2),
        _f("b608", Severity.HIGH, "c.py", 3),
        _f("b105", Severity.MEDIUM, "a.py", 9),
    ]
    groups = group_findings(findings)
    by_rule = {g.rule_identity: g for g in groups}
    assert by_rule["b608"].count == 3          # three occurrences collapse to one group
    assert by_rule["b105"].count == 1
    # Highest severity leads the ordering.
    assert groups[0].rule_identity == "b608"


def test_severity_gating_splits_escalated_from_rest():
    findings = [
        _f("b608", Severity.CRITICAL, "a.py", 1),
        _f("b105", Severity.MEDIUM, "b.py", 2),
        _f("b101", Severity.LOW, "c.py", 3),
    ]
    groups = group_findings(findings)
    escalate, rest = select_for_ai(groups, parse_severities("HIGH,CRITICAL"))
    assert [g.rule_identity for g in escalate] == ["b608"]
    assert {g.rule_identity for g in rest} == {"b105", "b101"}


class _CountingLLM:
    """Fake LLMService counting calls; returns one item per group in the prompt."""

    def __init__(self):
        self.calls = 0

    def generate_structured_json(self, prompt, schema, skip_cache: bool = False):
        self.calls += 1
        # Echo back an item for every rule_identity mentioned in the prompt.
        import re

        rules = re.findall(r"rule_identity='([^']+)'", prompt)
        return schema(items=[
            {
                "rule_identity": r,
                "explanation": f"why {r}",
                "remediation": f"fix {r}",
                "likely_false_positive": False,
            }
            for r in rules
        ])


def test_batch_uses_one_call_for_small_commit():
    findings = [_f(f"rule{i}", Severity.HIGH, "a.py", i) for i in range(10)]
    groups = group_findings(findings)
    llm = _CountingLLM()
    analyzer = LLMBatchTriage(llm, batch_size=30, max_calls=5)
    result = analyzer.analyze(groups, ctx=None)
    assert llm.calls == 1                      # 10 rules → single batched call
    assert len(result) == 10
    assert result["rule0"].remediation == "fix rule0"


def test_batch_respects_call_cap():
    # 65 distinct rules, batch_size 10 → would be 7 chunks, capped at 3 calls.
    findings = [_f(f"rule{i}", Severity.HIGH, "a.py", i) for i in range(65)]
    groups = group_findings(findings)
    llm = _CountingLLM()
    analyzer = LLMBatchTriage(llm, batch_size=10, max_calls=3)
    result = analyzer.analyze(groups, ctx=None)
    assert llm.calls == 3                       # hard cap honored
    assert len(result) == 65                    # every rule still covered (fallback beyond cap)


def test_batch_falls_back_on_llm_error():
    class _FailingLLM:
        def generate_structured_json(self, prompt, schema, skip_cache: bool = False):
            raise RuntimeError("LLM down")

    findings = [_f("b608", Severity.CRITICAL, "a.py", 1)]
    groups = group_findings(findings)
    result = LLMBatchTriage(_FailingLLM()).analyze(groups, ctx=None)
    assert isinstance(result["b608"], RuleAnalysis)   # graceful fallback, no crash
