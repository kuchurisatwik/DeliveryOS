"""Ruby route discovery for endpoint extraction (Sinatra and Rails).

Recognises the two common Ruby route-declaration shapes with a pure line/token
regex scan — the source is **never** executed, imported, evaluated, or invoked
(Req 1.5-1.8):

- **Sinatra**: a block route whose verb leads the line, e.g.::

      get "/u/:id" do
      post '/x' do |params|

- **Rails**: a routes-file entry that maps a verb + path to a controller
  action, e.g.::

      get "/u/:id" => "users#show"
      post "/x", to: "widgets#create"

Both shapes begin (after optional indentation) with one of the HTTP verbs
``get``/``post``/``put``/``patch``/``delete`` followed by a quoted path literal,
so a single anchored regex captures both. Each match yields one
:class:`~dast.endpoints.base.RawRoute` carrying that verb, the framework-native
path exactly as written, and the 1-based line the declaration begins on
(Req 3.1). Path templatising and method casing/expansion are the orchestrator's
job (Req 3, Req 4).

Requirements traced: 2.1, 2.2, 3.1, 3.2, 3.3, 1.5, 1.6, 1.7, 1.8.
"""

from __future__ import annotations

import re

from dast.endpoints.base import RawRoute

#: File extension this extractor handles, matched on ``source_path`` alone
#: (never by reading the file).
_RUBY_SUFFIX = ".rb"

#: A Ruby Route_Declaration: an HTTP verb leading the line (after optional
#: indentation) followed by a single- or double-quoted path literal. The same
#: pattern matches both the Sinatra block form (``get "/x" do``) and the Rails
#: mapping form (``get "/x" => "c#a"`` / ``get "/x", to: "c#a"``) because both
#: start ``verb "path"``.
#:
#: Anchoring at the line start with ``^\s*`` keeps this from matching verbs that
#: appear mid-expression or as substrings (``forget``, ``x.get``) and skips
#: commented-out lines (``# get "/x"``), where a ``#`` precedes the verb.
_ROUTE = re.compile(
    r"""^\s*                          # leading indentation only
        (get|post|put|patch|delete)   # HTTP verb (group 1), Ruby-native case
        \s+                           # at least one space before the path
        (['"])                        # opening quote (group 2)
        (.*?)                         # framework-native path (group 3)
        \2                            # matching closing quote
    """,
    re.VERBOSE,
)


class RubyExtractor:
    """Discovers Sinatra/Rails Route_Declarations in Ruby source (Req 2.1).

    Duck-typed against :class:`~dast.endpoints.base.LanguageExtractor`: exposes a
    ``language`` label plus :meth:`matches` and :meth:`discover`. Recognises
    exactly one language/framework family (Ruby web routes) and never touches any
    other extractor (Req 2.5).
    """

    #: Stable language label recorded in the run's Extraction_Activity evidence.
    language: str = "ruby"

    def matches(self, source_path: str) -> bool:
        """Return ``True`` for ``.rb`` files, decided from the path alone.

        Cheap and static — the file is never read here (Req 2.2). The match is by
        extension only, case-insensitively so ``Foo.RB`` is still handled.
        """
        return source_path.lower().endswith(_RUBY_SUFFIX)

    def discover(self, source_text: str, *, source_path: str) -> list[RawRoute]:
        """Return the Route_Declarations found in ``source_text``.

        Pure line/token regex scan (Req 1.5-1.8): the text is split into lines and
        each line is tested against :data:`_ROUTE`. Every match becomes one
        :class:`~dast.endpoints.base.RawRoute` with the single declared verb in
        its Ruby-native case, the path exactly as written, and the 1-based line
        number (Req 3.1, 3.2). No file or network I/O happens here.
        """
        routes: list[RawRoute] = []
        for index, line in enumerate(source_text.splitlines(), start=1):
            match = _ROUTE.match(line)
            if match is None:
                continue
            verb = match.group(1)
            raw_path = match.group(3)
            routes.append(
                RawRoute(methods=(verb,), raw_path=raw_path, line=index)
            )
        return routes
