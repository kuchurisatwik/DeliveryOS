# Security Pipeline — A Beginner's Guide

> No prior security knowledge needed. This guide explains, in plain language,
> what the DeliveryOS Security Pipeline does, the tools it uses, what each tool
> looks for, and what you get at the end.

---

## 1. What is it, in one sentence?

Every time you push code, the pipeline automatically **scans your changes for
security problems**, asks an **AI to explain and suggest fixes** for the important
ones, and opens a **Pull Request with a report** — so a human can review it before
anything gets merged.

Think of it as a security-savvy teammate that reviews every push for you.

---

## 2. The big picture (simple flow)

```
        You push code to GitHub
                 │
                 ▼
        ┌─────────────────────┐
        │  1. Understand      │   What files changed?
        │     the change      │
        └─────────────────────┘
                 │
                 ▼
        ┌─────────────────────┐
        │  2. Scan for        │   6 tools run in parallel,
        │     problems        │   each hunting a different threat
        └─────────────────────┘
                 │
                 ▼
        ┌─────────────────────┐
        │  3. Think about     │   AI explains the risky ones
        │     the findings    │   and suggests fixes
        └─────────────────────┘
                 │
                 ▼
        ┌─────────────────────┐
        │  4. Decide &        │   Score readiness, write report,
        │     report          │   open a Pull Request
        └─────────────────────┘
                 │
                 ▼
        A human reads the report and decides to merge
```

**Golden rule:** the pipeline **never merges code by itself**. It only advises. A
person always makes the final call.

---

## 3. The 4 stages explained simply

### Stage 1 — Understand the change
The pipeline looks at your commit and figures out **which files and functions you
touched**. This keeps the scan focused and fast (it can also scan the whole repo
when you want a full audit — see Section 6).

### Stage 2 — Scan for problems
Six specialized security tools run **at the same time**. Each is an expert at
spotting one kind of problem (secrets, SQL injection, risky dependencies, etc.).
If one tool fails, the others keep going — one broken tool never stops the scan.

### Stage 3 — Think about the findings
Raw tool output is noisy. This stage:
- Cleans up and **removes duplicate** findings (two tools reporting the same issue).
- **Ranks** findings by real-world risk (a critical bug on a public endpoint beats a
  minor style nit).
- Asks an **AI** to explain the important findings in human terms and **suggest a
  fix** — sometimes even a ready-to-apply code patch.

### Stage 4 — Decide & report
- Runs a **quality gate**: pass/fail against rules (e.g. "zero leaked secrets").
- Computes an advisory **merge-confidence score** (0–100).
- Writes everything into a **report** and opens a **Pull Request** on GitHub.

---

## 4. The 6 scanning tools — what each one catches

Each tool is a well-known open-source security scanner. Here's what each one hunts
for, in plain terms:

| Tool | Category | What it looks for (examples) |
|---|---|---|
| **Bandit** | Python code safety | Dangerous Python: `eval()`/`exec()`, running shell commands unsafely, weak encryption, hardcoded passwords, unsafe YAML/pickle loading |
| **Semgrep** | Code patterns | **SQL injection**, **command injection**, **cross-site scripting (XSS)**, **SSRF**, path traversal, broken login/permission checks |
| **CodeQL** | Deep data-flow | Complex bugs that span multiple functions — e.g. untrusted input flowing into a database query (**taint-tracking SQL injection**), authorization bypasses, resource leaks |
| **Gitleaks** | Secret detection | **Leaked secrets** in code: API keys, cloud credentials, SSH keys, access tokens, database passwords, `.env` file leaks |
| **Checkov** | Infrastructure config | Misconfigured cloud setup (Terraform, Kubernetes, CloudFormation): public storage buckets, wide-open firewall rules, weak IAM permissions |
| **Trivy** | Dependencies & containers | Known vulnerabilities (**CVEs**) in the libraries you depend on, insecure Docker images, OS package vulns; also catches secrets and IaC issues |

### A quick "which tool catches what?" cheat sheet

```
  SQL injection            →  Semgrep, CodeQL
  Command injection        →  Semgrep, Bandit
  Cross-site scripting     →  Semgrep
  Leaked API keys/secrets  →  Gitleaks, Trivy
  Weak crypto / eval()     →  Bandit
  Vulnerable dependency    →  Trivy
  Public S3 bucket / bad IAM  →  Checkov, Trivy
  Insecure Dockerfile      →  Trivy, Checkov
```

Notice the **overlap** — that's on purpose. Multiple tools looking at the same
threat from different angles catch more real bugs. Stage 3 merges any duplicates so
you don't see the same issue twice.

### Many languages, automatically

The pipeline isn't Python-only. It **auto-detects the languages** in your change and
points the code scanners at the right rules:

