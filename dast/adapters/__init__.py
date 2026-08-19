"""DAST scanner adapters.

Each adapter wraps one tool and returns shared :class:`~app.security.models.Finding`
objects, following the same split the SAST adapters use: ``scan()`` is impure (it
runs the tool), ``parse()`` is a pure classmethod over the decoded payload so it can
be unit-tested against a saved file with no network and no subprocess.
"""

from dast.adapters.nuclei_adapter import NucleiAdapter
from dast.adapters.schemathesis_adapter import SchemathesisAdapter
from dast.adapters.zap_adapter import ZapAdapter

__all__ = ["NucleiAdapter", "SchemathesisAdapter", "ZapAdapter"]
