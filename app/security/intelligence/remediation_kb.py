"""Deterministic remediation knowledge base (0 LLM calls).

For the common, well-understood rule classes the fix is always the same, so an
LLM call adds cost and variance without adding value. This module maps rule
identities / categories to a fixed, curated remediation string. It is used for
MEDIUM/LOW findings (which are not escalated to the AI) so the report still
gives every finding actionable guidance — instantly, consistently, and for free.

Lookup order in :func:`lookup_remediation`:

1. Exact / prefix match on the normalized ``rule_identity`` (e.g. ``b303``,
   ``b101``, semgrep ``...insecure-hash...``).
2. Category fallback (``code`` / ``secret`` / ``iac`` / ``dependency`` /
   ``container``).
3. A generic catch-all.

All lookups are pure and deterministic.
"""

from __future__ import annotations

#: Rule-identity → remediation. Keys are matched as case-insensitive substrings
#: of the normalized rule_identity so both Bandit ids (``b303``) and Semgrep
#: slugs (``insecure-hash-algorithm-md5``) hit the same guidance.
_RULE_REMEDIATIONS: dict[str, str] = {
    # --- Bandit code rules ---
    "b101": "Avoid `assert` for runtime checks — it is stripped under `python -O`. Raise explicit exceptions instead.",
    "b102": "Do not use `exec()`. Refactor to call the intended function/logic directly.",
    "b103": "Avoid setting permissive file permissions (e.g. 0o777). Grant the least privilege the file needs.",
    "b104": "Do not bind services to 0.0.0.0 unless required. Bind to a specific interface/loopback.",
    "b105": "Remove hardcoded passwords/secrets. Load them from environment variables or a secrets manager.",
    "b106": "Remove hardcoded credentials passed as function arguments; inject them from configuration/secrets.",
    "b107": "Remove hardcoded default passwords; require credentials to be supplied via configuration.",
    "b108": "Avoid predictable temp paths like /tmp/x. Use `tempfile.mkstemp()`/`NamedTemporaryFile`.",
    "b110": "Do not silently `pass` on exceptions. Log and handle them so failures are visible.",
    "b112": "Avoid `try/except/continue` that swallows errors; log and handle the exception.",
    "b113": "Set an explicit timeout on network requests to avoid indefinite hangs (e.g. `requests.get(..., timeout=10)`).",
    "b301": "Do not `pickle.loads()` untrusted data — it enables arbitrary code execution. Use JSON or a safe serializer.",
    "b303": "MD5/SHA1 are cryptographically broken. Use SHA-256+ for integrity, and bcrypt/scrypt/Argon2 for passwords.",
    "b307": "Do not use `eval()`. Parse input explicitly (e.g. `ast.literal_eval` for literals) or dispatch on a whitelist.",
    "b311": "Do not use the `random` module for security. Use the `secrets` module for tokens/keys.",
    "b324": "Weak hash (`hashlib.md5`/`sha1`). Use SHA-256+, and set `usedforsecurity=False` only for non-security uses.",
    "b403": "Importing `pickle`/`marshal` is risky. Prefer JSON; never deserialize untrusted data with them.",
    "b404": "Importing `subprocess` is fine, but never call it with `shell=True` on untrusted input; pass an argument list.",
    "b501": "Do not disable TLS verification (`verify=False`). Keep certificate validation enabled.",
    "b506": "Do not use `yaml.load()` without a safe loader. Use `yaml.safe_load()`.",
    "b602": "Avoid `subprocess` with `shell=True`. Pass a list of arguments and keep `shell=False`.",
    "b603": "Validate/whitelist any external input passed to `subprocess` even without a shell.",
    "b605": "Avoid `os.system()`. Use `subprocess.run([...], shell=False)` with an argument list.",
    "b608": "Possible SQL injection from string-built queries. Use parameterized queries / an ORM, never string concatenation.",
    # --- Semgrep slugs (substring match) ---
    "insecure-hash": "Replace the weak hash (MD5/SHA1) with SHA-256+ (bcrypt/Argon2 for passwords).",
    "md5": "MD5 is broken. Use SHA-256+ for integrity and bcrypt/scrypt/Argon2 for passwords.",
    "avoid-pickle": "Do not deserialize untrusted data with pickle. Use JSON or a schema-validated format.",
    "eval-detected": "Remove `eval()`. Use explicit parsing or a whitelist dispatch instead.",
    "exec-detected": "Remove `exec()`. Call the intended logic directly.",
    "subprocess-shell-true": "Set `shell=False` and pass arguments as a list to prevent command injection.",
    "disabled-cert-validation": "Re-enable TLS certificate validation (`verify=True`).",
    "sql": "Use parameterized queries / ORM bindings; never interpolate user input into SQL.",
}

#: Category → generic remediation used when no rule-level entry matches.
_CATEGORY_REMEDIATIONS: dict[str, str] = {
    "code": "Review against secure-coding guidance for this rule and apply the standard fix (validate input, avoid dangerous APIs).",
    "secret": "Remove the secret from source, rotate it immediately, and load it from a secrets manager / environment.",
    "iac": "Harden the infrastructure config: least-privilege access, no public exposure, encryption enabled.",
    "dependency": "Upgrade the affected package to a patched version that resolves this advisory.",
    "container": "Use a maintained, minimal base image, pin versions, and run as a non-root user.",
}

_GENERIC = "Review this finding against secure-coding guidance and remediate before merge."


def lookup_remediation(rule_identity: str, category: str) -> str:
    """Return canned remediation for ``rule_identity``/``category`` (pure, 0 calls)."""
    rid = (rule_identity or "").strip().lower()
    for key, text in _RULE_REMEDIATIONS.items():
        if key in rid:
            return text
    return _CATEGORY_REMEDIATIONS.get((category or "").strip().lower(), _GENERIC)
