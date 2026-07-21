"""Layer 3 Cross-tool correlation — collapse multi-tool duplicates (Phase 1).

:func:`deduplicate` (Requirement 6) already merges findings that share the *same
rule identity* at the same location. But different tools name the same underlying
vulnerability differently — e.g. a single ``subprocess(..., shell=True)`` line is
reported as CodeQL ``py/command-line-injection``, Semgrep
``subprocess-shell-true``/``dangerous-subprocess-use``, and Bandit ``b602``. After
dedup those are still **four** findings for one bug, inflating the counts and the
severity histogram.

:func:`correlate` is a **pure, deterministic** post-dedup step that groups findings
by ``(canonical_path, start_line, vuln_class)`` — where ``vuln_class`` is inferred
from the rule identity + message — and merges each group into one finding:

* the merged ``scanners`` frozenset is the **union** of every contributing tool
  (so ≥2 tools agreeing is visible = corroboration);
* the base finding is the **highest-severity** member (severity is never lost);
* findings that cannot be classified into a known class are left untouched (keyed
  by their own identity), so distinct issues are never over-merged.

This is intentionally conservative: only well-known vulnerability classes are
correlated, and only when they land on the exact same file+line.
"""

from __future__ import annotations

from dataclasses import replace

from app.security.intelligence.normalize import _canonical_path
from app.security.models import Normalized_Finding, Severity

# Severity rank for "highest severity wins" (higher = more severe).
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.CRITICAL: 5,
    Severity.HIGH: 4,
    Severity.MEDIUM: 3,
    Severity.LOW: 2,
    Severity.INFO: 1,
}

#: Ordered (vuln_class, keyword-substrings) table. First class with any keyword
#: substring found in the finding's ``rule_identity + message`` wins. Order matters:
#: more specific classes come first.
_VULN_CLASS_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("sql-injection", ("sql-injection", "sql injection", "tainted-sql", "sqli", "b608")),
    (
        "command-injection",
        (
            "command-injection", "command injection", "command-line-injection",
            "os-command", "shell-true", "shell=true", "dangerous-exec",
            "tainted-exec", "child-process", "child_process", "detect-child-process",
            "subprocess", "b602", "b603", "b604", "b605", "b606", "b607",
        ),
    ),
    ("code-injection", ("code-injection", "code injection", "code-string-concat", "eval-detected", "eval(", "b307")),
    ("path-traversal", ("path-traversal", "path traversal", "pathtraversal", "b108")),
    ("ssrf", ("ssrf", "server-side request forgery")),
    ("xss", ("xss", "cross-site-scripting", "echoed-request", "direct-response-write")),
    (
        "deserialization",
        ("deserial", "pickle", "yaml.load", "fullloader", "unsafe-load", "b301", "b506"),
    ),
    (
        "weak-crypto",
        ("md5", "sha1", "weak-hash", "insecure-hash", "insecure-cipher", "b303", "b324"),
    ),
    (
        "hardcoded-secret",
        (
            "hardcoded", "hard-coded", "api-key", "api_key", "private-key",
            "access-key", "aws-access", "credential", "b105", "b106", "b107",
        ),
    ),
    ("ssl-tls", ("use-tls", "insecure-transport", "verify=false", "insecure-ssl")),
)


def classify(finding: Normalized_Finding) -> str:
    """Infer a coarse vulnerability class from a finding, or ``""`` if unknown (pure)."""
    text = f"{finding.rule_identity} {finding.message}".lower()
    for vuln_class, keywords in _VULN_CLASS_PATTERNS:
        if any(kw in text for kw in keywords):
            return vuln_class
    return ""


def _severity_rank(sev: Severity) -> int:
    return _SEVERITY_RANK.get(sev, 0)


def correlate(findings: list[Normalized_Finding]) -> list[Normalized_Finding]:
    """Merge cross-tool duplicates of the same vuln class at the same location (pure).

    Args:
        findings: Deduplicated normalized findings (output of :func:`deduplicate`).

    Returns:
        A list where findings sharing ``(canonical_path, start_line, vuln_class)``
        are merged into their highest-severity member with the union of all
        contributing scanners. Unclassifiable findings are passed through keyed by
        their own identity (never over-merged). Group order follows first
        appearance, so the function is deterministic.
    """
    # key -> (base_finding, unioned_scanners, insertion_index)
    groups: dict[tuple, list] = {}
    order: list[tuple] = []

    for finding in findings:
        vuln_class = classify(finding)
        if vuln_class:
            key = (_canonical_path(finding.location.path), finding.location.start_line, vuln_class)
        else:
            # Unclassified → keep its own identity (path+line+end+symbol+rule).
            loc = finding.location
            key = (
                _canonical_path(loc.path),
                loc.start_line,
                loc.end_line,
                loc.symbol or "",
                finding.rule_identity,
            )

        if key not in groups:
            groups[key] = [finding, set(finding.scanners)]
            order.append(key)
        else:
            entry = groups[key]
            entry[1].update(finding.scanners)
            # Keep the highest-severity finding as the base.
            if _severity_rank(finding.severity) > _severity_rank(entry[0].severity):
                entry[0] = finding

    return [
        replace(groups[key][0], scanners=frozenset(groups[key][1]))
        for key in order
    ]
