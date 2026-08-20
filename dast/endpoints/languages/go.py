"""Go route extractor (``net/http``-style).

Reads ``net/http`` route registrations out of ``.go`` source *without executing
it*. The whole extractor is a line/token regex scan: it never imports, compiles,
evaluates, or otherwise runs the file it is handed (Req 1.5-1.8). The orchestrator
reads the file once and passes its text in via ``source_text``; this module only
pattern-matches.

What it recognises
------------------

The ``net/http`` package (and compatible routers such as ``gorilla/mux`` or the
standard ``http.ServeMux``) registers handlers with ``HandleFunc`` on either the
package or a mux/router object::

    http.HandleFunc("/user", userHandler)      # -> /user
    mux.HandleFunc("/users", listUsers)        # -> /users
    r.HandleFunc("/users/{id}", getUser)       # -> /users/{id}

Because a ``HandleFunc`` registration carries **no explicit HTTP method**, each
match yields a :class:`~dast.endpoints.base.RawRoute` with an *empty* ``methods``
tuple; the orchestrator defaults it to ``GET`` (Req 3.3). The framework-native
path (``/users/{id}``) is returned verbatim on the ``RawRoute``; normalising it
to the shared ``{id}`` placeholder is the orchestrator's job (Req 4), not this
extractor's.

Design notes
------------

- **Path must start with ``/``.** ``net/http`` patterns are always rooted, so the
  scan only accepts a first argument that is a string literal beginning with
  ``/``. This keeps unrelated ``HandleFunc`` look-alikes and other calls from
  being mistaken for routes.
- **``<obj>.HandleFunc`` covers both forms.** The object may be the ``http``
  package itself (``http.HandleFunc``) or any mux/router identifier (``mux``,
  ``r``, ``router``…); a single pattern handles both.
- **Double-quoted and raw (backtick) string literals** are both accepted as the
  path delimiter, matching Go's two string-literal forms.

Requirements traced: 2.1, 2.2, 3.1, 3.3, 1.5, 1.6, 1.7, 1.8.
"""

from __future__ import annotations

import os
import re

from dast.endpoints.base import RawRoute

#: Extensions this extractor claims. Decided from the path alone (Req 2.2); the
#: file contents are never read by :meth:`GoExtractor.matches`.
_EXTENSIONS: frozenset[str] = frozenset({".go"})

#: One ``net/http`` route registration:
#:   <object>.HandleFunc( <quote><path-starting-with-/> <quote>
#: The object may be any identifier (``http``, ``mux``, ``r``, ``router``…). The
#: path literal may use " or ` delimiters and MUST start with ``/`` so unrelated
#: calls are not captured. ``discover`` computes the 1-based line from each
#: match's start offset (Req 3.1).
_ROUTE_RE = re.compile(
    r"""
    [A-Za-z_][\w]*                      # object: http, mux, r, router, ...
    \s*\.\s*
    HandleFunc                          # net/http registration
    \s*\(\s*
    (?P<quote>["`])                     # opening quote (double or raw/backtick)
    (?P<path>/[^"`]*)                   # rooted path, up to the closing quote
    (?P=quote)                          # matching closing quote
    """,
    re.VERBOSE,
)


class GoExtractor:
    """Recognise ``net/http``-style routes in ``.go`` source (Req 2.1).

    Duck-typed against :class:`dast.endpoints.base.LanguageExtractor`: it exposes
    a ``language`` label plus ``matches`` and ``discover``, so it needs no shared
    base class. Adding this extractor leaves every other extractor untouched
    (Req 2.5).
    """

    #: Stable label recorded in the run's extraction evidence.
    language: str = "go"

    def matches(self, source_path: str) -> bool:
        """Return ``True`` for ``.go`` files (by extension only).

        Cheap and static: the decision is made from the path's extension alone
        and never reads the file (Req 2.2).
        """
        return os.path.splitext(source_path)[1].lower() in _EXTENSIONS

    def discover(self, source_text: str, *, source_path: str) -> list[RawRoute]:
        """Return the ``net/http`` Route_Declarations found in ``source_text``.

        Pure and side-effect free: a regex scan over the already-read text. It
        never executes, imports, evaluates, or invokes the source (Req 1.5-1.8).

        Each ``HandleFunc`` match yields one :class:`RawRoute` carrying the
        framework-native path verbatim and the 1-based line the declaration
        begins on (Req 3.1). A ``HandleFunc`` registration declares no HTTP verb,
        so its ``methods`` tuple is empty and the orchestrator defaults it to
        ``GET`` (Req 3.3).
        """
        routes: list[RawRoute] = []
        for match in _ROUTE_RE.finditer(source_text):
            raw_path = match.group("path")
            # 1-based line at which the declaration begins (Req 3.1).
            line = source_text.count("\n", 0, match.start()) + 1
            # HandleFunc carries no explicit method; leave methods empty so the
            # orchestrator applies the GET default (Req 3.3).
            routes.append(RawRoute(methods=(), raw_path=raw_path, line=line))
        return routes
