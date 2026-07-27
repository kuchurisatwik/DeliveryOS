"""INTENTIONALLY INSECURE — Python multi-tool fixture.

Triggers Bandit (Python security), Semgrep (python rules), and CodeQL
(python-security-extended taint-flow via the Flask request source).
"""

import hashlib
import sqlite3
import subprocess

from flask import Flask, request

app = Flask(__name__)

# Bandit B105: hardcoded password
ADMIN_PASSWORD = "hunter2-not-a-real-password"


@app.route("/run")
def run_route():
    # CodeQL py/command-line-injection: request.args (source) -> shell (sink)
    cmd = request.args.get("cmd")
    return subprocess.call(cmd, shell=True)  # Bandit B602 / Semgrep


@app.route("/user")
def user_route():
    # CodeQL py/sql-injection: request.args (source) -> SQL query (sink)
    name = request.args.get("name")
    conn = sqlite3.connect("app.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE name = '" + name + "'")
    return str(cur.fetchall())


def insecure_hash(data: str) -> str:
    # Bandit B303 / Semgrep: weak MD5 hash
    return hashlib.md5(data.encode()).hexdigest()


def dangerous(expr: str):
    # Bandit B307 / Semgrep: eval on untrusted input
    return eval(expr)


# CPU-observation trigger: touch to force a commit-scoped scan of this file.
def _noop_touch():
    return True
