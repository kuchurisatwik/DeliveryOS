# Security Scanner Tools — Beginner's Guide (Inputs, Outputs & How Each Works)

This guide explains the 6 security scanners in the DeliveryOS security pipeline in
plain language: what each tool hunts for, the **exact command** our pipeline runs,
what we feed it (**input**), and what it gives back (**output**). It is grounded in
the actual adapter code under `app/security/detection/adapters/`.

---

## The mental model (read this first)

Each of the 6 tools is just a **command-line program**. Our pipeline wraps each one
with an "adapter" that does three jobs:

1. **Build a command** — turn our internal `ScanScope` (the list of files/paths to
   look at) into the exact command-line string the tool understands.
2. **Run it as a subprocess** — exactly as if you typed it in a terminal. The tool
   prints its results (usually JSON) to the screen (stdout) or to a file.
3. **Parse the output** — read that JSON and convert every issue into one shared
   shape called a `Finding`.

### Why one shared `Finding` shape?

Six tools speak six different "languages" (different JSON shapes, different severity
words). The adapter translates all of them into **one common `Finding`** so the rest
of the pipeline (deduplicate → enrich → score → triage → report) only ever deals
with one format.

A `Finding` always has:

| Field | Meaning |
|---|---|
| `scanner` | which tool found it (e.g. `"bandit"`) |
| `rule_id` | the tool's code for *what kind* of issue (e.g. `"B602"`) |
| `location` | file path + line numbers |
| `severity` | translated to our shared scale: INFO / LOW / MEDIUM / HIGH / CRITICAL |
| `message` | human-readable description |
| `raw` | the tool's original untouched output (kept for reference) |

### Severity translation

Each tool uses its own severity words. Each adapter has a small dictionary mapping
the tool's words → our 5-level scale. Examples: Bandit `HIGH→HIGH`; Semgrep
`ERROR→HIGH`, `WARNING→MEDIUM`; Trivy `CRITICAL→CRITICAL`.

---

## 1. Bandit — Python security linter

**Hunts:** dangerous Python code — `eval()`, `exec()`, `os.system()`, unsafe
`subprocess`, `pickle` deserialization, weak crypto (MD5), hardcoded passwords,
unsafe YAML loading.

**Command:**
```
bandit -r -f json -o <tempfile.json> <file1.py> <file2.py> ...
```
- `-r` recurse into folders · `-f json` JSON output · `-o <file>` write report to a file.

**Input:** the scoped (changed) Python files.
**Output:** a JSON file with a `"results"` array; each entry has `filename`,
`line_number`, `issue_severity`, `test_id`, `issue_text`.

**Pipeline notes:**
- We write to a **file** (`-o`) not the screen, because on Windows Bandit's startup
  logging polluted stdout and broke JSON parsing.
- Bandit exits `1` when it *finds* issues — that's normal, not a failure. Only exit
  `>= 2` with no report is a real error.

---

## 2. Semgrep — pattern-matching SAST (deep dive)

**Hunts:** injection and web-app flaws — SQL injection, command injection, XSS,
SSRF, path traversal, authentication/authorization flaws.

### How Semgrep works, step by step

Semgrep searches for **patterns**, but it is smarter than plain text search (Ctrl+F)
because it understands code **structure**:

1. You give it **targets** (files/folders) and a **ruleset** (`--config`). A rule is
   a small YAML file describing a dangerous code shape, e.g.:
   ```yaml
   pattern: cursor.execute("..." + $USER_INPUT)
   message: Possible SQL injection
   severity: ERROR
   ```
2. Semgrep **parses each file into an AST** (a structured tree of the code, the way
   Python itself reads it).
3. It **matches every rule's pattern against that tree**. `$USER_INPUT` is a
   "metavariable" — a wildcard matching any expression — so the rule catches SQL
   built by string concatenation regardless of the exact variable name or spacing.
4. For each match it emits a result: `check_id`, `path`, `start.line`, `end.line`,
   `extra.severity`, `extra.message`.

**Command:**
```
semgrep --config p/security-audit --config p/python --json --quiet <files...>
```
- `--config p/security-audit` = Semgrep's **broad security ruleset** (injection,
  auth, crypto, deserialization, SSRF, path traversal, ...).
- `--config p/python` = the Python-focused pack. Both are passed so their rules are
  **unioned** (more coverage).
- `--json` machine-readable output · `--quiet` suppress progress chatter.

**Input:** the scoped files + one or more ruleset names.
**Output:** JSON with a `"results"` array (fields above). We map
`ERROR→HIGH`, `WARNING→MEDIUM`, `INFO→INFO`.

**Pipeline note:** with only `p/python`, earlier runs returned 0 findings because
that pack is narrow. We now also run `p/security-audit` for broader coverage.

---

## 3. CodeQL — deep semantic / data-flow analysis

**Hunts:** the *hard* bugs that span multiple functions — user input flowing from an
HTTP handler through several calls into a SQL query (multi-step "taint flow"),
authorization bypasses, resource leaks.

