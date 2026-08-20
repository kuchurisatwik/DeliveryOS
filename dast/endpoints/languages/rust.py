"""Rust route extractor (actix-web attribute macros + axum/actix ``.route`` builder).

Reads Rust web-framework Route_Declarations out of ``.rs`` source *without
executing it*. The whole extractor is a line/token regex scan: it never imports,
compiles, evaluates, or otherwise runs the file it is handed (Req 1.5-1.8). The
orchestrator reads the file once and passes its text in via ``source_text``; this
module only pattern-matches.

What it recognises
------------------

Two dominant Rust web styles are covered:

- **actix-web attribute macros.** The macro name is the HTTP verb and the string
  literal is the path::

      #[get("/users")]           -> GET    /users
      #[post("/users/{id}")]     -> POST   /users/{id}
      #[put("/users/{id}")]      -> PUT    /users/{id}
      #[patch("/users/{id}")]    -> PATCH  /users/{id}
      #[delete("/users/{id}")]   -> DELETE /users/{id}
      #[head("/ping")]           -> HEAD   /ping

- **axum / actix ``.route(...)`` builder.** The first string literal is the path;
  the HTTP verbs are every axum *method-filter* function
  (``get``/``post``/``put``/``patch``/``delete``/``head``/``options``) named in
  the remainder of that same ``.route(...)`` call::

      .route("/users", get(list))                    -> GET    /users
      .route("/users/{id}", get(show).delete(remove))-> GET, DELETE /users/{id}
      .route("/users/{id}", post(update))            -> POST   /users/{id}

  When several method filters are chained on one route (``get(...).delete(...)``)
  each verb becomes its own :class:`~dast.endpoints.base.RawRoute`.

Design notes
------------

- **Path params are left verbatim.** axum uses the ``{id}`` brace form; it is
  returned exactly as declared. Collapsing dynamic segments to the shared
  ``{id}`` placeholder is the orchestrator's normaliser job (Req 4), not this
  extractor's.
- **One RawRoute per (verb, path).** Attribute macros carry exactly one verb; a
  multi-filter ``.route`` yields one RawRoute per method filter found.
- **actix ``web::resource("/x").route(web::get()...)`` is not specially handled.**
  This extractor focuses on the two dominant styles above. A
  ``web::resource(...)`` path literal followed by ``web::get()``-style filters is
  a known limitation — such routes may be missed rather than mis-reported.
- **Method filters are matched by name only.** Any ``verb(`` token in the route
  remainder (e.g. ``get(``) counts, matching axum's ``axum::routing::get`` free
  functions regardless of import alias.

Requirements traced: 2.1, 2.2, 3.1, 3.2, 3.3, 1.5, 1.6, 1.7, 1.8.
"""

from __future__ import annotations

import os
import re

from dast.endpoints.base import RawRoute

#: Extensions this extractor claims. Decided from the path alone (Req 2.2); the
#: file contents are never read by :meth:`RustExtractor.matches`.
_EXTENSIONS: frozenset[str] = frozenset({".rs"})

#: actix-web attribute macro: ``#[get("/path")]``. The macro name is the verb and
#: the first string literal is the path. ``discover`` computes the 1-based line
#: from each match's start offset (Req 3.1).
_ATTR_MACRO_RE = re.compile(
    r"""
    \#\s*\[\s*                          # attribute opener: #[
    (?P<verb>get|post|put|patch|delete|head|options)
    \s*\(\s*
    "(?P<path>[^"]*)"                   # the path string literal
    """,
    re.VERBOSE | re.IGNORECASE,
)

#: actix-web generic route attribute macro: ``#[route("/path", method = "PUT")]``.
#: The path is the string literal; the verb(s) come from one or more
#: ``method = "VERB"`` guards captured in ``rest``.
_ROUTE_ATTR_RE = re.compile(
    r"""
    \#\s*\[\s*route\s*\(\s*             # attribute opener: #[route(
    "(?P<path>[^"]*)"                   # the path string literal
    (?P<rest>[^\]]*)                    # remaining args (method = "..." guards)
    \]
    """,
    re.VERBOSE,
)

