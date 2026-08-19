# Feature: dast-schemathesis, Property 3: URL templatisation yields stable finding identity
"""Property 3 — URL templatisation yields stable finding identity.

*For any* endpoint template in ``spec_paths`` and any two concrete URLs that differ
only in their dynamic segments (e.g. ``/api/users/12345`` vs ``/api/users/67890``),
the ``Finding`` objects produced by :meth:`SchemathesisAdapter.parse` share the same
endpoint identity and therefore the same ``finding_id``.

The chain under test: ``parse()`` builds each finding's ``Location`` via
``make_web_location(url, method=..., spec_paths=...)`` (``dast/adapters/base.py``),
which calls ``endpoint_identity`` (``dast/urls.py``) to strip the host and templatise
dynamic path segments against the OpenAPI templates. The downstream identity used by
the normalisation layer, ``finding_id`` (``app/security/intelligence/normalize.py``),
hashes the rule identity + location, so a stable location means a stable id.

**Validates: Requirements 9.2**
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.security.intelligence.normalize import normalize
from dast.adapters.schemathesis_adapter import SchemathesisAdapter

from tests.dast._schemathesis_fakes import make_case, make_report

# The failure kinds parse() classifies; the choice is irrelevant to identity, so we
# vary it to prove templatisation stability holds across every finding kind.
_FAILED_CHECKS = (
    "not_a_server_error",
    "ignored_auth",
    "response_schema_conformance",
)

# HTTP methods — the method is part of the endpoint identity, so both concrete URLs
# must be invoked with the SAME method to isolate the templatisation effect.
_METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH")

# Route-name segments are drawn from lowercase letters only, so a literal segment can
# never look like a dynamic identifier (numeric / uuid / long-hex) and be templatised
# by the heuristic — keeping literal vs dynamic segments unambiguous.
_route_names = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=8)


@st.composite
def templated_endpoints(draw):
    """Generate a spec template + two concrete URLs differing only in dynamic segments.

    Returns ``(spec_path, url_a, url_b, method)`` where:

    * ``spec_path`` is an OpenAPI path template such as ``/api/users/{p0}/orders/{p1}``;
    * ``url_a`` / ``url_b`` are concrete URLs built from that template, sharing every
      literal segment and differing in every dynamic segment (distinct id values);
    * ``method`` is the HTTP verb both URLs are invoked with.

    At least one dynamic segment is always present, so the two URLs genuinely differ
    yet must still collapse to one identity.
    """
    # A plan of path segments: each is either a literal route name or a parameter.
    # ``True`` marks a dynamic (parameter) segment.
    n_segments = draw(st.integers(min_value=1, max_value=5))
    is_dynamic = draw(
        st.lists(st.booleans(), min_size=n_segments, max_size=n_segments)
    )
    # Guarantee at least one dynamic segment so the URLs actually differ.
    if not any(is_dynamic):
        idx = draw(st.integers(min_value=0, max_value=n_segments - 1))
        is_dynamic[idx] = True

    spec_segments: list[str] = []
    seg_a: list[str] = []
    seg_b: list[str] = []
    for i, dynamic in enumerate(is_dynamic):
        if dynamic:
            # Two distinct concrete id values for this parameter.
            id_a = draw(st.integers(min_value=0, max_value=10**9))
            id_b = draw(st.integers(min_value=0, max_value=10**9).filter(lambda v, a=id_a: v != a))
            spec_segments.append(f"{{p{i}}}")
            seg_a.append(str(id_a))
            seg_b.append(str(id_b))
        else:
            name = draw(_route_names)
            spec_segments.append(name)
            seg_a.append(name)
            seg_b.append(name)

    spec_path = "/" + "/".join(spec_segments)
    host = "https://target.example"
    url_a = host + "/" + "/".join(seg_a)
    url_b = host + "/" + "/".join(seg_b)
    method = draw(st.sampled_from(_METHODS))
    return spec_path, url_a, url_b, method


@settings(max_examples=200)
@given(
    endpoints=templated_endpoints(),
    failed_check=st.sampled_from(_FAILED_CHECKS),
    status_code=st.integers(min_value=200, max_value=599),
)
def test_property_03_templatisation_yields_stable_finding_identity(
    endpoints: tuple[str, str, str, str],
    failed_check: str,
    status_code: int,
) -> None:
    spec_path, url_a, url_b, method = endpoints
    spec_paths = (spec_path,)

    # Two reports identical in every respect except the concrete URL's dynamic
    # segments — same method, same failing check, same status.
    report_a = make_report(
        cases=[
            make_case(
                method=method,
                path=spec_path,
                uri=url_a,
                status_code=status_code,
                failed_checks=[failed_check],
            )
        ]
    )
    report_b = make_report(
        cases=[
            make_case(
                method=method,
                path=spec_path,
                uri=url_b,
                status_code=status_code,
                failed_checks=[failed_check],
            )
        ]
    )

    findings_a = SchemathesisAdapter.parse(report_a, spec_paths=spec_paths)
    findings_b = SchemathesisAdapter.parse(report_b, spec_paths=spec_paths)

    # Each report has exactly one failing case → exactly one finding.
    assert len(findings_a) == 1, findings_a
    assert len(findings_b) == 1, findings_b
    finding_a = findings_a[0]
    finding_b = findings_b[0]

    # The endpoint identity (method-prefixed templatised path) is stable across the
    # differing dynamic segments.
    assert finding_a.location == finding_b.location
    # The templatised path really is the OpenAPI template, not the concrete URL.
    assert finding_a.location.path == f"{method.upper()} {spec_path}"
    # The scanner-stable rule id (kind:endpoint:status) is identical.
    assert finding_a.rule_id == finding_b.rule_id

    # …and therefore the downstream finding_id is identical.
    assert normalize(finding_a).finding_id == normalize(finding_b).finding_id
