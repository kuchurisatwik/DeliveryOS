"""Deterministic deduplication of extracted endpoints (Req 5).

A single route can be declared in several files (a mount here, a re-export
there), and the same file can be walked in different orders on different
machines. If those duplicates flowed straight into the inventory they would
inflate it, and the *choice* of which duplicate to keep would depend on
traversal order — which would make a finding impossible to re-confirm.

:func:`deduplicate` collapses every group of endpoints that share an
``Endpoint_Identity`` (``(method, path)``) into exactly one endpoint, choosing
what to keep by a total order that does not depend on input order:

- **retained source location** — the minimum by
  ``(repo-relative source_file, source_line)`` (Req 5.1, 5.3);
- **parameters** — the union keyed by ``name`` across the whole group, so each
  distinct parameter name appears exactly once (Req 5.2);
- **output order** — sorted by ``(path, method)`` so the returned sequence is
  itself deterministic.

The function is pure: it reads its input, allocates new frozen dataclasses, and
performs no I/O.

Requirements traced: 5.1, 5.2, 5.3.
"""

from __future__ import annotations

from typing import Iterable

from dast.endpoints.models import EndpointParameter, ExtractedEndpoint

__all__ = ["deduplicate"]


def _location_key(endpoint: ExtractedEndpoint) -> tuple[str, int]:
    """Order key selecting the retained declaration within an identity group.

    Ascending repository-relative ``source_file`` first, then ascending
    ``source_line`` (Req 5.1). Because this is a total order over the group and
    ignores input position, the winner is identical regardless of the order the
    endpoints were discovered or supplied in (Req 5.3).
    """
    return (endpoint.source_file, endpoint.source_line)


def _parameter_key(parameter: EndpointParameter) -> tuple[str, str]:
    """Deterministic order key for a parameter (name first, then kind value).

    Used only to make the *choice* of representative for a given name stable when
    the same name appears with differing kinds across the group.
    """
    return (parameter.name, parameter.kind.value)


def _merge_parameters(
    group: Iterable[ExtractedEndpoint],
) -> frozenset[EndpointParameter]:
    """Union the group's parameters keyed by name, each name exactly once (Req 5.2).

    When one name appears with more than one :class:`ParameterKind` across the
    group, a single representative is chosen deterministically (smallest by
    ``(name, kind)``) so the merge is independent of input order (Req 5.3).
    """
    by_name: dict[str, EndpointParameter] = {}
    for endpoint in group:
        for parameter in endpoint.parameters:
            existing = by_name.get(parameter.name)
            if existing is None or _parameter_key(parameter) < _parameter_key(
                existing
            ):
                by_name[parameter.name] = parameter
    return frozenset(by_name.values())


def deduplicate(
    endpoints: Iterable[ExtractedEndpoint],
) -> tuple[ExtractedEndpoint, ...]:
    """Collapse endpoints sharing an ``Endpoint_Identity`` (Req 5).

    Endpoints that share ``(method, path)`` are merged into one: the retained
    source location is the minimum by ``(source_file, source_line)`` (Req 5.1),
    the parameters are the union keyed by name (Req 5.2), and the returned tuple
    is sorted by ``(path, method)`` (Req 5.3). Pure and order-independent.
    """
    groups: dict[tuple[str, str], list[ExtractedEndpoint]] = {}
    for endpoint in endpoints:
        groups.setdefault(endpoint.identity, []).append(endpoint)

    retained: list[ExtractedEndpoint] = []
    for group in groups.values():
        winner = min(group, key=_location_key)
        merged = ExtractedEndpoint(
            method=winner.method,
            path=winner.path,
            parameters=_merge_parameters(group),
            source_file=winner.source_file,
            source_line=winner.source_line,
        )
        retained.append(merged)

    retained.sort(key=lambda endpoint: (endpoint.path, endpoint.method))
    return tuple(retained)
