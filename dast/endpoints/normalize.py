"""Path normalisation for endpoint extraction.

Turns a *framework-native* route path — ``/users/:id``, ``/users/<int:id>``,
``/users/{user_id}``, ``/files/*`` — into the one canonical template shape the
DAST scanners already speak, and pulls out the declared path-parameter names.

Why a separate normaliser from :func:`dast.urls.normalize_path`?
``dast.urls.normalize_path`` templatises a *concrete URL* — it has to *guess*
which segments are identifiers (a pure-digit or UUID-looking segment). Here we
templatise a *declared route*, where the framework tells us exactly which
segments are dynamic and what they are called. The two must nevertheless agree
on the *output* shape: Req 4.6 pins that the template we emit is a fixed point of
:func:`dast.urls.endpoint_identity` — feeding our output back through the
scanner's identity function returns it unchanged. That is what lets an extracted
endpoint and a scanned URL collapse to one finding identity instead of two.

The shared placeholder is imported from :mod:`dast.urls` (``{id}``) rather than
re-declared, so there is exactly one source of truth for the identity language.

Requirements traced: 4.1, 4.2, 4.3, 4.4, 4.5, 3.4.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from dast.urls import PLACEHOLDER

#: The ``:name`` colon form (Express / Sinatra / Rails), e.g. ``:id``.
_COLON = re.compile(r"^:(.+)$")
#: The ``<name>`` and ``<type:name>`` angle forms (Flask), e.g. ``<id>`` /
#: ``<int:id>`` / ``<path:filename>``.
_ANGLE = re.compile(r"^<(.+)>$")
#: The ``{name}`` brace form (FastAPI / OpenAPI), e.g. ``{id}`` / ``{user_id}``.
_BRACE = re.compile(r"^\{(.+)\}$")


def _declared_param_name(segment: str) -> str | None:
    """Return the declared parameter name if ``segment`` is dynamic, else ``None``.

    Recognises the four framework dynamic-segment syntaxes plus the bare ``*``
    wildcard (Req 4.2). A non-dynamic segment returns ``None`` and is preserved
    verbatim by the caller (Req 4.1).

    The name is the identifier the route *declared*, before it collapses to the
    shared placeholder (Req 3.4): ``:id`` -> ``"id"``, ``<int:id>`` -> ``"id"``,
    ``<path:filename>`` -> ``"filename"``, ``{user_id}`` -> ``"user_id"``. A bare
    ``*`` wildcard carries no declared name, so it is named after the shared
    placeholder's own identifier, ``"id"``.
    """
    match = _COLON.match(segment)
    if match:
        return match.group(1)

    match = _ANGLE.match(segment)
    if match:
        # ``<type:name>`` -> the name is the part after the type converter; a
        # plain ``<name>`` has no ``:`` and yields itself.
        return match.group(1).rsplit(":", 1)[-1]

    match = _BRACE.match(segment)
    if match:
        # Tolerate a ``{type:name}`` spelling the same way; plain ``{name}`` and
        # ``{id}`` yield themselves.
        return match.group(1).rsplit(":", 1)[-1]

    if segment == "*":
        return "id"

    return None


def normalize_route_path(raw_path: str) -> tuple[str, tuple[str, ...]]:
    """Return ``(path_template, ordered path-parameter names)`` for ``raw_path``.

    The returned template:

    - replaces every dynamic segment — the ``:name`` colon form, the ``<name>``
      and ``<type:name>`` angle forms, the ``{name}`` brace form, and a bare
      ``*`` wildcard — with the shared :data:`dast.urls.PLACEHOLDER` (``{id}``),
      preserving every non-dynamic segment unchanged (Req 4.1, 4.2);
    - begins with exactly one leading ``/`` and carries no scheme or host
      component (Req 4.3);
    - collapses every run of two or more ``/`` separators into a single ``/``
      (Req 4.4); and
    - drops a trailing ``/`` for every template other than the root ``/``
      (Req 4.5).

    The returned names are the segment names *as declared* in the route, in path
    order, each becoming a path-kind Endpoint_Parameter of the endpoint (Req 3.4).

    The output is a fixed point of :func:`dast.urls.endpoint_identity` (Req 4.6):
    dynamic segments become ``{id}`` (which the scanner leaves untouched) and
    literal route-name segments are preserved, so re-normalising the result is a
    no-op.

    Args:
        raw_path: A framework-native route path, e.g. ``/users/:id`` or
            ``/users/<int:id>``. A full URL is tolerated — its scheme and host
            are dropped (Req 4.3).

    Returns:
        A tuple of the canonical path template and the ordered tuple of declared
        path-parameter names.
    """
    # Drop any scheme/host so only the path is normalised (Req 4.3). urlsplit
    # only strips these when a scheme is actually present, so a plain path with a
    # ``:name`` segment is left alone.
    if "://" in raw_path:
        raw_path = urlsplit(raw_path).path

    # Splitting on "/" and discarding empty pieces collapses runs of "//"
    # (Req 4.4) and drops any leading/trailing "/" (Req 4.3, 4.5) in one step.
    segments = [segment for segment in raw_path.split("/") if segment]

    template_segments: list[str] = []
    param_names: list[str] = []
    for segment in segments:
        name = _declared_param_name(segment)
        if name is None:
            template_segments.append(segment)
        else:
            template_segments.append(PLACEHOLDER)
            param_names.append(name)

    # No segments -> the root path. Re-add the single leading "/" otherwise.
    path_template = "/" + "/".join(template_segments) if template_segments else "/"
    return path_template, tuple(param_names)