**How it differs:** Bandit/Semgrep look at code *shapes*. CodeQL first **compiles the
whole codebase into a database**, then runs **queries** against it (like SQL, but for
code), so it can *follow data across functions*.

**Commands (two steps):**
```
1) codeql database create <db> --language=python --source-root=<repo> --overwrite --quiet
2) codeql database analyze <db> codeql/python-queries --format=sarif-latest --output=<tempfile.sarif> --download
```

**Input:** the whole source root (it needs everything to trace flows) + a query
suite (`codeql/python-queries`).
**Output:** a **SARIF** file (standardized static-analysis JSON). We parse it, then
**filter results down to the scoped files** so it behaves like the other scanners.

**Pipeline note:** CodeQL is the **slow** one — building the database takes ~35s per
run. Correct but heavy.

---

## 4. Gitleaks — secret scanner

**Hunts:** leaked secrets — API keys, cloud credentials, SSH private keys, tokens,
database passwords, `.env` leaks. Uses a large library of regex patterns.

**Command:**
```
gitleaks detect --no-git --source . --report-format json --report-path -
```
- `--no-git` scan files on disk · `--source .` the whole repo · `--report-path -`
  print JSON to the screen.

**Input:** the **entire repo tree** (not just changed files — a secret anywhere is
dangerous).
**Output:** a JSON array; each leak has `File`, `StartLine`, `EndLine`, `RuleID`,
`Description`. Secrets have no natural severity, so we mark them all **HIGH**.

**Pipeline note:** Gitleaks emits `null` (not `[]`) when clean — our parser handles
that.

---

## 5. Checkov — Infrastructure-as-Code (IaC) scanner

**Hunts:** misconfigurations in infrastructure files — Terraform, CloudFormation,
Kubernetes YAML, Dockerfiles. E.g. a publicly-open S3 bucket, an over-permissive IAM
role, a security group open to the internet.

**Command:**
```
checkov -d . -o json --compact --quiet
```
- `-d .` scan the whole directory (Checkov **auto-discovers** IaC files by type).

**Input:** the repo root (it finds IaC files itself).
**Output:** JSON with `results.failed_checks`; each has `file_path`,
`file_line_range`, `check_id`, `check_name`, `resource`.

**Pipeline note:** Checkov prints **one JSON document per framework back-to-back**
(one for Terraform, one for K8s, ...), which isn't valid single JSON — so we use a
multi-document parser (`load_json_multi`).

---

## 6. Trivy — dependency & container vulnerability scanner

**Hunts:** known vulnerabilities (CVEs) in **dependencies** (libraries in
`requirements.txt`/lockfiles), OS packages, container images, plus some misconfigs
and secrets. Compares your versions against a large vulnerability database.

**Command:**
```
trivy fs --format json --scanners vuln,misconfig,secret --quiet .
```
- `fs` filesystem mode · `--scanners vuln,misconfig,secret` · `.` the whole repo.

**Input:** the whole repo tree (manifests live across the repo).
**Output:** JSON with a `Results` array; each block can contain `Vulnerabilities`
(CVEs), `Misconfigurations`, and `Secrets`. We parse all three. Severity maps
directly (CRITICAL/HIGH/MEDIUM/LOW).

---

## All 6 at a glance

| Tool | Finds | We feed it | Scans | Output |
|---|---|---|---|---|
| **Bandit** | Python security bugs | changed `.py` files | scoped files | JSON file |
| **Semgrep** | injection/web patterns | changed files + rulesets | scoped files | JSON (screen) |
| **CodeQL** | cross-function data-flow bugs | whole source → DB | whole repo (filtered) | SARIF file |
| **Gitleaks** | leaked secrets | whole repo | whole repo | JSON (screen) |
| **Checkov** | IaC misconfigs | repo root | whole repo (auto-find) | JSON (multi-doc) |
| **Trivy** | dependency CVEs | repo root | whole repo | JSON (screen) |

### Two key takeaways

1. **All 6 run in parallel** as separate subprocesses, with failure isolation — one
   broken tool never kills the scan.
2. **They overlap on purpose.** Bandit + Semgrep + CodeQL look at Python at different
   depths (shape → pattern → data-flow); Gitleaks + Trivy both catch secrets. This
   redundancy means a bug one tool misses, another may catch. Afterwards the pipeline
   **deduplicates** so the same issue reported twice becomes one `Finding`.

### Known scoping caveat

Currently Semgrep and Bandit receive the tight changed-file list, while Gitleaks,
Trivy, Checkov, and CodeQL scan the **whole repo**. This is intentional for secrets
and dependencies (repo-wide by nature) but means Python findings can include
whole-codebase noise rather than strictly "what this commit changed."

---

## Test fixtures

See `security_samples/` for intentionally-insecure sample files (one target per
tool) used to verify the whole detection → report flow end-to-end. Those files are
**fixtures only** — they are never imported or executed by the application.
