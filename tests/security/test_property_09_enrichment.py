"""Property 9: Enrichment completeness (security-pipeline).

Exercises :func:`app.security.intelligence.enrich.enrich` over arbitrary sets of
:class:`app.security.models.Normalized_Finding` and a varied
:class:`app.schemas.repository.RepositoryContext`.

Layer 3 enrichment must always populate every contextual signal — no matter what
the repository context carries — because downstream risk scoring (Requirement 8)
depends on every factor being present. Where a signal cannot be determined from
the context, a documented deterministic default is used (never ``None``).

The test asserts that, for every enriched finding:
* ``reachability`` is populated and in ``[0, 1]`` (Requirement 7.1),
* ``business_criticality`` is populated and in ``[0, 1]`` (Requirement 7.2),
* ``exposure`` is drawn from ``{PUBLIC, INTERNAL}`` (Requirement 7.3),
* ``auth_context`` is a valid :class:`AuthContext` (Requirement 7.4).

It also checks that ``enrich`` preserves the count and order of findings and does
not mutate its inputs (the inputs, being frozen dataclasses, must be untouched).

The empty case (empty finding list and/or empty repository context, exercising the
documented defaults) is covered by the generated inputs.

Validates: Requirements 7.1, 7.2, 7.3, 7.4
"""

from __future__ import annotations

import copy

from hypothesis import given, settings
from hypothesis import strategies as st

from app.schemas.repository import (
    RelatedSymbol,
    RepositoryContext,
    RetrievedSymbol,
    SymbolReachability,
)
from app.security.intelligence.enrich import enrich
from app.security.models import AuthContext, Exposure, Normalized_Finding
from tests.security.strategies import identifiers, normalized_findings, parseable_paths

# --------------------------------------------------------------------------- #
# Repository-context strategies (varied: with/without each signal, incl. empty)
# --------------------------------------------------------------------------- #


@st.composite
def retrieved_symbols(draw: st.DrawFn) -> RetrievedSymbol:
    return RetrievedSymbol(
        name=draw(identifiers),
        type=draw(st.sampled_from(("function", "class", "method", "unknown"))),
        file_path=draw(parseable_paths),
        body=draw(st.text(max_size=20)),
    )


@st.composite
def related_symbols(draw: st.DrawFn) -> RelatedSymbol:
    return RelatedSymbol(
        name=draw(identifiers),
        qualified_name=draw(st.one_of(st.none(), identifiers)),
        type=draw(st.sampled_from(("function", "class", "unknown"))),
        file_path=draw(st.one_of(st.none(), parseable_paths)),
        relation=draw(st.sampled_from(("caller", "callee", "imported"))),
    )


@st.composite
def symbol_reachabilities(draw: st.DrawFn) -> SymbolReachability:
    return SymbolReachability(
        symbol_name=draw(identifiers),
        qualified_name=draw(st.one_of(st.none(), identifiers)),
        file_path=draw(parseable_paths),
        caller_count=draw(st.integers(min_value=0, max_value=20)),
        callee_count=draw(st.integers(min_value=0, max_value=20)),
        has_callers=draw(st.booleans()),
        reachable_from_entrypoint=draw(st.booleans()),
    )


@st.composite
def repository_contexts(draw: st.DrawFn) -> RepositoryContext:
    """A varied :class:`RepositoryContext`.

    Each of ``target_symbols``, ``related_symbols`` and ``reachability`` is
    independently drawn and may be empty — so the fully-empty context (which
    forces every documented default to be exercised) is reachable, as are
    contexts carrying any combination of the three signals.
    """
    return RepositoryContext(
        target_symbols=draw(st.lists(retrieved_symbols(), max_size=4)),
        related_symbols=draw(st.lists(related_symbols(), max_size=4)),
        reachability=draw(st.lists(symbol_reachabilities(), max_size=4)),
    )


# --------------------------------------------------------------------------- #
# Property
# --------------------------------------------------------------------------- #


# Feature: security-pipeline, Property 9: For any set of Normalized_Findings and RepoContext, every enriched finding has a populated reachability, business_criticality, auth_context, and an exposure drawn from {public, internal}.
@settings(max_examples=100)
@given(
    findings=st.lists(normalized_findings(), max_size=8),
    repo_context=repository_contexts(),
)
def test_property_09_enrichment_completeness(
    findings: list[Normalized_Finding],
    repo_context: RepositoryContext,
) -> None:
    # Snapshot inputs to assert non-mutation afterwards.
    findings_before = copy.deepcopy(findings)
    context_before = repo_context.model_copy(deep=True)

    enriched = enrich(findings, repo_context)

    # Count and order preserved: one enriched finding per input, same identities.
    assert len(enriched) == len(findings)
    assert [e.finding_id for e in enriched] == [f.finding_id for f in findings]

    for original, e in zip(findings, enriched):
        # (7.1) reachability populated and within the unit interval.
        assert e.reachability is not None
        assert 0.0 <= e.reachability <= 1.0

        # (7.2) business_criticality populated and within the unit interval.
        assert e.business_criticality is not None
        assert 0.0 <= e.business_criticality <= 1.0

        # (7.4) auth_context populated with a valid AuthContext member.
        assert e.auth_context is not None
        assert isinstance(e.auth_context, AuthContext)

        # (7.3) exposure drawn from {PUBLIC, INTERNAL}.
        assert e.exposure in {Exposure.PUBLIC, Exposure.INTERNAL}

        # Identity/provenance carried through unchanged.
        assert e.finding_id == original.finding_id
        assert e.location == original.location
        assert e.severity == original.severity
        assert e.scanners == original.scanners

    # Inputs must not be mutated (Normalized_Finding is frozen; context untouched).
    assert findings == findings_before
    assert repo_context == context_before
