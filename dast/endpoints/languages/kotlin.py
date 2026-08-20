"""Kotlin route extractor (Spring MVC / Spring Boot annotations + Ktor DSL).

Reads Kotlin Route_Declarations out of ``.kt`` source *without executing it*. The
whole extractor is a line/token regex scan: it never imports, compiles,
evaluates, or otherwise runs the file it is handed (Req 1.5-1.8). The orchestrator
reads the file once and passes its text in via ``source_text``; this module only
pattern-matches.

What it recognises
------------------

Kotlin web code shows up in two dominant styles, and this extractor handles both.

**1. Spring annotations.** Kotlin Spring controllers use the very same annotation
surface as Java, so the class-level base path is joined with each method-level
mapping exactly as in the Java extractor::

    @RestController
    @RequestMapping("/api/v1")
    class UserController {
        @GetMapping("/users/{id}")   -> GET    /api/v1/users/{id}
        @PostMapping("/users")       -> POST   /api/v1/users
        @PutMapping("/users/{id}")   -> PUT    /api/v1/users/{id}
        @PatchMapping("/users/{id}") -> PATCH  /api/v1/users/{id}
        @DeleteMapping("/users/{id}")-> DELETE /api/v1/users/{id}
    }

Method-level ``@RequestMapping`` is also read; its verbs come from a
``method = [RequestMethod.GET, ...]`` (Kotlin array literal) or a bare
``method = RequestMethod.GET`` attribute. When it lists no verb, the ``methods``
tuple is left empty and the orchestrator defaults it to GET (Req 3.3).

The Spring half reuses the Java extractor's path helpers (``_path_from_args``,
``_base_path``, ``_join``, and the mapping/class regexes) verbatim — importing
them read-only rather than re-deriving the base-path-join logic — so Kotlin Spring
controllers behave identically to Java ones. ``dast/endpoints/languages/java.py``
is not modified.

**2. Ktor routing DSL.** Ktor declares routes as verb-named DSL functions whose
first argument is the path string literal::

    get("/users")        -> GET    /users
    post("/users/{id}")  -> POST   /users/{id}
    put("/users/{id}")   -> PUT    /users/{id}
    patch("/users/{id}") -> PATCH  /users/{id}
    delete("/users/{id}")-> DELETE /users/{id}

The verb is the DSL function name and the path is its string-literal argument.

Design notes / limitations
--------------------------

- **Ktor ``route("/x") { ... }`` prefixes are ignored (v1).** Only the leaf
  ``get``/``post``/``put``/``patch``/``delete`` calls are captured, with their
  literal path exactly as written. Routes nested under a ``route(...)`` block are
  therefore emitted *without* the enclosing prefix — a deliberate, documented
  simplification. Resolving nested prefixes is future work.
- **Verbatim paths.** Spring path variables (``{id}``) and Ktor path parameters
  (``{id}``) are left as declared on the :class:`~dast.endpoints.base.RawRoute`;
  the orchestrator's normaliser collapses dynamic segments to the shared ``{id}``
  placeholder (Req 4), so this extractor does not templatise.

Requirements traced: 2.1, 2.2, 2.5, 3.1, 3.2, 3.3, 1.5, 1.6, 1.7, 1.8.
"""

from __future__ import annotations

import os
import re

from dast.endpoints.base import RawRoute

# Reuse the Java extractor's Spring helpers read-only (java.py is not modified).
# Kotlin Spring controllers use the identical annotation surface, so the
# base-path-join logic is shared rather than re-derived.
from dast.endpoints.languages.java import (
    _CLASS_DECL,
    _MAPPING,
    _REQUEST_METHOD,
    _VERB_ANNOTATIONS,
    _base_path,
    _join,
    _path_from_args,
)

#: Extensions this extractor claims. Decided from the path alone (Req 2.2); the
#: file contents are never read by :meth:`KotlinExtractor.matches`.
_EXTENSIONS: frozenset[str] = frozenset({".kt"})

