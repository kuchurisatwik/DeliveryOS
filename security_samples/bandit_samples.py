"""INTENTIONALLY INSECURE — Bandit test fixture.

None of these functions are imported or executed anywhere. They exist only so the
Bandit scanner has real issues to detect. Do not copy these patterns.
"""

import hashlib
import os
import pickle
import subprocess

import yaml

# B105: hardcoded password (fake, non-functional placeholder).
ADMIN_PASSWORD = "SuperSecret123!"
DB_CONNECTION = "postg://admin:hunter2@localhost:5432/prod"


def run_eval(expr):
    # B307: use of eval on caller-supplied data.
    return eval(expr)


def run_exec(code):
    # B102: use of exec.
    exec(code)


def shell_command(user_input):
    # B602: subprocess with shell=True and untrusted input (command injection).
    return subprocess.call("echo " + user_input, shell=True)


def os_system(user_input):
    # B605: os.system with a constructed command string.
    os.system("ping " + user_input)


def load_pickle(blob):
    # B301: pickle can execute arbitrary code during deserialization.
    return pickle.loads(blob)


def load_yaml(text):
    # B506: yaml.load without SafeLoader.
    return yaml.load(text)


def weak_hash(password):
    # B303: MD5 is a weak/broken hash for security use.
    return hashlib.md5(password.encode()).hexdigest()


def insecure_tempfile():
    # B108: hardcoded /tmp path (predictable temp file).
    path = "/tmp/session_token.txt"
    with open(path, "w") as fh:
        fh.write(ADMIN_PASSWORD)
    return path
