"""DeliveryOS Security Pipeline package.

Net-new, security-specific modules for the four-layer security pipeline. The
deterministic core (models, normalization, deduplication, scoring, quality gate,
merge confidence) is expressed as pure functions over the immutable data models
defined in :mod:`app.security.models`; side-effecting boundaries are isolated
behind the Protocols in :mod:`app.security.protocols`.
"""
