"""OpenAPI synthesis and parsing for the endpoint inventory.

When the running target publishes no OpenAPI spec of its own, Schemathesis has
nothing to generate requests from. This module closes that gap: it turns an
:class:`~dast.endpoints.models.EndpointInventory` — the endpoints read statically
out of the target's source — into a *minimal but valid* OpenAPI 3.0 document that
Schemathesis can consume, and reads such a document back into an inventory.

Three pure functions, no I/O:

- :func:`synthesize_openapi` builds the OpenAPI 3.0 ``dict`` (Req 8.1, 8.4, 8.5).
- :func:`synthesize_openapi_bytes` serialises it byte-deterministically so two
  invocations over the same inventory produce identical bytes (Req 8.6).
- :func:`parse_openapi` reads a document back into an inventory, identities only,
  enabling the synthesise -> parse round-trip (Req 8.3).

Deliberate limitations (stated on purpose): the synthesised document carries no
``requestBody`` and no response *schemas*. A full request/response contract is a
real OpenAPI document's job; this one exists only to give Schemathesis a valid set
of operations to exercise. Each operation still carries the minimal ``responses``
object the OpenAPI 3.0 schema requires so the document loads without a
schema-validation error (Req 8.2).

Requirements traced: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6.
"""

from __future__ import annotations

import json
import re
from typing import Mapping

from dast.endpoints.models import (
    SUPPORTED_METHODS,
    EndpointInventory,
    EndpointParameter,
    ExtractedEndpoint,
    ParameterKind,
)

#: OpenAPI version the synthesised document declares. 3.0.x is what the
#: Schemathesis adapter already loads elsewhere in the service.
_OPENAPI_VERSION = "3.0.0"

#: Fixed ``info`` block — title/version are required by the OpenAPI schema but carry
#: no meaning for a synthesised spec, so they are constant (keeps output
#: byte-identical across runs, Req 8.6).
_INFO = {"title": "Synthesized endpoint inventory", "version": "1.0.0"}

#: Every synthesised operation carries this minimal ``responses`` object. The
#: OpenAPI 3.0 Operation Object *requires* ``responses``; a single ``default``
#: response with only a description is the smallest structurally valid value and
#: declares no response schema (stated limitation).
_DEFAULT_RESPONSES = {"default": {"description": "Synthesized operation."}}

#: The supported methods as lowercase OpenAPI operation keys, mirroring extraction's
#: supported set. Used when reading a document back (Req 8.3).
_SUPPORTED_METHOD_KEYS: frozenset[str] = frozenset(
    method.lower() for method in SUPPORTED_METHODS
)

#: Matches a template variable in a path, e.g. the ``id`` inside ``{id}``.
_TEMPLATE_VAR = re.compile(r"\{([^}]+)\}")


def _template_var_names(path: str) -> tuple[str, ...]:
    """Return the distinct template-variable names in ``path`` in first-seen order.

    A normalised inventory path uses the shared ``{id}`` placeholder for every
    dynamic segment, so ``/users/{id}/orders/{id}`` yields ``("id",)`` — a single
    name declared once. Declaring one path parameter per *distinct* name (rather
    than one per occurrence) keeps the operation's parameter list free of the
    duplicate ``(name, in)`` pairs the OpenAPI schema forbids (Req 8.2).
    """
    seen: list[str] = []
    for match in _TEMPLATE_VAR.finditer(path):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return tuple(seen)


def _path_parameter(name: str) -> dict:
    """A required, string-typed ``path`` parameter object (Req 8.5)."""
    return {
        "name": name,
        "in": "path",
        "required": True,
        "schema": {"type": "string"},
    }


def _query_parameter(name: str) -> dict:
    """An optional, string-typed ``query`` parameter object."""
    return {
        "name": name,
        "in": "query",
        "required": False,
        "schema": {"type": "string"},
    }


def _operation(endpoint: ExtractedEndpoint) -> dict:
    """Build the OpenAPI Operation Object for one endpoint.

    - Each distinct ``{id}`` template variable becomes a required ``string`` path
      parameter (Req 8.5).
    - Each :attr:`~dast.endpoints.models.ParameterKind.QUERY` parameter becomes an
      optional ``string`` query parameter.
    - No ``requestBody`` and no response schema; only the minimal required
      ``responses`` object (stated limitation, Req 8.2).
    """
    parameters: list[dict] = [
        _path_parameter(name) for name in _template_var_names(endpoint.path)
    ]

    query_names = sorted(
        parameter.name
        for parameter in endpoint.parameters
        if parameter.kind is ParameterKind.QUERY
    )
    parameters.extend(_query_parameter(name) for name in query_names)

    operation: dict = {"responses": dict(_DEFAULT_RESPONSES)}
    if parameters:
        operation["parameters"] = parameters
    return operation


