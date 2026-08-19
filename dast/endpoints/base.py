"""The extraction extension point: the ``LanguageExtractor`` contract and its
pre-normalisation output, :class:`RawRoute`.

Adding support for a new language or web framework means writing one plugin that
satisfies :class:`LanguageExtractor` and registering it — no existing extractor is
touched (Req 2.5). Each registered extractor recognises Route_Declarations for
*exactly one* language or framework (Req 2.1).

The contract is duck-typed against a :class:`~typing.Protocol`, mirroring how
``DastAdapter`` is duck-typed in the runner: any object exposing the right
attributes and methods qualifies, so extractors need not inherit from a shared
base class.

**Static only.** An extractor *reads* source text; it never runs it. Every
implementation of :meth:`LanguageExtractor.discover` MUST NOT execute, import,
evaluate, or invoke the source it is handed (Req 1.5-1.8). The Python extractor
uses :func:`ast.parse` (which builds a syntax tree without running the module);
the others scan lines/tokens with regexes. There is no runtime boot, no framework
loading, no ``eval``/``exec``/``import`` of target code.

Requirements traced: 2.1, 2.5, 1.5, 1.6, 1.7, 1.8.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class RawRoute:
    """A Route_Declaration as read from source, *before* normalisation.

    This is the raw output of a :class:`LanguageExtractor`: the framework-native
    path exactly as it appears in the source, the verbs the declaration
    registered (in their native case), and the 1-based line the declaration
    begins on. Turning this into one or more :class:`~dast.endpoints.models.ExtractedEndpoint`
    — path templatised to the shared ``{id}`` placeholder, methods uppercased and
    filtered to the supported set, one endpoint per method — is the orchestrator's
    job, not the extractor's.
    """

    #: HTTP verbs registered by this declaration, in framework-native case. An
    #: empty tuple means the declaration specified *no explicit method*, which the
    #: orchestrator defaults to ``GET`` (Req 3.3).
    methods: tuple[str, ...]
    #: Framework-native path exactly as declared, e.g. ``"/users/:id"``,
    #: ``"/users/<int:id>"``, or ``"/users/{id}"``. Normalisation to the shared
    #: ``{id}`` template happens later (Req 4).
    raw_path: str
    #: 1-based line at which the Route_Declaration begins (Req 3.1).
    line: int
    #: Optional query-parameter names the extractor could read from the
    #: declaration. Path parameters are *not* listed here — they are derived from
    #: the path during normalisation (Req 3.4). Defaults to no query parameters.
    query_parameters: tuple[str, ...] = field(default=())


@runtime_checkable
class LanguageExtractor(Protocol):
    """Recognises Route_Declarations for exactly one language/framework (Req 2.1).

    Duck-typed against this Protocol, mirroring ``DastAdapter``: any object with a
    ``language`` attribute plus ``matches`` and ``discover`` methods qualifies as a
    Language_Extractor without inheriting from a shared base. New languages are
    added by writing one more such object and registering it, leaving every
    existing extractor unchanged (Req 2.5).
    """

    #: Stable language/framework label, recorded in
    #: :attr:`dast.endpoints.models.ExtractionActivity.languages` for the run's
    #: evidence. For example ``"python"``, ``"javascript"``, ``"go"``, ``"ruby"``.
    language: str

    def matches(self, source_path: str) -> bool:
        """Return ``True`` when this extractor handles the given file.

        The decision is made from the path alone — by extension or filename — and
        is cheap and static: it never reads or parses the file's contents. A
        single file may match more than one registered extractor; when it does,
        the orchestrator applies every matching extractor and combines their
        routes (Req 2.4). A file that matches no extractor is skipped without an
        error (Req 2.3).
        """
        ...

    def discover(self, source_text: str, *, source_path: str) -> list[RawRoute]:
        """Return the Route_Declarations found in already-read ``source_text``.

        Pure and side-effect free. This method MUST NOT execute, import, evaluate,
        or invoke the source it is handed (Req 1.5-1.8): the Python extractor uses
        :func:`ast.parse` to build a syntax tree without running the module; the
        other extractors scan lines/tokens with regexes. No file I/O and no
        network I/O happen here — the orchestrator has already read the file and
        passes its text in via ``source_text``, with ``source_path`` supplied only
        for context (e.g. deciding a sub-framework by filename).

        Raising is allowed: the orchestrator catches any exception and skips the
        offending file, continuing with the rest of the repository (Req 10.1).
        """
        ...
