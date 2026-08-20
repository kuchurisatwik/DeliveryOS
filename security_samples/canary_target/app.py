"""A tiny, deliberately-vulnerable staging target for DAST pipeline validation.

This is NOT production code and must never be deployed anywhere reachable. It
exists to give the DAST pipeline a target that satisfies OWASP ZAP's trust gates:

* It publishes **no** OpenAPI spec of its own, so the pipeline must seed ZAP from
  the spec our endpoint engine synthesises from *this file's* Flask routes — which
  is exactly the integration we want to exercise end to end.
* It exposes ``/canary/xss`` — a route that reliably trips ZAP's detection (an
  insecure cookie plus an unescaped reflection). ZAP raising an alert on this path
  is what proves the scanner's own detection works (the canary gate).
* It carries a few extra intentionally-sloppy endpoints so passive and active
  scans have real surface to find issues on.

Written as plain Flask ``@app.route`` declarations so the Python endpoint
extractor (``dast/endpoints/languages/python.py``) discovers every route
statically, without importing or running this module.
"""

from __future__ import annotations

from flask import Flask, Response, jsonify, request

app = Flask(__name__)

# A small in-memory "database". Not persisted; reset on every start.
_ITEMS = {
    "1": {"id": "1", "name": "widget", "secret": "alpha"},
    "2": {"id": "2", "name": "gadget", "secret": "bravo"},
}


@app.route("/")
def home():
    """Service root — a plain, harmless landing response."""
    return jsonify({"service": "canary-target", "status": "ok"})


@app.route("/canary/xss")
def canary_xss():
    """The deliberately vulnerable canary route.

    Two independent things make ZAP raise an alert here, so the canary gate passes
    even during seeding (before the active scan runs):

    1. An insecure session cookie (no ``HttpOnly``/``Secure``) — ZAP's passive
       scanner flags this on the plain seeding GET, with the alert URL carrying
       ``/canary/xss``.
    2. An unescaped reflection of the ``input`` query parameter into both an HTML
       body context and a ``<script>`` context — a textbook reflected XSS the
       active scanner confirms.
    """
    tainted = request.args.get("input", "<script>alert('canary')</script>")
    body = (
        "<!doctype html><html><head><title>canary</title></head><body>"
        f"<div id='reflect'>{tainted}</div>"
        f"<script>var c = '{tainted}';</script>"
        "</body></html>"
    )
    response = Response(body, mimetype="text/html")
    # Deliberately insecure cookie: no HttpOnly, no Secure, no SameSite.
    response.headers["Set-Cookie"] = "canary_session=please-flag-me; Path=/"
    return response


@app.route("/items")
def list_items():
    """List items (excluding their secrets)."""
    return jsonify([{"id": i["id"], "name": i["name"]} for i in _ITEMS.values()])


@app.route("/items/<item_id>")
def get_item(item_id):
    """Fetch one item by id.

    Intentionally leaks the item's ``secret`` (broken object-level authorization)
    and reflects unknown ids straight back into an HTML error (reflected XSS),
    giving the active scanner something real to find.
    """
    item = _ITEMS.get(item_id)
    if item is None:
        return Response(
            f"<html><body>No such item: {item_id}</body></html>",
            status=404,
            mimetype="text/html",
        )
    return jsonify(item)


@app.route("/search")
def search():
    """Search endpoint that reflects the raw query term unescaped (reflected XSS)."""
    term = request.args.get("q", "")
    return Response(
        f"<html><body>Results for: {term}</body></html>",
        mimetype="text/html",
    )


if __name__ == "__main__":
    # Bind all interfaces so the container is reachable across the compose network.
    app.run(host="0.0.0.0", port=5000)