#: A ``method = "VERB"`` guard inside a ``#[route(...)]`` attribute.
_METHOD_ATTR_RE = re.compile(r'method\s*=\s*"(?P<verb>\w+)"', re.IGNORECASE)

#: An axum/actix ``.route("/path", <handlers...>)`` call. ``rest`` captures the
#: remainder of the call (the method-filter chain) up to the end of the line, from
#: which every verb function is read.
_ROUTE_BUILDER_RE = re.compile(
    r"""
    \.\s*route\s*\(\s*                  # .route(
    "(?P<path>[^"]*)"                   # first string literal = the path
    \s*,\s*
    (?P<rest>[^\n]*)                    # the method-filter chain (rest of line)
    """,
    re.VERBOSE,
)

#: A method-filter function call inside a ``.route`` remainder, e.g. ``get(`` or
#: ``delete(``. Word-boundary anchored so ``target(`` or ``forget(`` do not match.
_METHOD_FILTER_RE = re.compile(
    r"\b(?P<verb>get|post|put|patch|delete|head|options)\s*\(",
    re.IGNORECASE,
)


class RustExtractor:
    """Recognise actix-web / axum routes in ``.rs`` source (Req 2.1).

    Duck-typed against :class:`dast.endpoints.base.LanguageExtractor`: it exposes
    a ``language`` label plus ``matches`` and ``discover``, so it needs no shared
    base class. Adding this extractor leaves every other extractor untouched
    (Req 2.5).
    """

    #: Stable label recorded in the run's extraction evidence.
    language: str = "rust"

    def matches(self, source_path: str) -> bool:
        """Return ``True`` for ``.rs`` files (by extension only).

        Cheap and static: the decision is made from the path's extension alone
        and never reads the file (Req 2.2).
        """
        return os.path.splitext(source_path)[1].lower() in _EXTENSIONS

    def discover(self, source_text: str, *, source_path: str) -> list[RawRoute]:
        """Return the Rust Route_Declarations found in ``source_text``.

        Pure and side-effect free: a regex scan over the already-read text. It
        never executes, imports, evaluates, or invokes the source (Req 1.5-1.8).

        actix-web attribute macros yield one :class:`RawRoute` (verb from the
        macro name); axum/actix ``.route`` builders yield one RawRoute per method
        filter found in the call. Each carries the framework-native path verbatim
        and the 1-based line the declaration begins on (Req 3.1, 3.2).
        """
        routes: list[RawRoute] = []

        # actix-web attribute macros: verb = macro name, path = string literal.
        for match in _ATTR_MACRO_RE.finditer(source_text):
            verb = match.group("verb").upper()
            raw_path = match.group("path")
            line = source_text.count("\n", 0, match.start()) + 1
            routes.append(
                RawRoute(methods=(verb,), raw_path=raw_path, line=line)
            )

        # actix-web generic route macro: #[route("/path", method = "PUT")]. The
        # verb(s) come from one or more method = "VERB" guards; none listed leaves
        # methods empty so the orchestrator defaults to GET (Req 3.3).
        for match in _ROUTE_ATTR_RE.finditer(source_text):
            raw_path = match.group("path")
            line = source_text.count("\n", 0, match.start()) + 1
            methods = tuple(
                m.group("verb").upper()
                for m in _METHOD_ATTR_RE.finditer(match.group("rest") or "")
            )
            routes.append(
                RawRoute(methods=methods, raw_path=raw_path, line=line)
            )

        # axum / actix .route("/path", get(..).delete(..)) builders: one RawRoute
        # per method filter named in the remainder of the call.
        for match in _ROUTE_BUILDER_RE.finditer(source_text):
            raw_path = match.group("path")
            line = source_text.count("\n", 0, match.start()) + 1
            for filt in _METHOD_FILTER_RE.finditer(match.group("rest")):
                verb = filt.group("verb").upper()
                routes.append(
                    RawRoute(methods=(verb,), raw_path=raw_path, line=line)
                )

        return routes
