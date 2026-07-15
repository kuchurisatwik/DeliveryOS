"""INTENTIONALLY INSECURE — Semgrep test fixture.

Targets the p/security-audit and p/python rulesets: SQL injection, command
injection, SSRF/insecure requests, and disabled TLS verification. Dead code only;
never imported or executed. Do not copy these patterns.
"""

import os
import sqlite3
import subprocess

import requests


def sql_injection(username):
    # Semgrep: formatted/concatenated SQL query (SQL injection).
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE name = '" + username + "'"
    cursor.execute(query)
    return cursor.fetchall()


def sql_injection_fstring(user_id):
    # Semgrep: f-string interpolation directly into SQL.
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM sessions WHERE user_id = {user_id}")
    conn.commit()


def command_injection(filename):
    # Semgrep: shell=True with interpolated input (command injection).
    subprocess.Popen(f"cat {filename}", shell=True)


def os_command(host):
    # Semgrep: os.system with untrusted input.
    os.system("nslookup " + host)


def insecure_request(url):
    # Semgrep: TLS certificate verification disabled.
    return requests.get(url, verify=False)


def ssrf(user_supplied_url):
    # Semgrep: server-side request to a user-controlled URL (SSRF).
    return requests.get(user_supplied_url).text
