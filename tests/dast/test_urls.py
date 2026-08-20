"""URL normalisation tests — the foundation of a usable baseline.

If these break, every rescan reports the same bug thousands of times over and the
"only show me what's new" diff becomes noise.
"""

from dast.urls import endpoint_identity, normalize_path

SPEC = ("/api/users/{user_id}", "/api/users/me", "/api/users/{user_id}/orders/{order_id}", "/health")


def test_numeric_segments_collapse():
    assert normalize_path("/api/users/12345") == "/api/users/{id}"


def test_uuid_segments_collapse():
    path = "/api/items/1b4e28ba-2fa1-11d2-883f-0016d3cca427/tags"
    assert normalize_path(path) == "/api/items/{id}/tags"


def test_long_hex_segments_collapse():
    assert normalize_path("/blobs/9f86d081884c7d65") == "/blobs/{id}"


def test_route_names_are_never_collapsed():
    assert normalize_path("/api/users/profile") == "/api/users/profile"


def test_two_ids_on_one_endpoint_produce_one_identity():
    a = normalize_path("/api/users/1/orders/99")
    b = normalize_path("/api/users/2/orders/17")
    assert a == b == "/api/users/{id}/orders/{id}"


def test_spec_templates_win_over_heuristics():
    # The spec knows ``user_id`` is a parameter even when the value looks like a word.
    assert normalize_path("/api/users/alice", SPEC) == "/api/users/{user_id}"


def test_literal_spec_route_beats_the_more_general_template():
    # ``/users/me`` must not be swallowed by ``/users/{user_id}``.
    assert normalize_path("/api/users/me", SPEC) == "/api/users/me"


def test_host_is_stripped_so_moving_staging_does_not_re_id_findings():
    a = endpoint_identity("https://staging.example.com/api/users/1")
    b = endpoint_identity("https://staging-blue.example.com/api/users/2")
    assert a == b == "/api/users/{id}"


def test_query_string_is_dropped():
    assert endpoint_identity("https://x.test/search?q=1&page=2") == "/search"


def test_root_url():
    assert endpoint_identity("https://x.test") == "/"
    assert endpoint_identity("https://x.test/") == "/"


def test_non_http_target_is_passed_through():
    # Network/TLS templates report ``host:port``; there is no path to templatise.
    assert endpoint_identity("staging.example.com:5432") == "staging.example.com:5432"
