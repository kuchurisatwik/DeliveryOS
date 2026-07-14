"""Example test: AI triage content SHAPE (Layer 3, Requirement 9.1).

Design reference: design.md "Testing Strategy" → "AI triage content shape with
mocked adapter". This is a deterministic *example* test (not property-based).

It exercises :meth:`app.security.intelligence.triage.LLMTriageAdapter.triage`
with a **mocked** :class:`~app.services.llm_service.LLMService` whose
``generate_structured_json`` returns a canned
:class:`~app.security.intelligence.triage.TriageResponseSchema`. Because the LLM
output is non-deterministic in production, the test asserts only the *shape* of
the resulting :class:`~app.security.models.AITriage` and the deterministic
integer→:class:`~app.security.models.Priority` mapping — never specific content
values.

It additionally asserts the adapter's contract with the LLM service: a non-empty
prompt is passed positionally-or-by-keyword and the ``TriageResponseSchema`` is
handed to ``generate_structured_json`` as the schema.

Validates: Requirements 9.1
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.schemas.repository import RepositoryContext, RetrievedSymbol
from app.security.intelligence.triage import LLMTriageAdapter, TriageResponseSchema
from app.security.models import AITriage, Location, Normalized_Finding, Priority, Severity


def _finding() -> Normalized_Finding:
    """A minimal, fully-formed normalized finding to triage."""
    return Normalized_Finding(
        finding_id="F-1",
        rule_identity="python.lang.security.audit.dangerous-exec",
        location=Location(path="app/handlers.py", start_line=10, end_line=14, symbol="run"),
        severity=Severity.HIGH,
        scanners=frozenset({"semgrep", "bandit"}),
        category="code",
        message="Use of dangerous exec()",
    )


def _context() -> RepositoryContext:
    """A small repository context so the adapter renders a non-trivial prompt."""
    return RepositoryContext(
        target_symbols=[
            RetrievedSymbol(name="run", type="function", file_path="app/handlers.py", body="def run(): ...")
        ],
    )


def _adapter_with_canned(response: TriageResponseSchema) -> tuple[LLMTriageAdapter, MagicMock]:
    """Build an adapter backed by a mock LLM service returning ``response``."""
    mock_llm = MagicMock()
    mock_llm.generate_structured_json.return_value = response
    adapter = LLMTriageAdapter(llm_service=mock_llm)
    return adapter, mock_llm


def test_triage_returns_aitriage_with_expected_shape() -> None:
    """triage() returns an AITriage whose fields have the expected types (9.1)."""
    canned = TriageResponseSchema(
        explanation="This exec call runs untrusted input.",
        priority=1,
        suggested_fix="Replace exec with a safe dispatch table.",
        likely_false_positive=False,
    )
    adapter, _ = _adapter_with_canned(canned)

    result = adapter.triage(_finding(), _context())

    # Shape assertions only — no specific content values.
    assert isinstance(result, AITriage)
    assert isinstance(result.explanation, str)
    assert isinstance(result.priority, Priority)
    assert isinstance(result.suggested_fix, str)
    assert isinstance(result.likely_false_positive, bool)


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, Priority.P0),
        (1, Priority.P1),
        (2, Priority.P2),
        (3, Priority.P3),
    ],
)
def test_triage_maps_integer_priority_to_enum(value: int, expected: Priority) -> None:
    """Each integer 0..3 maps onto the corresponding Priority member (9.1)."""
    canned = TriageResponseSchema(
        explanation="explanation",
        priority=value,
        suggested_fix="fix",
        likely_false_positive=True,
    )
    adapter, _ = _adapter_with_canned(canned)

    result = adapter.triage(_finding(), _context())

    assert result.priority is expected
    # likely_false_positive shape/value is a bool passed through unchanged.
    assert isinstance(result.likely_false_positive, bool)
    assert result.likely_false_positive is True


def test_triage_calls_llm_service_with_nonempty_prompt_and_schema() -> None:
    """The adapter passes a non-empty prompt and TriageResponseSchema to the LLM (9.1)."""
    canned = TriageResponseSchema(
        explanation="explanation",
        priority=2,
        suggested_fix="fix",
        likely_false_positive=False,
    )
    adapter, mock_llm = _adapter_with_canned(canned)

    adapter.triage(_finding(), _context())

    mock_llm.generate_structured_json.assert_called_once()
    call = mock_llm.generate_structured_json.call_args

    # prompt and schema may be passed positionally or by keyword — resolve both.
    prompt = call.kwargs.get("prompt")
    if prompt is None and call.args:
        prompt = call.args[0]
    schema = call.kwargs.get("schema")
    if schema is None and len(call.args) > 1:
        schema = call.args[1]

    assert isinstance(prompt, str)
    assert prompt.strip() != ""
    assert schema is TriageResponseSchema
