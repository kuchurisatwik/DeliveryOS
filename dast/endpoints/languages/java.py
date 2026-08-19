"""Java route extractor (Spring MVC / Spring Boot).

Reads Spring's annotation-based Route_Declarations out of ``.java`` source
*without executing it*. The whole extractor is a line/token regex scan: it never
imports, compiles, evaluates, or otherwise runs the file it is handed
(Req 1.5-1.8). The orchestrator reads the file once and passes its text in via
``source_text``; this module only pattern-matches.

What it recognises
------------------

Spring controllers declare their HTTP surface with two layers of annotation:

- a **class-level base path** on ``@RequestMapping`` (usually alongside
  ``@RestController``)::

      @RestController
      @RequestMapping("/api/v1")
      public class LogAnalysisController { ... }

- **method-level mappings** that give the verb and the sub-path::

      @GetMapping("/logs")              -> GET    /api/v1/logs
      @GetMapping("/logs/{id}")         -> GET    /api/v1/logs/{id}
      @PostMapping("/logs")             -> POST   /api/v1/logs
      @PatchMapping("/clients/{id}")    -> PATCH  /api/v1/clients/{id}
      @DeleteMapping("/clients/{id}")   -> DELETE /api/v1/clients/{id}
      @RequestMapping(path = "/x", method = RequestMethod.PUT)  -> PUT /api/v1/x

The full framework-native path of each endpoint is the class base joined with the
method sub-path (``/api/v1`` + ``/logs`` -> ``/api/v1/logs``). Spring path
variables — ``{id}``, and the regex-constrained ``{entity:[a-z-]+}`` form — are
left verbatim on the :class:`~dast.endpoints.base.RawRoute`; the orchestrator's
normaliser collapses every dynamic segment to the shared ``{id}`` placeholder
(Req 4), so this extractor does not templatise.

Design notes
------------

- **Base path is class-scoped.** The ``@RequestMapping`` that sits *before* the
  ``class`` declaration is the base applied to every method mapping in the file;
  a ``@RequestMapping`` *after* the class token is treated as a method mapping
  (its verb read from ``method = RequestMethod.*``). One controller per file is
  assumed, matching Spring convention.
- **Verb from the annotation.** ``@GetMapping`` -> GET, ``@PostMapping`` -> POST,
  etc. A method-level ``@RequestMapping`` may list one or more
  ``RequestMethod.*`` verbs, each becoming its own endpoint; when it lists none,
  the ``methods`` tuple is left empty and the orchestrator defaults it to GET
  (Req 3.3) — a deliberate, documented simplification (Spring would map all
  verbs).
- **Path from the annotation.** The path is taken from a ``value = "..."`` or
  ``path = "..."`` attribute, else the first string literal argument. An
  annotation with no string literal maps to the base path alone. Paths built by
  string concatenation or constants cannot be resolved statically and degrade to
  the first literal fragment rather than crashing (Req 10.1).

Requirements traced: 2.1, 2.2, 3.1, 3.2, 3.3, 1.5, 1.6, 1.7, 1.8.
"""

from __future__ import annotations

import os
import re

from dast.endpoints.base import RawRoute

#: Extensions this extractor claims. Decided from the path alone (Req 2.2); the
#: file contents are never read by :meth:`JavaExtractor.matches`.
_EXTENSIONS: frozenset[str] = frozenset({".java"})

#: Verb-named method mappings: the annotation name determines the HTTP method.
_VERB_ANNOTATIONS: dict[str, str] = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "PatchMapping": "PATCH",
    "DeleteMapping": "DELETE",
}

#: The first ``class``/``interface``/``enum`` declaration — everything before it
#: is the class-level annotation block (where the base ``@RequestMapping`` lives).
_CLASS_DECL = re.compile(r"\b(?:class|interface|enum)\s+\w+")

#: Any mapping annotation with its (optional) argument list. ``args`` stops at the
#: first ``)`` which covers the single-line annotations Spring controllers use.
_MAPPING = re.compile(
    r"@(?P<ann>GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping|RequestMapping)"
    r"\b\s*(?:\(\s*(?P<args>[^)]*)\))?"
)

#: A class-level base ``@RequestMapping`` (used only to find the base path).
_BASE_MAPPING = re.compile(r"@RequestMapping\b\s*(?:\(\s*(?P<args>[^)]*)\))?")

#: ``value = "..."`` / ``path = "..."`` attribute inside an annotation's args.
_NAMED_PATH = re.compile(r"(?:value|path)\s*=\s*\"([^\"]*)\"")
#: Any double-quoted string literal (fallback path source / concatenation head).
_ANY_STRING = re.compile(r"\"([^\"]*)\"")
#: Each ``RequestMethod.VERB`` named in a method-level ``@RequestMapping``.
_REQUEST_METHOD = re.compile(r"RequestMethod\.(\w+)")


def _path_from_args(args: str | None) -> str:
    """Return the declared path from an annotation's argument text.

    Prefers an explicit ``value =``/``path =`` attribute, falls back to the first
    string literal, and returns ``""`` when the annotation has no string literal
    (which maps to the class base path alone).
    """
    if not args:
        return ""
    named = _NAMED_PATH.search(args)
    if named:
        return named.group(1)
    literal = _ANY_STRING.search(args)
    return literal.group(1) if literal else ""


def _base_path(source_text: str, class_pos: int) -> str:
    """Return the class-level base path, or ``""`` when there is none.

    The base is the last ``@RequestMapping`` occurring before ``class_pos`` (the
    class declaration), i.e. the annotation attached to the controller class.
    """
    base = ""
    for match in _BASE_MAPPING.finditer(source_text, 0, class_pos):
        base = _path_from_args(match.group("args"))
    return base


def _join(base: str, sub: str) -> str:
    """Join a class base path with a method sub-path.

    Slash hygiene (leading slash, collapsing ``//``) is finalised by the shared
    normaliser; this only has to produce a sensible framework-native join.
    """
    if not sub:
        return base or "/"
    if not base:
        return sub
    return base.rstrip("/") + "/" + sub.lstrip("/")


class JavaExtractor:
    """Recognise Spring MVC routes in ``.java`` source (Req 2.1).

    Duck-typed against :class:`dast.endpoints.base.LanguageExtractor`: it exposes
    a ``language`` label plus ``matches`` and ``discover``, so it needs no shared
    base class. Adding this extractor leaves every other extractor untouched
    (Req 2.5).
    """

    #: Stable label recorded in the run's extraction evidence.
    language: str = "java"

    def matches(self, source_path: str) -> bool:
        """Return ``True`` for ``.java`` files (by extension only).

        Cheap and static: the decision is made from the path's extension alone
        and never reads the file (Req 2.2).
        """
        return os.path.splitext(source_path)[1].lower() in _EXTENSIONS

    def discover(self, source_text: str, *, source_path: str) -> list[RawRoute]:
        """Return the Spring Route_Declarations found in ``source_text``.

        Pure and side-effect free: a regex scan over the already-read text. It
        never executes, imports, evaluates, or invokes the source (Req 1.5-1.8).

        Each method-level mapping yields one :class:`RawRoute` per HTTP verb,
        carrying the class base joined with the method sub-path and the 1-based
        line the annotation begins on (Req 3.1, 3.2). The class-level
        ``@RequestMapping`` supplies the base path and is not itself emitted.
        """
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
                # Method-level @RequestMapping: verbs come from method = {...};
                # none listed -> empty tuple so the orchestrator defaults to GET.
                methods = tuple(_REQUEST_METHOD.findall(args or ""))

            routes.append(
                RawRoute(methods=methods, raw_path=full_path, line=line)
            )
        return routes
