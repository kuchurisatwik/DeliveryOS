"""Kotlin route extractor tests (Spring annotations + Ktor DSL).

Example-based checks with inline Kotlin snippets: a Spring ``@RestController``
whose class-level ``@RequestMapping`` base must be joined onto each method
mapping, and a Ktor routing block whose verb comes from the DSL function name.
Also confirms ``matches`` keys off the ``.kt`` extension only.
"""

from dast.endpoints.languages.kotlin import KotlinExtractor

SPRING_CONTROLLER = '''
package com.example.api

import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/api/v1")
class UserController {

    @GetMapping("/users/{id}")
    fun getUser(@PathVariable id: Long): User = repo.find(id)

    @PostMapping("/users")
    fun createUser(@RequestBody user: User): User = repo.save(user)
}
'''

KTOR_ROUTING = '''
package com.example.api

import io.ktor.server.routing.*

fun Application.configureRouting() {
    routing {
        get("/users") {
            call.respond(repo.all())
        }
        post("/users/{id}") {
            call.respond(repo.save(id))
        }
    }
}
'''


def test_spring_base_path_is_joined_onto_method_mappings():
    routes = KotlinExtractor().discover(SPRING_CONTROLLER, source_path="UserController.kt")

    found = {(r.methods, r.raw_path) for r in routes}
    assert found == {
        (("GET",), "/api/v1/users/{id}"),
        (("POST",), "/api/v1/users"),
    }


def test_ktor_dsl_verb_and_literal_path():
    routes = KotlinExtractor().discover(KTOR_ROUTING, source_path="Routing.kt")

    found = {(r.methods, r.raw_path) for r in routes}
    assert found == {
        (("GET",), "/users"),
        (("POST",), "/users/{id}"),
    }


def test_routes_carry_one_based_line_numbers():
    routes = KotlinExtractor().discover(KTOR_ROUTING, source_path="Routing.kt")

    get_route = next(r for r in routes if r.methods == ("GET",))
    # The get("/users") call sits on the 8th line of the snippet (1-based).
    assert get_route.line == KTOR_ROUTING.split("\n").index('        get("/users") {') + 1


def test_matches_rejects_non_kt_paths():
    extractor = KotlinExtractor()
    assert extractor.matches("UserController.kt") is True
    assert extractor.matches("UserController.java") is False
    assert extractor.matches("routing.py") is False


def test_language_label_is_kotlin():
    assert KotlinExtractor().language == "kotlin"