| Language | Pattern SAST (Semgrep) | Deep data-flow (CodeQL) | Deps (Trivy) | Secrets (Gitleaks) |
|---|---|---|---|---|
| Python | ✓ (+Bandit) | ✓ | ✓ | ✓ |
| JavaScript / TypeScript | ✓ | ✓ | ✓ | ✓ |
| Java / Kotlin | ✓ | ✓ (opt-in*) | ✓ | ✓ |
| Go | ✓ | ✓ (opt-in*) | ✓ | ✓ |
| Ruby | ✓ | ✓ | ✓ | ✓ |
| C# | ✓ | ✓ (opt-in*) | ✓ | ✓ |
| C / C++ | ✓ | ✓ (opt-in*) | ✓ | ✓ |
| PHP | ✓ | — | ✓ | ✓ |
| Shell / Bash | ✓ | — | — | ✓ |

*\*Compiled languages need a build step during CodeQL analysis, so deep CodeQL scans
for them are opt-in (`SECURITY_CODEQL_COMPILED`). Semgrep still covers them by
default.*

You don't configure anything — detection is automatic. If you ever need to pin it,
set `SECURITY_LANGUAGES` (e.g. `python,go`).

---

## 5. Deterministic tools + AI: who does what?

This is the core idea, and it keeps the pipeline trustworthy:

```
   Tools FIND the problems   →   AI EXPLAINS & SUGGESTS fixes   →   Tools VERIFY the fix
   (deterministic, reliable)     (smart, but double-checked)        (deterministic again)
```

- **Tools discover** vulnerabilities — they're predictable and repeatable.
- **AI reasons** about the findings: it writes plain-English explanations, ranks
  priority, and proposes fixes. But AI never gets the final word.
- **Tools re-verify** any AI-suggested fix (when fix-verification is enabled) — a
  patch is only marked "fixed" if the scanners confirm the problem is gone *and* no
  new problem was introduced.

To keep AI usage cheap and focused, findings are handled in tiers:
- **Critical** → AI writes a concrete before/after code patch.
- **High** → AI gives grouped explanations with example fixes (batched to save calls).
- **Medium / Low** → standard built-in guidance, **no AI call at all**.

---

## 6. Scan scope: your changes vs. the whole repo

The pipeline can run in two modes (set by `SECURITY_SCAN_SCOPE`):

| Mode | What it scans | When to use |
|---|---|---|
| `commit` (default) | Only the files you changed | Everyday per-push checks — fast |
| `full` | The entire repository | One-off or scheduled full audits |

Two related language knobs:

| Setting | Default | What it does |
|---|---|---|
| `SECURITY_LANGUAGES` | `auto` | Detect languages automatically, or pin a list (`python,javascript,go`) |
| `SECURITY_CODEQL_COMPILED` | `false` | Turn on deep CodeQL scans for compiled languages (needs a working build) |

---

## 7. What you get at the end (the output)

Two things:

### a) A Pull Request on GitHub
A new branch (`ai-sde/review-<commit>-<timestamp>`) with a PR containing the report.

### b) An `AI_REPORT.md` file
A readable report with these sections:

```
🔒 Security Pipeline Report
 ├─ Commit / Repository / Branch    ← what was reviewed
 ├─ Security Summary                ← "X fixed; Y remaining; gate passed/failed"
 ├─ Scanned scope                   ← changed files, or "whole repository"
 ├─ Findings by severity            ← quick histogram
 ├─ 🛰️ Scanner Coverage            ← which of the 6 tools ran (and found what)
 ├─ 🛠️ Remediation Guide           ← key high/critical issues + how to fix them
 ├─ Merge Confidence (advisory)     ← a 0–100 readiness score
 ├─ Quality Gate                    ← pass/fail + which rules failed
 ├─ ✅ Fixed Findings               ← problems the AI patched & tools verified
 └─ ❗ Remaining Findings           ← what still needs a human's attention
```

### How to read it
1. **Scanner Coverage** — did all 6 tools run? A ❌ means a tool couldn't finish, so
   treat that area as "unknown", not "clean".
2. **Findings by severity** — how many issues, and how serious.
3. **Remediation Guide** — the important issues with concrete fixes for the dev team.
4. **Quality Gate + Merge Confidence** — the advisory verdict.
5. **Remaining Findings** — the to-do list before merging.

> Remember: everything here is **advisory**. The report helps a human decide — it
> does not merge anything on its own.

---

## 8. A clean-run example

If your code has no detectable issues, the report is short and honest:

- Scanner Coverage: **6/6 completed**
- Findings by severity: **none**
- Fixed / Remaining: **0 / 0**

That means the six tools looked at your code and found nothing to flag. (The quality
gate may still show "failed" purely because test-coverage isn't configured in
security-only runs — that's a config artifact, not a security problem, and the report
says so.)

---

## 9. One-page summary

- **Trigger:** every Git push.
- **4 stages:** understand → scan → think → decide/report.
- **6 tools:** Bandit, Semgrep, CodeQL, Gitleaks, Checkov, Trivy — each an expert on
  a different threat (code bugs, SQLi, deep data-flow, secrets, cloud config, deps).
- **AI:** explains and suggests fixes for the important findings; tools verify them.
- **Output:** a GitHub Pull Request + an `AI_REPORT.md` with findings, fixes, and an
  advisory score.
- **Safety:** never auto-merges — a human always decides.

---

*For deeper technical detail see `Security_Pipeline_Layers.md` (architecture) and
`Security_Scanner_Tools_Guide.md` (per-tool inputs/outputs).*
