"""Static endpoint extraction for the DAST service.

This package reads HTTP endpoints out of a Target_Repository's *source code*
(never by executing it) and produces a normalised, deduplicated inventory that
seeds the ZAP and Schemathesis scanners through the existing
``DastScope.spec_paths`` contract.

Only the data models are re-exported here; the extractor, per-language plugins,
normalisation, dedup, reconciliation, and synthesis land in later modules.
"""

from __future__ import annotations

from dast.endpoints.models import (
    SUPPORTED_METHODS,
    EndpointInventory,
    EndpointParameter,
    ExtractedEndpoint,
    ExtractionActivity,
    ExtractionError,
    ExtractionResult,
    ParameterKind,
)

__all__ = [
    "SUPPORTED_METHODS",
    "EndpointInventory",
    "EndpointParameter",
    "ExtractedEndpoint",
    "ExtractionActivity",
    "ExtractionError",
    "ExtractionResult",
    "ParameterKind",
]
