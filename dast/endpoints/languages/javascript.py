"""JavaScript / TypeScript route extractor (Express-style).

Reads Express / Express-Router route declarations out of ``.js`` and ``.ts``
source *without executing it*. The whole extractor is a line/token regex scan:
it never imports, evaluates, requires, or otherwise runs the file it is handed
(Req 1.5-1.8). The orchestrator reads the file once and passes its text in via
``source_text``; this module only pattern-matches.

What it recognises
------------------

The Express router registers routes as method calls on an ``app`` or ``router``
object with a leading string path::

    app.get("/users/:id", handler)         # -> GET  /users/:id
    router.post("/users", handler)         # -> POST /users
    app.put("/users/:id", handler)         # -> PUT  /users/:id
    app.delete("/users/:id", handler)      # -> DELETE /users/:id
    app.patch("/users/:id", handler)       # -> PATCH  /users/:id
    app.use("/api", router)                # -> mount path /api (no verb -> GET)

The framework-native path (``/users/:id``) is returned verbatim on the
:class:`~dast.endpoints.base.RawRoute`; normalising the ``:name`` segment to the
shared ``{id}`` placeholder is the orchestrator's job (Req 4), not this
extractor's.

Design notes
------------

- **Path must start with ``/``.** Express route paths are always rooted, so the
  scan only accepts a first argument that is a string literal beginning with
  ``/``. This keeps unrelated ``.get``/``.post`` calls (``cache.get("key")``,
  ``axios.post("https://…")``) from being mistaken for routes.
- **``use`` is a mount, not a verb.** ``app.use("/api", router)`` mounts a
  sub-router at a path; the declaration carries no HTTP verb, so its
  :class:`RawRoute` has empty ``methods`` and the orchestrator defaults it to
  ``GET`` (Req 3.3).
- **Single quotes, double quotes, and template literals** are all accepted as the
  path literal delimiter; a template literal is only read when it contains no
  ``${…}`` interpolation (an interpolated path is not a static literal).

Requirements traced: 2.1, 2.2, 3.1, 3.2, 3.3, 1.5, 1.6, 1.7, 1.8.
"""

from __future__ import annotations

import os
import re

from dast.endpoints.base import RawRoute

#: Extensions this extractor claims. Decided from the path alone (Req 2.2); the
#: file contents are never read by :meth:`JavaScriptExtractor.matches`.
_EXTENSIONS: frozenset[str] = frozenset({".js", ".ts"})

#: HTTP-verb method names Express exposes on ``app``/``router``. ``use`` is
#: handled separately (it is a mount, not a verb).
_VERB_METHODS: frozenset[str] = frozenset(
    {"get", "post", "put", "delete", "patch"}
)

#: One Express route/mount declaration:
#:   <object>.<method>( <quote><path-starting-with-/> <quote>
#: The object may be any identifier (``app``, ``router``, ``api``, ``r``…). The
#: path literal may use ', ", or ` delimiters and MUST start with ``/`` so that
#: unrelated ``.get``/``.post`` calls are not captured. ``discover`` computes the
#: 1-based line from each match's start offset (Req 3.1).
_ROUTE_RE = re.compile(
    r"""
    [A-Za-z_$][\w$]*                    # object: app, router, api, r, ...
    \s*\.\s*
    (?P<method>get|post|put|delete|patch|use)   # HTTP verb or mount
    \s*\(\s*
    (?P<quote>['"`])                    # opening quote
    (?P<path>/[^'"`${}]*)               # rooted path, no interpolation/brace
    (?P=quote)                          # matching closing quote
    """,
    re.VERBOSE,
)


class JavaScriptExtractor:
    """Recognise Express-style routes in ``.js``/``.ts`` source (Req 2.1).

    Duck-typed against :class:`dast.endpoints.base.LanguageExtractor`: it exposes
    a ``language`` label plus ``matches`` and ``discover``, so it needs no shared
    base class. Adding this extractor leaves every other extractor untouched
    (Req 2.5).
    """

    #: Stable label recorded in the run's extraction evidence.
    language: str = "javascript"

    def matches(self, source_path: str) -> bool:
        """Return ``True`` for ``.js`` and ``.ts`` files (by extension only).

        Cheap and static: the decision is made from the path's extension alone
        and never reads the file (Req 2.2).
        """
        return os.path.splitext(source_path)[1].lower() in _EXTENSIONS

    def discover(self, source_text: str, *, source_path: str) -> list[RawRoute]:
        """Return the Express Route_Declarations found in ``source_text``.

        Pure and side-effect free: a regex scan over the already-read text. It
        never executes, imports, evaluates, or invokes the source (Req 1.5-1.8).

        Each match yields one :class:`RawRoute` carrying the framework-native
        path verbatim, the derived HTTP verb(s), and the 1-based line the
        declaration begins on (Req 3.1, 3.2). A ``use`` mount carries no explicit
        verb — its ``methods`` is empty and the orchestrator defaults it to
        ``GET`` (Req 3.3).
        """
        routes: list[RawRoute] = []
        for match in _ROUTE_RE.finditer(source_text):
            method = match.group("method")
            raw_path = match.group("path")
            # 1-based line at which the declaration begins (Req 3.1).
            line = source_text.count("\n", 0, match.start()) + 1

            if method == "use":
                # A mount point declares a path but no HTTP verb; leave methods
                # empty so the orchestrator applies the GET default (Req 3.3).
                methods: tuple[str, ...] = ()
            else:
                # Native verb name -> uppercase HTTP method (Req 3.2).
                methods = (method.upper(),)

            routes.append(RawRoute(methods=methods, raw_path=raw_path, line=line))
        return routes