#: One Ktor routing-DSL leaf call: ``<verb>("<path>")``. The verb is the DSL
#: function name; the path is the first double-quoted string literal argument.
#: A word boundary in front keeps ``get``/``post``/… from matching the tails of
#: longer identifiers (e.g. ``forget(``). ``discover`` computes the 1-based line
#: from each match's start offset (Req 3.1).
_KTOR_ROUTE = re.compile(
    r"""
    \b(?P<verb>get|post|put|patch|delete)   # Ktor DSL verb function
    \s*\(\s*
    "(?P<path>[^"]*)"                        # first string-literal argument = path
    """,
    re.VERBOSE,
)


class KotlinExtractor:
    """Recognise Spring-annotation and Ktor-DSL routes in ``.kt`` source (Req 2.1).

    Duck-typed against :class:`dast.endpoints.base.LanguageExtractor`: it exposes
    a ``language`` label plus ``matches`` and ``discover``, so it needs no shared
    base class. Adding this extractor leaves every other extractor untouched
    (Req 2.5).
    """

    #: Stable label recorded in the run's extraction evidence.
    language: str = "kotlin"

    def matches(self, source_path: str) -> bool:
        """Return ``True`` for ``.kt`` files (by extension only).

        Cheap and static: the decision is made from the path's extension alone
        and never reads the file (Req 2.2).
        """
        return os.path.splitext(source_path)[1].lower() in _EXTENSIONS

    def discover(self, source_text: str, *, source_path: str) -> list[RawRoute]:
        """Return the Kotlin Route_Declarations found in ``source_text``.

        Pure and side-effect free: a regex scan over the already-read text. It
        never executes, imports, evaluates, or invokes the source (Req 1.5-1.8).

        Spring method-level mappings each yield one :class:`RawRoute` per HTTP
        verb, carrying the class base joined with the method sub-path; the
        class-level ``@RequestMapping`` supplies the base and is not itself
        emitted. Ktor DSL calls each yield one :class:`RawRoute` with the verb
        from the function name and the literal path. Every route records the
        1-based line the declaration begins on (Req 3.1, 3.2).
        """
        routes: list[RawRoute] = []
        routes.extend(self._discover_spring(source_text))
        routes.extend(self._discover_ktor(source_text))
        return routes

    @staticmethod
    def _discover_spring(source_text: str) -> list[RawRoute]:
        """Spring annotations — mirrors the Java extractor via shared helpers."""
        class_decl = _CLASS_DECL.search(source_text)
        class_pos = class_decl.start() if class_decl else len(source_text)
        base = _base_path(source_text, class_pos)

        routes: list[RawRoute] = []
        for match in _MAPPING.finditer(source_text):
            ann = match.group("ann")
            args = match.group("args")

            # The class-level @RequestMapping (before the class token) is the base
            # path, not an endpoint — skip it here.
            if ann == "RequestMapping" and match.start() < class_pos:
                continue

            full_path = _join(base, _path_from_args(args))
            line = source_text.count("\n", 0, match.start()) + 1

            if ann in _VERB_ANNOTATIONS:
                methods: tuple[str, ...] = (_VERB_ANNOTATIONS[ann],)
            else:
                # Method-level @RequestMapping: verbs come from
                # method = [RequestMethod.*] (or a bare RequestMethod.*); none
                # listed -> empty tuple so the orchestrator defaults to GET.
                methods = tuple(_REQUEST_METHOD.findall(args or ""))

            routes.append(RawRoute(methods=methods, raw_path=full_path, line=line))
        return routes

    @staticmethod
    def _discover_ktor(source_text: str) -> list[RawRoute]:
        """Ktor routing DSL — leaf verb calls only (nested ``route(...)`` ignored)."""
        routes: list[RawRoute] = []
        for match in _KTOR_ROUTE.finditer(source_text):
            verb = match.group("verb").upper()
            raw_path = match.group("path")
            line = source_text.count("\n", 0, match.start()) + 1
            routes.append(RawRoute(methods=(verb,), raw_path=raw_path, line=line))
        return routes