def synthesize_openapi(inventory: EndpointInventory) -> dict:
    """Emit a minimal OpenAPI 3.0 document for ``inventory`` (Req 8.1, 8.4, 8.5).

    One ``paths`` entry per distinct Path_Template, one operation per HTTP_Method
    under it. An empty inventory yields a structurally valid document whose
    ``paths`` object is empty (Req 8.4).

    Pure: builds and returns a fresh ``dict`` on every call, performing no I/O.
    """
    paths: dict[str, dict] = {}
    for endpoint in inventory.endpoints:
        path_item = paths.setdefault(endpoint.path, {})
        # (method, path) is unique across a deduplicated inventory, so this never
        # overwrites a sibling method under the same path.
        path_item[endpoint.method.lower()] = _operation(endpoint)

    return {
        "openapi": _OPENAPI_VERSION,
        "info": dict(_INFO),
        "paths": paths,
    }


def synthesize_openapi_bytes(inventory: EndpointInventory) -> bytes:
    """Serialise :func:`synthesize_openapi` to byte-identical UTF-8 (Req 8.6).

    ``sort_keys=True`` makes the output independent of dict insertion order and the
    fixed ``separators`` remove insignificant whitespace, so two invocations over
    the same inventory produce byte-for-byte identical documents.
    """
    document = synthesize_openapi(inventory)
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _parameters_for(path: str, operation: object) -> frozenset[EndpointParameter]:
    """Reconstruct an endpoint's parameters from a path template + operation object.

    Path parameters are derived from the template variables (each distinct name is
    a :attr:`~dast.endpoints.models.ParameterKind.PATH` parameter), and any
    ``in: query`` parameter declared on the operation becomes a
    :attr:`~dast.endpoints.models.ParameterKind.QUERY` parameter. Missing or
    malformed parameter declarations are tolerated — only identities are required
    to round-trip (Req 8.3).
    """
    parameters: set[EndpointParameter] = {
        EndpointParameter(name=name, kind=ParameterKind.PATH)
        for name in _template_var_names(path)
    }

    if isinstance(operation, Mapping):
        declared = operation.get("parameters")
        if isinstance(declared, (list, tuple)):
            for parameter in declared:
                if not isinstance(parameter, Mapping):
                    continue
                if parameter.get("in") != "query":
                    continue
                name = parameter.get("name")
                if isinstance(name, str) and name:
                    parameters.add(
                        EndpointParameter(name=name, kind=ParameterKind.QUERY)
                    )

    return frozenset(parameters)


def parse_openapi(document: Mapping | dict) -> EndpointInventory:
    """Read an OpenAPI document back into an :class:`EndpointInventory` (Req 8.3).

    Walks ``paths`` -> operation, recording one
    :class:`~dast.endpoints.models.ExtractedEndpoint` per operation whose verb is in
    the supported set ``{GET, POST, PUT, PATCH, DELETE}`` (mirroring extraction).
    A missing or empty ``paths`` object yields an empty inventory. Source-location
    fields carry no meaning for a parsed document, so they are left empty; only the
    Endpoint_Identity ``(method, path)`` is guaranteed to round-trip.

    The result is sorted by ``(path, method)`` for determinism, matching the shape a
    freshly extracted inventory has.
    """
    endpoints: list[ExtractedEndpoint] = []

    paths = document.get("paths") if isinstance(document, Mapping) else None
    if isinstance(paths, Mapping):
        for path, path_item in paths.items():
            if not isinstance(path, str) or not isinstance(path_item, Mapping):
                continue
            for verb, operation in path_item.items():
                if not isinstance(verb, str):
                    continue
                if verb.lower() not in _SUPPORTED_METHOD_KEYS:
                    continue
                endpoints.append(
                    ExtractedEndpoint(
                        method=verb.upper(),
                        path=path,
                        parameters=_parameters_for(path, operation),
                        source_file="",
                        source_line=0,
                    )
                )

    endpoints.sort(key=lambda endpoint: (endpoint.path, endpoint.method))
    return EndpointInventory(endpoints=tuple(endpoints))
