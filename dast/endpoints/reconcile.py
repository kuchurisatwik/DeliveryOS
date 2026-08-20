"""Reconcile extracted endpoints with the runtime OpenAPI spec.

The DAST scanners are seeded from two sources that describe the same target from
different angles: the OpenAPI spec fetched from the *running* application at
preflight, and the :class:`~dast.endpoints.models.EndpointInventory` read
statically from the target's *source code*. Neither is complete on its own — a
target may publish no spec at all, or publish one that misses routes the source
declares — so the scan surface must be the union of both.

This module produces that union as a single ordered tuple of path templates,
ready to drop onto ``DastScope.spec_paths`` verbatim (Req 7).

Two subtleties make this more than a set union:

1. **Identity across placeholder names.** An OpenAPI template names its
   parameters (``/users/{user_id}``) while the inventory always uses the shared
   ``dast.urls`` placeholder (``/users/{id}``). Those two strings differ but
   denote *the same endpoint*. So identity is compared on a canonical form in
   which every brace segment ``{...}`` is rewritten to ``{id}`` — for comparison
   only. The template text that is actually kept is never rewritten.

2. **Spec wins a clash.** When an inventory template collides with a spec
   template on that canonical identity, the spec's template is retained and the
   inventory's dropped (Req 6.2). The spec's parameter names are the target's own
   and keep ``spec_paths`` in the exact form the adapters already consume.

Requirements traced: 6.1, 6.2, 6.3, 6.4, 6.5.
"""

from __future__ import annotations

import re
from typing import Sequence

from dast.urls import PLACEHOLDER

#: Matches a single OpenAPI/route brace segment such as ``{id}`` or ``{user_id}``.
#: Rewriting every match to the shared placeholder canonicalises a template so
#: that ``/u/{user_id}`` and ``/u/{id}`` compare equal (Req 6.2).
_BRACE_SEGMENT = re.compile(r"\{[^{}]*\}")


def _canonical_identity(template: str) -> str:
    """Return the identity key for ``template`` (comparison only).

    Every brace segment ``{...}`` is collapsed to the shared ``{id}`` placeholder
    so that two templates naming the same parameter differently — ``/u/{user_id}``
    and ``/u/{id}`` — share one identity. The returned string is used purely to
    detect clashes; the original ``template`` text is preserved in the output.
    """
    return _BRACE_SEGMENT.sub(PLACEHOLDER, template)


def reconcile(
    spec_paths: Sequence[str], inventory_paths: Sequence[str]
) -> tuple[str, ...]:
    """Union runtime-spec templates with inventory templates (Req 6).

    Args:
        spec_paths: Path templates from the target's runtime OpenAPI spec, in the
            order preflight produced them. May be empty.
        inventory_paths: Path templates from the statically extracted
            :class:`~dast.endpoints.models.EndpointInventory`, in inventory order.
            May be empty.

    Returns:
        The reconciled path templates as an ordered tuple in which:

        - each distinct endpoint identity appears exactly once (Req 6.1);
        - when a spec template and an inventory template denote the same identity,
          the spec template is kept and the inventory one dropped (Req 6.2);
        - an empty spec yields the inventory templates alone, an empty inventory
          yields the spec templates alone, and two empty inputs yield an empty
          tuple (Req 6.3, 6.4, 6.5);
        - spec templates come first in their given order, then the inventory-only
          templates in their given order.
    """
    reconciled: list[str] = []
    seen: set[str] = set()

    # Spec templates first: they win any identity clash (Req 6.2) and lead the
    # ordering. Guarding on the canonical identity also drops any duplicate
    # identities within the spec itself, keeping each distinct one once (Req 6.1).
    for template in spec_paths:
        identity = _canonical_identity(template)
        if identity not in seen:
            seen.add(identity)
            reconciled.append(template)

    # Inventory templates next: only those whose identity was not already seen —
    # neither in the spec nor earlier in the inventory — are appended (Req 6.1).
    for template in inventory_paths:
        identity = _canonical_identity(template)
        if identity not in seen:
            seen.add(identity)
            reconciled.append(template)

    return tuple(reconciled)
