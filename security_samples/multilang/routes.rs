// Multi-framework Rust route sample for the endpoint extractor tests.
//
// Mixes actix-web attribute macros, an actix `#[route(..., method = ...)]`,
// and an axum `Router` builder so one fixture exercises all three recognised
// declaration shapes. This file is a static sample only — it is never compiled
// or executed by the extractor.

use actix_web::{get, post, route, web, App, HttpServer, Responder};
use axum::{routing::{get, delete}, Router};

// actix-web attribute macros: verb from the macro, brace path params.
#[get("/users/{id}")]
async fn get_user(path: web::Path<u32>) -> impl Responder {
    format!("user {}", path.into_inner())
}

#[post("/users")]
async fn create_user() -> impl Responder {
    "created"
}

// actix-web generic route macro: verb from the `method` attribute.
#[route("/legacy", method = "PUT")]
async fn legacy() -> impl Responder {
    "legacy"
}

// axum Router builder: verb from the routing function, mixed path styles.
fn app() -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/items/{id}", delete(remove_item))
}

async fn health() -> &'static str {
    "ok"
}

async fn remove_item() -> &'static str {
    "gone"
}
