"""PHP route extractor tests — Laravel facade routes and Symfony attributes.

Example-based unit tests over inline PHP snippets (no fixture files). Each test
asserts the exact set of ``(method, raw_path)`` pairs the extractor discovers,
plus that ``matches`` is decided by extension alone.
"""

from dast.endpoints.languages.php import PhpExtractor


def _pairs(routes):
    """Flatten discovered RawRoutes into a set of (method, raw_path) pairs.

    A route with no explicit verb (empty ``methods``) contributes a single
    ``("", raw_path)`` pair so the "defaults to GET later" case is visible here.
    """
    pairs = set()
    for route in routes:
        if route.methods:
            for method in route.methods:
                pairs.add((method, route.raw_path))
        else:
            pairs.add(("", route.raw_path))
    return pairs


def test_matches_accepts_php_and_rejects_others():
    extractor = PhpExtractor()
    assert extractor.matches("routes/web.php") is True
    assert extractor.matches("src/Controller.PHP") is True
    assert extractor.matches("app/main.py") is False
    assert extractor.matches("handler.go") is False
    assert extractor.matches("README.md") is False


def test_laravel_verb_routes():
    source = """<?php
    Route::get('/users', 'UserController@index');
    Route::post('/users', 'UserController@store');
    Route::put('/users/{id}', 'UserController@replace');
    Route::patch('/users/{id}', 'UserController@update');
    Route::delete('/users/{id}', 'UserController@destroy');
    Route::options("/users", 'UserController@options');
    """
    routes = PhpExtractor().discover(source, source_path="routes/web.php")
    assert _pairs(routes) == {
        ("get", "/users"),
        ("post", "/users"),
        ("put", "/users/{id}"),
        ("patch", "/users/{id}"),
        ("delete", "/users/{id}"),
        ("options", "/users"),
    }


def test_laravel_match_route_takes_verbs_from_array():
    source = """<?php
    Route::match(['get', 'post'], '/search', 'SearchController@run');
    """
    routes = PhpExtractor().discover(source, source_path="routes/web.php")
    assert _pairs(routes) == {("get", "/search"), ("post", "/search")}


def test_laravel_any_route_has_no_explicit_method():
    source = """<?php
    Route::any('/webhook', 'WebhookController@handle');
    """
    routes = PhpExtractor().discover(source, source_path="routes/web.php")
    assert len(routes) == 1
    assert routes[0].methods == ()
    assert routes[0].raw_path == "/webhook"
    # No explicit verb -> orchestrator defaults to GET later.
    assert _pairs(routes) == {("", "/webhook")}


def test_symfony_attribute_route_with_methods():
    source = """<?php
    #[Route('/users/{id}', methods: ['GET', 'POST'])]
    public function show(int $id) {}
    """
    routes = PhpExtractor().discover(source, source_path="src/Controller/UserController.php")
    assert _pairs(routes) == {("GET", "/users/{id}"), ("POST", "/users/{id}")}


def test_symfony_attribute_route_without_methods_defaults_empty():
    source = """<?php
    #[Route('/health')]
    public function health() {}
    """
    routes = PhpExtractor().discover(source, source_path="src/Controller/HealthController.php")
    assert len(routes) == 1
    assert routes[0].methods == ()
    assert routes[0].raw_path == "/health"


def test_symfony_annotation_route_with_methods():
    source = """<?php
    /**
     * @Route("/legacy/{id}", methods={"GET"})
     */
    public function legacy(int $id) {}
    """
    routes = PhpExtractor().discover(source, source_path="src/Controller/LegacyController.php")
    assert _pairs(routes) == {("GET", "/legacy/{id}")}


def test_line_numbers_are_one_based():
    source = "<?php\nRoute::get('/a', 'C@a');\nRoute::post('/b', 'C@b');\n"
    routes = PhpExtractor().discover(source, source_path="routes/web.php")
    by_path = {r.raw_path: r.line for r in routes}
    assert by_path["/a"] == 2
    assert by_path["/b"] == 3


def test_mixed_laravel_and_symfony_in_one_file():
    source = """<?php
    Route::get('/users', 'UserController@index');
    Route::match(['put', 'patch'], '/users/{id}', 'UserController@update');
    Route::any('/ping', 'PingController@ping');

    #[Route('/api/items/{id}', methods: ['DELETE'])]
    public function delete(int $id) {}
    """
    routes = PhpExtractor().discover(source, source_path="routes/web.php")
    assert _pairs(routes) == {
        ("get", "/users"),
        ("put", "/users/{id}"),
        ("patch", "/users/{id}"),
        ("", "/ping"),
        ("DELETE", "/api/items/{id}"),
    }
