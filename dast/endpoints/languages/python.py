"""Python route extractor (Flask / FastAPI).

Recognises the decorator-based Route_Declarations of the two dominant Python web
frameworks and emits one :class:`~dast.endpoints.base.RawRoute` per declaration:

- Flask's method-less form ``@app.route("/users/<id>")`` (defaults to ``GET`` in
  the orchestrator, Req 3.3) and its explicit form
  ``@app.route("/users/<id>", methods=["GET", "POST"])``;
- the verb-named decorators shared by Flask 2+ and FastAPI —
  ``@app.get("/users/{id}")``, ``@app.post(...)``, ``@router.put(...)``,
  ``@router.delete(...)`` etc.; and
- FastAPI's ``@router.api_route("/x", methods=[...])`` explicit form.

**Static only.** Discovery uses :func:`ast.parse`, which builds a syntax tree
*without running the module* — the source is never executed, imported, evaluated,
or invoked (Req 1.5-1.8). Only string-literal paths and string-literal method
lists are read; anything computed at runtime (an f-string path, a variable list
of methods) is left for a real OpenAPI spec to describe and is skipped here.

Requirements traced: 2.1, 2.2, 3.1, 3.2, 3.3, 1.5, 1.6, 1.7, 1.8.
"""

from __future__ import annotations

import ast

from dast.endpoints.base import RawRoute

#: Verb-named route decorators. The decorator's attribute name *is* the HTTP
#: method (e.g. ``@app.get`` -> ``GET``). Kept broad on purpose — the orchestrator
#: filters to the supported set {GET, POST, PUT, PATCH, DELETE} (Req 3.5), so
#: recognising extra verbs here never leaks an unsupported endpoint downstream.
_VERB_DECORATORS: frozenset[str] = frozenset(
    {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
)

#: Route decorators that take their verbs from a ``methods=`` keyword rather than
#: from the decorator name: Flask's ``route`` and FastAPI's ``api_route``. With no
#: ``methods=`` present the declaration has no explicit method — an empty
#: :attr:`RawRoute.methods` tuple, which the orchestrator defaults to ``GET``
#: (Req 3.3).
_METHODS_KW_DECORATORS: frozenset[str] = frozenset({"route", "api_route"})

#: Keyword argument names under which the different frameworks pass the path when
#: it is not the first positional argument (Flask uses ``rule``; FastAPI ``path``).
_PATH_KEYWORDS: tuple[str, ...] = ("path", "rule")


def _string_constant(node: ast.expr | None) -> str | None:
    """Return the value of a string-literal ``node``, or ``None`` if it is not one."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _path_argument(call: ast.Call) -> str | None:
    """Return the declared path string of a route ``call``, or ``None``.

    Reads the first positional argument, falling back to a ``path=``/``rule=``
    keyword. Only string literals are accepted — a computed path cannot be
    resolved statically and is skipped.
    """
    if call.args:
        literal = _string_constant(call.args[0])
        if literal is not None:
            return literal

    for keyword in call.keywords:
        if keyword.arg in _PATH_KEYWORDS:
            literal = _string_constant(keyword.value)
            if literal is not None:
                return literal

    return None


def _methods_keyword(call: ast.Call) -> tuple[str, ...]:
    """Return the string verbs listed in a ``methods=`` keyword of ``call``.

    An absent ``methods=`` keyword, or one whose value is not a literal
    list/tuple/set, yields an empty tuple (no explicit method — Req 3.3). Verbs
    are returned in their framework-native case; the orchestrator uppercases and
    filters them.
    """
    for keyword in call.keywords:
        if keyword.arg != "methods":
            continue
        if isinstance(keyword.value, (ast.List, ast.Tuple, ast.Set)):
            verbs = [
                literal
                for element in keyword.value.elts
                if (literal := _string_constant(element)) is not None
            ]
            return tuple(verbs)
    return ()


def _route_from_decorator(decorator: ast.expr) -> RawRoute | None:
    """Turn a single decorator expression into a :class:`RawRoute`, or ``None``.

    Recognises ``<obj>.route(...)`` / ``<obj>.api_route(...)`` (verbs from
    ``methods=``) and the verb-named ``<obj>.get(...)`` / ``.post(...)`` etc.
    (verb from the decorator name). A decorator that is not a call, whose
    attribute is not a route attribute, or whose path is not a string literal
    returns ``None`` and is ignored.
    """
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    if not isinstance(func, ast.Attribute):
        return None

    attr = func.attr
    path = _path_argument(decorator)
    if path is None:
        return None

    if attr in _METHODS_KW_DECORATORS:
        methods = _methods_keyword(decorator)
    elif attr in _VERB_DECORATORS:
        methods = (attr,)
    else:
        return None

    return RawRoute(methods=methods, raw_path=path, line=decorator.lineno)


class PythonExtractor:
    """Discovers Flask/FastAPI route declarations from Python source.

    Satisfies the :class:`~dast.endpoints.base.LanguageExtractor` protocol by
    duck typing: it exposes ``language``, ``matches`` and ``discover`` without
    inheriting from a shared base.
    """

    language = "python"

    def matches(self, source_path: str) -> bool:
        """Return ``True`` for ``.py`` files, decided by extension alone.

        Cheap and static — the file's contents are never read here (per the
        :class:`LanguageExtractor` contract).
        """
        return source_path.endswith(".py")

    def discover(self, source_text: str, *, source_path: str) -> list[RawRoute]:
        """Return the route declarations found in ``source_text``.

        Parses the source into a syntax tree with :func:`ast.parse` (no
        execution/import/eval/invoke — Req 1.5-1.8) and walks every function's
        decorators, collecting one :class:`RawRoute` per recognised route
        decorator. A syntax error propagates to the orchestrator, which catches
        it and skips the file (Req 10.1).
        """
        tree = ast.parse(source_text)

        routes: list[RawRoute] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                route = _route_from_decorator(decorator)
                if route is not None:
                    routes.append(route)
        return routes
