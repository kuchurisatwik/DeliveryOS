"""URL normalisation — turning concrete URLs into stable endpoint identities.

Why this exists: the finding identity used by the shared normalisation layer hashes
the location path. DAST tools report *concrete* URLs, so ``/api/users/12345`` and
``/api/users/67890`` hash to two different findings — even though they are one bug
on one endpoint. On a target with real data that turns a single broken endpoint
into thousands of "new" findings and makes the baseline useless within a week.

It is the same mistake as opening a new ticket for every car that runs the same
broken traffic light. There is one broken light.

So before a URL becomes a :class:`~app.security.models.Location` we:

1. drop the scheme and host — otherwise moving staging to a new hostname re-IDs
   every finding we have ever recorded; and
2. collapse dynamic path segments to a placeholder, preferring the target's own
   OpenAPI path templates as the source of truth and falling back to heuristics
   when no spec is available.
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence
from urllib.parse import urlsplit

#: Placeholder substituted for a dynamic path segment.
PLACEHOLDER = "{id}"

#: A path segment that is entirely digits (``/orders/40021``).
_NUMERIC = re.compile(r"^\d+$")
#: A canonical UUID (``/users/1b4e28ba-2fa1-11d2-883f-0016d3cca427``).
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
#: A long hex run — object ids, content hashes, tokens (``/blobs/9f86d081884c7d65``).
_LONG_HEX = re.compile(r"^[0-9a-f]{12,}$", re.IGNORECASE)
#: An OpenAPI template segment (``{user_id}``).
_SPEC_PARAM = re.compile(r"^\{.+\}$")


def _is_dynamic(segment: str) -> bool:
    """True when a concrete path segment looks like an identifier, not a route name."""
    return bool(
        _NUMERIC.match(segment) or _UUID.match(segment) or _LONG_HEX.match(segment)
    )


def _match_spec_path(segments: Sequence[str], spec_paths: Iterable[str]) -> str | None:
    """Return the OpenAPI path template matching ``segments``, or ``None``.

    A spec segment wrapped in braces matches any concrete segment; every other
    segment must match literally. When several templates match (e.g. ``/users/me``
    and ``/users/{id}``) the one with the most literal matches wins, so a concrete
    route is never swallowed by a more general template.
    """
    best: tuple[int, str] | None = None
    for spec_path in spec_paths:
        spec_segments = [s for s in spec_path.split("/") if s]
        if len(spec_segments) != len(segments):
            continue
        literals = 0
        for spec_segment, segment in zip(spec_segments, segments):
            if _SPEC_PARAM.match(spec_segment):
                continue
            if spec_segment != segment:
                break
            literals += 1
        else:
            if best is None or literals > best[0]:
                best = (literals, spec_path)
    return best[1] if best else None


def normalize_path(path: str, spec_paths: Iterable[str] = ()) -> str:
    """Collapse a concrete URL path into a stable endpoint identity.

    Args:
        path: A URL path, e.g. ``/api/users/12345/orders/98``.
        spec_paths: OpenAPI path templates from the target's spec. When supplied
            these take precedence — the spec knows which segments are parameters
            and heuristics only guess.

    Returns:
        The templated path, e.g. ``/api/users/{id}/orders/{id}``.
    """
    segments = [s for s in path.split("/") if s]
    if not segments:
        return "/"

    matched = _match_spec_path(segments, spec_paths)
    if matched:
        return matched

    return "/" + "/".join(
        PLACEHOLDER if _is_dynamic(segment) else segment for segment in segments
    )


def endpoint_identity(url: str, spec_paths: Iterable[str] = ()) -> str:
    """Reduce a full URL to a host-independent, ID-independent endpoint identity.

    ``https://staging.example.com/api/users/12345?debug=1`` → ``/api/users/{id}``

    The host is dropped deliberately: the same endpoint on staging and on a renamed
    staging host is the same endpoint, and keeping the host would re-ID every
    finding whenever infrastructure moves. The query string is dropped too — the
    affected parameter is recorded separately on the location's ``symbol``.
    """
    parts = urlsplit(url)
    if parts.scheme in ("http", "https"):
        return normalize_path(parts.path or "/", spec_paths)
    if url.startswith("/"):
        # Already a bare path (some tools report one).
        return normalize_path(urlsplit(url).path, spec_paths)
    # Tools that scan non-HTTP protocols report ``host:port`` rather than a URL.
    # There is no path to normalise, so keep the raw value — note that urlsplit
    # would otherwise read ``staging.example.com:5432`` as scheme + path and
    # helpfully templatise the port number into ``/{id}``.
    return url
