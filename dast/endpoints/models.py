"""Data models for endpoint extraction.

The DAST scanners are only as good as the list of endpoints they are handed.
This module defines the *static-extraction* side of that list: the normalised
endpoints read out of a Target_Repository's source code, the deduplicated
inventory they collapse into, and the evidence record of one extraction run.

Everything here is a frozen dataclass (or an :class:`~enum.Enum`), matching the
existing ``dast/models.py`` and ``app/security/models.py`` style, so the pure
extraction core stays hashable and side-effect free.

Invariants are enforced *by construction* (see :class:`ExtractedEndpoint`):

- an endpoint's ``method`` is always one of the supported HTTP verbs
  ``{GET, POST, PUT, PATCH, DELETE}`` (Req 3.5); and
- an endpoint's :attr:`~ExtractedEndpoint.identity` is ``(method, path)`` only —
  ``parameters`` never participate in identity (Req 5).

Requirements traced: 1.1, 3.1, 5.1, 11.1.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

#: The HTTP verbs an :class:`ExtractedEndpoint` may carry. Any route declaration
#: registering a verb outside this set is dropped during extraction (Req 3.5);
#: the model constructor is the last line of defence enforcing that invariant.
SUPPORTED_METHODS: frozenset[str] = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE"}
)


class ExtractionError(Exception):
    """Raised when extraction cannot even begin.

    The extractor degrades gracefully for every *per-file* problem — an
    unreadable file, an unparseable file, a file outside the root, an oversized
    file — by skipping it and continuing (Req 1.4, 2.3, 9.7, 10.1). The one
    condition that has no inventory to return is a bad root: a Target_Repository
    root path that does not exist or is not a directory (Req 10.2). That case
    raises this error, naming the offending path.
    """


class ParameterKind(Enum):
    """Whether an :class:`EndpointParameter` came from the path or the query.

    - :attr:`PATH` parameters are derived from the route's dynamic segments and
      are named after the declared segment (Req 3.4).
    - :attr:`QUERY` parameters are advisory metadata an extractor could read.
    """

    PATH = "path"
    QUERY = "query"


@dataclass(frozen=True)
class EndpointParameter:
    """A single named parameter of an :class:`ExtractedEndpoint`.

    Parameters are identity-independent metadata: two endpoints with the same
    ``(method, path)`` are the same endpoint regardless of their parameters
    (Req 5). During dedup, parameters are unioned by :attr:`name`.
    """

    name: str
    kind: ParameterKind


@dataclass(frozen=True)
class ExtractedEndpoint:
    """One normalised endpoint read from source (Req 3.1).

    Carries the HTTP method, the normalised path template (dynamic segments
    collapsed to the shared ``{id}`` placeholder), the set of parameters, and the
    repository-relative source location the declaration was read from.
    """

    #: Uppercase HTTP verb, always in :data:`SUPPORTED_METHODS`.
    method: str
    #: Normalised path template, e.g. ``"/users/{id}"`` — one leading ``/``, no
    #: scheme/host, no ``//``, no trailing ``/`` except root.
    path: str
    #: Identity-independent metadata; unioned by name during dedup (Req 5.2).
    parameters: frozenset[EndpointParameter]
    #: Repository-relative path of the Source_File the route was declared in.
    source_file: str
    #: 1-based line at which the Route_Declaration begins (Req 3.1).
    source_line: int

    def __post_init__(self) -> None:
        # Enforce the supported-method invariant by construction (Req 3.5): an
        # ExtractedEndpoint can never exist with an unsupported verb, so callers
        # downstream never have to re-check.
        if self.method not in SUPPORTED_METHODS:
            raise ValueError(
                f"unsupported HTTP method {self.method!r}; "
                f"expected one of {sorted(SUPPORTED_METHODS)}"
            )

    @property
    def identity(self) -> tuple[str, str]:
        """Endpoint_Identity = ``(HTTP_Method, Path_Template)`` (Req 5).

        Deliberately excludes ``parameters`` so that two declarations of the same
        method+path collapse to one endpoint regardless of their parameters,
        matching ``dast.urls.endpoint_identity``.
        """
        return (self.method, self.path)


@dataclass(frozen=True)
class EndpointInventory:
    """The deduplicated collection produced by one extraction run (Req 1.1).

    No two endpoints share an :attr:`~ExtractedEndpoint.identity`; the sequence is
    sorted by ``(path, method)`` for determinism (enforced by the dedup step, not
    the constructor).
    """

    endpoints: tuple[ExtractedEndpoint, ...]


@dataclass(frozen=True)
class ExtractionActivity:
    """Evidence of one extraction run (Req 11.1).

    The extraction analogue of :class:`dast.models.ToolActivity`: it records what
    the run *did*, so an empty inventory can be told apart from a genuinely
    route-free repository. An empty inventory combined with an empty spec is an
    *unseeded* scan surface, never scanned-and-clean.
    """

    #: Source_Files a Language_Extractor actually read during the run.
    files_read: int
    #: Endpoints in the resulting :class:`EndpointInventory`.
    endpoints_found: int
    #: Languages whose registered extractor produced at least one route.
    languages: frozenset[str]


@dataclass(frozen=True)
class ExtractionResult:
    """What one extraction run produced: the inventory plus its evidence."""

    inventory: EndpointInventory
    activity: ExtractionActivity
