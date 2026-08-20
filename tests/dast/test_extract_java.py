"""Unit tests for the Java/Spring endpoint extractor (``JavaExtractor``).

Example-based (not property-based) checks that the extractor:

- joins the class-level ``@RequestMapping`` base path onto each method mapping,
- reads the HTTP verb from ``@GetMapping``/``@PostMapping``/... and from a
  method-level ``@RequestMapping(method = RequestMethod.X)``,
- treats method paths as absolute when there is no class-level base, and
- claims ``.java`` files (and only those) via ``matches``.

The first case parses the on-disk fixture ``SpringController.java``; the second
uses an inline snippet.
"""

from pathlib import Path

from dast.endpoints.languages.java import JavaExtractor

# security_samples/multilang/SpringController.java, relative to the repo root
# (two parents up from tests/dast/).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE = _REPO_ROOT / "security_samples" / "multilang" / "SpringController.java"


def _method_path_pairs(routes):
    """Flatten routes into a ``{(METHOD, raw_path)}`` set for easy comparison."""
    pairs = set()
    for route in routes:
        for method in route.methods:
            pairs.add((method, route.raw_path))
    return pairs


def test_fixture_joins_base_path_with_method_paths():
    text = _FIXTURE.read_text(encoding="utf-8")

    routes = JavaExtractor().discover(text, source_path=str(_FIXTURE))

    expected = {
        ("GET", "/api/v1/items"),
        ("GET", "/api/v1/items/{id}"),
        ("POST", "/api/v1/items"),
        ("PATCH", "/api/v1/items/{id}"),
        ("DELETE", "/api/v1/items/{id}"),
        ("POST", "/api/v1/items/search"),
    }
    assert _method_path_pairs(routes) == expected


def test_no_class_level_base_yields_absolute_method_paths():
    source = """
    package com.example.api;

    import org.springframework.web.bind.annotation.GetMapping;
    import org.springframework.web.bind.annotation.PostMapping;
    import org.springframework.web.bind.annotation.RestController;

    @RestController
    public class RootController {

        @GetMapping("/health")
        public String health() {
            return "ok";
        }

        @PostMapping("/login")
        public Token login(@RequestBody Credentials creds) {
            return service.login(creds);
        }
    }
    """

    routes = JavaExtractor().discover(source, source_path="RootController.java")

    assert _method_path_pairs(routes) == {
        ("GET", "/health"),
        ("POST", "/login"),
    }


def test_matches_java_files_only():
    extractor = JavaExtractor()
    assert extractor.matches("src/main/java/com/example/ItemController.java") is True
    assert extractor.matches("app/services/handler.py") is False
