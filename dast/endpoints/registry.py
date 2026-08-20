"""The Language_Extractor registry: the ordered set of extractors one run applies.

Registration is a plain, ordered list resolved once per call, mirroring how the
DAST runner builds its tool set in ``dast.runner.default_adapters``. Each entry
recognises Route_Declarations for exactly one language or web framework (Req 2.1),
and adding a language means appending one more extractor here — no existing
extractor is modified (Req 2.5).

The extractors are duck-typed against
:class:`dast.endpoints.base.LanguageExtractor` (they expose ``language``,
``matches`` and ``discover`` without inheriting a shared base), so the returned
list is typed as ``list[LanguageExtractor]``.

Requirements traced: 2.1, 2.5.
"""

from __future__ import annotations

from dast.endpoints.base import LanguageExtractor
from dast.endpoints.languages.go import GoExtractor
from dast.endpoints.languages.java import JavaExtractor
from dast.endpoints.languages.javascript import JavaScriptExtractor
from dast.endpoints.languages.kotlin import KotlinExtractor
from dast.endpoints.languages.php import PhpExtractor
from dast.endpoints.languages.python import PythonExtractor
from dast.endpoints.languages.ruby import RubyExtractor
from dast.endpoints.languages.rust import RustExtractor


def default_language_extractors() -> list[LanguageExtractor]:
    """Return the ordered set of registered Language_Extractors for one run.

    One extractor per language/framework (Req 2.1), resolved fresh on each call
    (analogous to :func:`dast.runner.default_adapters`). Registering an additional
    language means appending one more extractor to this list, leaving every
    existing extractor unchanged (Req 2.5).
    """
    return [
        PythonExtractor(),
        JavaScriptExtractor(),
        GoExtractor(),
        RubyExtractor(),
        JavaExtractor(),
        PhpExtractor(),
        KotlinExtractor(),
        RustExtractor(),
    ]
