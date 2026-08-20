"""Unit tests for the Rust endpoint extractor (``RustExtractor``).

Example-based (not property-based) checks that the extractor:

- reads actix-web / Rocket attribute macros (``#[get("/path")]`` etc.),
- reads the verb from an actix ``#[route("/path", method = "X")]``,
- reads axum / actix ``.route("/path", verb(...))`` builder calls,
- emits the framework-native path verbatim (the orchestrator normalises it), and
- claims ``.rs`` files (and only those) via ``matches``.

The first case parses the on-disk fixture ``routes.rs``; the rest use inline
snippets.
"""

from pathlib import Path

from dast.endpoints.languages.rust import RustExtractor

# security_samples/multilang/routes.rs, relative to the repo root
# (two parents up from tests/dast/).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE = _REPO_ROOT / "security_samples" / "multilang" / "routes.rs"


def _pairs(routes):
    """Flatten discovered RawRoutes into a set of ``(method, raw_path)`` pairs."""
    pairs = set()
    for route in routes:
        for method in route.methods:
            pairs.add((method, route.raw_path))
    return pairs


def test_fixture_covers_actix_route_macro_and_axum_builder():
    text = _FIXTURE.read_text(encoding="utf-8")

    routes = RustExtractor().discover(text, source_path=str(_FIXTURE))

    assert _pairs(routes) == {
        ("GET", "/users/{id}"),
        ("POST", "/users"),
        ("PUT", "/legacy"),
        ("GET", "/health"),
        ("DELETE", "/items/{id}"),
    }


def test_actix_attribute_macros():
    source = """
    #[get("/ping")]
    async fn ping() -> impl Responder { "pong" }

    #[patch("/things/{id}")]
    async fn patch_thing() -> impl Responder { "ok" }
    """
    routes = RustExtractor().discover(source, source_path="handlers.rs")
    assert _pairs(routes) == {("GET", "/ping"), ("PATCH", "/things/{id}")}


def test_rocket_angle_path_is_emitted_verbatim():
    # Rocket uses <id> angle params; the extractor emits them unchanged and the
    # orchestrator's normaliser collapses them to {id} later.
    source = '#[get("/users/<id>")]\nfn user(id: u32) {}\n'
    routes = RustExtractor().discover(source, source_path="rocket.rs")
    assert _pairs(routes) == {("GET", "/users/<id>")}


def test_axum_route_builder_verbs():
    source = """
    let app = Router::new()
        .route("/a", get(a))
        .route("/b", post(b))
        .route("/c/:id", put(c));
    """
    routes = RustExtractor().discover(source, source_path="main.rs")
    assert _pairs(routes) == {
        ("GET", "/a"),
        ("POST", "/b"),
        ("PUT", "/c/:id"),
    }


def test_actix_web_qualified_route_builder():
    source = 'cfg.route("/submit", web::post().to(submit));\n'
    routes = RustExtractor().discover(source, source_path="config.rs")
    assert _pairs(routes) == {("POST", "/submit")}


def test_line_numbers_are_one_based():
    source = '#[get("/a")]\nfn a() {}\n#[post("/b")]\nfn b() {}\n'
    routes = RustExtractor().discover(source, source_path="h.rs")
    by_path = {r.raw_path: r.line for r in routes}
    assert by_path["/a"] == 1
    assert by_path["/b"] == 3


def test_matches_rust_files_only():
    extractor = RustExtractor()
    assert extractor.matches("src/main.rs") is True
    assert extractor.matches("src/handlers/users.RS") is True
    assert extractor.matches("app/main.py") is False
    assert extractor.matches("handler.go") is False


def test_language_label_is_rust():
    assert RustExtractor().language == "rust"
