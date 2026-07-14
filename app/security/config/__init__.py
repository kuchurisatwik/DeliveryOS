"""Per-repository configuration resolution for the security pipeline.

Exposes :class:`ConfigResolver`, which layers per-repository ``Repo_Config``
overrides on top of the existing global ``app.config.settings`` and produces a
single immutable :class:`~app.security.models.ResolvedConfig` consumed by every
layer (Requirement 15).
"""

from __future__ import annotations

from app.security.config.repo_config import ConfigResolver

__all__ = ["ConfigResolver"]
