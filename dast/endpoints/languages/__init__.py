"""Per-language ``LanguageExtractor`` plugins for endpoint extraction.

Each module in this package contributes exactly one extractor that recognises
Route_Declarations for a single language or web framework (Req 2.1). Adding a
language means adding one module here and registering it — no existing extractor
is touched (Req 2.5).
"""

from __future__ import annotations
