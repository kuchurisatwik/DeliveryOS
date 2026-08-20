"""PHP route extractor (Laravel facade routes / Symfony attribute routes).

Reads PHP Route_Declarations out of ``.php`` source *without executing it*. The
whole extractor is a line/token regex scan: it never imports, compiles,
evaluates, or otherwise runs the file it is handed (Req 1.5-1.8). The orchestrator
reads the file once and passes its text in via ``source_text``; this module only
pattern-matches.

What it recognises
------------------

Two dominant PHP routing styles are covered.

**Laravel facade routes.** The ``Route`` facade registers a verb and a path::

    Route::get('/users', ...)            -> GET    /users
    Route::post('/users/{id}', ...)      -> POST   /users/{id}
    Route::put('/users/{id}', ...)       -> PUT    /users/{id}
    Route::patch('/users/{id}', ...)     -> PATCH  /users/{id}
    Route::delete('/users/{id}', ...)    -> DELETE /users/{id}
    Route::options('/users', ...)        -> OPTIONS /users
    Route::any('/users', ...)            -> (no verb -> GET default)

    Route::match(['get', 'post'], '/x', ...)  -> GET, POST  /x

The verb is the facade method name. ``Route::any`` registers *all* verbs, which
this extractor represents with an empty ``methods`` tuple so the orchestrator
applies its ``GET`` default (Req 3.3). ``Route::match([...], '/x', ...)`` takes
its verbs from the array and the path from the string literal that follows it.

**Symfony attribute / annotation routes.** The path is the first string literal;
verbs come from an optional ``methods:`` / ``methods=`` clause::

    #[Route('/users/{id}', methods: ['GET', 'POST'])]   -> GET, POST /users/{id}
    #[Route('/users')]                                  -> (no verb -> GET default)
    @Route("/users/{id}", methods={"GET"})              -> GET /users/{id}

Design notes
------------

- **Path verbatim.** Laravel and Symfony already use the ``{id}`` brace form, so
  the framework-native path is returned unchanged on the
  :class:`~dast.endpoints.base.RawRoute`; collapsing dynamic segments to the
  shared ``{id}`` placeholder is the orchestrator's job (Req 4), not this
  extractor's.
- **String literals** may use single or double quotes; both are accepted.
- **Native verb case is fine.** Laravel spells verbs lowercase (``get``),
  Symfony uppercase (``GET``); either is emitted as-is because the orchestrator
  uppercases and filters (Req 3.3).
- **One RawRoute per declaration.** Each Laravel facade call and each Symfony
  ``Route`` attribute yields exactly one :class:`RawRoute`.

Requirements traced: 2.1, 2.2, 3.1, 3.2, 3.3, 1.5, 1.6, 1.7, 1.8.
"""

from __future__ import annotations

import os
import re

from dast.endpoints.base import RawRoute

#: Extensions this extractor claims. Decided from the path alone (Req 2.2); the
#: file contents are never read by :meth:`PhpExtractor.matches`.
_EXTENSIONS: frozenset[str] = frozenset({".php"})

#: Laravel verb-named facade routes: the method name is the HTTP verb. ``any``
#: is included so it can be mapped to an empty methods tuple (all verbs -> the
#: orchestrator's GET default). The path is the first string literal argument,
#: single- or double-quoted.
_LARAVEL_VERB_RE = re.compile(
    r"""
    Route\s*::\s*
    (?P<verb>get|post|put|patch|delete|options|any)   # facade verb method
    \s*\(\s*
    (?P<quote>['"])                                    # opening quote
    (?P<path>(?:\\.|(?!(?P=quote)).)*)                 # path literal contents
    (?P=quote)                                         # matching closing quote
    """,
    re.VERBOSE | re.IGNORECASE,
)

#: Laravel ``Route::match([...], '/path', ...)``: verbs come from the array, the
#: path is the string literal that follows it.
_LARAVEL_MATCH_RE = re.compile(
    r"""
    Route\s*::\s*match\s*\(\s*
    \[(?P<verbs>[^\]]*)\]                               # verb array
    \s*,\s*
    (?P<quote>['"])                                     # opening quote
    (?P<path>(?:\\.|(?!(?P=quote)).)*)                  # path literal contents
    (?P=quote)                                          # matching closing quote
    """,
    re.VERBOSE | re.IGNORECASE,
)

