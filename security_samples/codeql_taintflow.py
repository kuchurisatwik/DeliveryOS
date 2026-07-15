"""INTENTIONALLY INSECURE — CodeQL taint-flow test fixture.

CodeQL shines at *data-flow* bugs that span multiple functions. Here untrusted
input enters at `handle_request`, is passed through helper functions unchanged, and
reaches dangerous sinks (`os.system`, SQL). Pattern scanners often miss this because
the source and sink are in different functions; CodeQL tracks the taint across them.

Dead code only — never imported or executed. Do not copy these patterns.
"""

import os
import sqlite3


def _passthrough(value):
    # Taint is preserved across this helper (no sanitization).
    cleaned = value
    return cleaned


def _build_command(target):
    # Still tainted: the caller-controlled value flows into the command string.
    return "traceroute " + _passthrough(target)


def _build_query(name):
    return "SELECT * FROM accounts WHERE name = '" + _passthrough(name) + "'"


def handle_request(request_params):
    """Entry point: `request_params` is untrusted (source)."""
    host = request_params.get("host")
    name = request_params.get("name")

    # Sink 1: OS command injection reached via _build_command (multi-hop taint).
    os.system(_build_command(host))

    # Sink 2: SQL injection reached via _build_query (multi-hop taint).
    conn = sqlite3.connect("accounts.db")
    conn.cursor().execute(_build_query(name))
    conn.commit()