#: Symfony attribute (``#[Route(...)]``) or annotation (``@Route(...)``). The path
#: is the first string literal; the (optional) methods clause is captured whole.
_SYMFONY_RE = re.compile(
    r"""
    (?:\#\[\s*Route|@Route)                             # attribute or annotation
    \s*\(\s*
    (?P<quote>['"])                                     # opening quote
    (?P<path>(?:\\.|(?!(?P=quote)).)*)                  # path literal contents
    (?P=quote)                                          # matching closing quote
    (?P<rest>[^)]*)                                     # remaining args (methods:)
    \)
    """,
    re.VERBOSE,
)

#: A ``methods:`` (attribute) or ``methods=`` (annotation) clause with its list,
#: bracketed by ``[...]`` or ``{...}``.
_SYMFONY_METHODS_RE = re.compile(
    r"methods\s*[:=]\s*[\[{](?P<verbs>[^\]}]*)[\]}]"
)

#: A single quoted verb inside a verb list, e.g. ``'GET'`` or ``"post"``.
_QUOTED_VERB_RE = re.compile(r"""['"]\s*(\w+)\s*['"]""")


def _line_of(source_text: str, offset: int) -> int:
    """Return the 1-based line at which ``offset`` falls (Req 3.1)."""
    return source_text.count("\n", 0, offset) + 1


def _verbs_from_list(text: str) -> tuple[str, ...]:
    """Return the verbs named in a quoted verb list, in declaration order.

    Native case is preserved; the orchestrator uppercases and filters (Req 3.3).
    """
    return tuple(_QUOTED_VERB_RE.findall(text))


class PhpExtractor:
    """Recognise Laravel and Symfony routes in ``.php`` source (Req 2.1).

    Duck-typed against :class:`dast.endpoints.base.LanguageExtractor`: it exposes
    a ``language`` label plus ``matches`` and ``discover``, so it needs no shared
    base class. Adding this extractor leaves every other extractor untouched
    (Req 2.5).
    """

    #: Stable label recorded in the run's extraction evidence.
    language: str = "php"

    def matches(self, source_path: str) -> bool:
        """Return ``True`` for ``.php`` files (by extension only).

        Cheap and static: the decision is made from the path's extension alone
        and never reads the file (Req 2.2).
        """
        return os.path.splitext(source_path)[1].lower() in _EXTENSIONS

    def discover(self, source_text: str, *, source_path: str) -> list[RawRoute]:
        """Return the PHP Route_Declarations found in ``source_text``.

        Pure and side-effect free: a regex scan over the already-read text. It
        never executes, imports, evaluates, or invokes the source (Req 1.5-1.8).

        Each Laravel facade call and each Symfony ``Route`` attribute yields one
        :class:`RawRoute` carrying the framework-native path verbatim and the
        1-based line the declaration begins on (Req 3.1). ``Route::any`` and a
        Symfony route with no ``methods`` clause leave ``methods`` empty so the
        orchestrator defaults to ``GET`` (Req 3.3).
        """
        routes: list[RawRoute] = []

        # Laravel: Route::match(['get','post'], '/x', ...) — handle before the
        # verb pattern so the ``match`` keyword is not mistaken for a verb.
        for m in _LARAVEL_MATCH_RE.finditer(source_text):
            methods = _verbs_from_list(m.group("verbs"))
            routes.append(
                RawRoute(
                    methods=methods,
                    raw_path=m.group("path"),
                    line=_line_of(source_text, m.start()),
                )
            )

        # Laravel: Route::get/post/put/patch/delete/options/any('/path', ...).
        for m in _LARAVEL_VERB_RE.finditer(source_text):
            verb = m.group("verb")
            # ``any`` registers all verbs -> empty tuple -> orchestrator GET
            # default (Req 3.3). Every other verb is emitted as declared.
            methods: tuple[str, ...] = () if verb.lower() == "any" else (verb,)
            routes.append(
                RawRoute(
                    methods=methods,
                    raw_path=m.group("path"),
                    line=_line_of(source_text, m.start()),
                )
            )

        # Symfony: #[Route('/path', methods: [...])] and @Route("/path", ...).
        for m in _SYMFONY_RE.finditer(source_text):
            methods_clause = _SYMFONY_METHODS_RE.search(m.group("rest") or "")
            methods = (
                _verbs_from_list(methods_clause.group("verbs"))
                if methods_clause
                else ()
            )
            routes.append(
                RawRoute(
                    methods=methods,
                    raw_path=m.group("path"),
                    line=_line_of(source_text, m.start()),
                )
            )

        return routes
