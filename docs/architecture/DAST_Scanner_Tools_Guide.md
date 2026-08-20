# DAST Scanner Tools Guide

The five tools our DAST pipeline runs, and what each one is for.

## Why these five

DAST tools overlap heavily. We picked five that each answer a question none of the
others can, so nothing in the pipeline is redundant:

| Tool | The question it answers |
|---|---|
| **Nuclei** | Are we exposed to anything already publicly known? |
| **OWASP ZAP** | Does *our own code* have injection, XSS, or access-control flaws? |
| **Schemathesis** | Does our API behave the way its spec says it does? |
| **sqlmap** | Is that suspected SQL injection actually real? |
| **testssl.sh** | Is the HTTPS connection itself sound? |

Deliberately left out: ffuf, nmap, nikto, wapiti, whatweb, dalfox. Each either
duplicates one of the five above or adds little against an API-first service with a
published OpenAPI spec.

---

## 1. Nuclei

**Purpose** — Fires ~10,000 community-maintained checks ("templates") at a running
app to detect known vulnerabilities: CVEs, exposed `.env` / `.git` files, default
logins, forgotten admin panels, misconfigurations.

**Why it matters in security** — Most real breaches exploit flaws that were already
public and already patched somewhere. This is the tool that tells us whether we're
standing on one of them.

**Where we run it** — Against the deployed application URL. It sends mostly ordinary
GET requests to known paths, so it is safe enough to point at production too.

**When we run it** — Every deploy; it finishes in seconds. Also on a schedule, because
a new CVE means a new template, and we want the check to run without a code change.

**Input** — Target URL (or a list of URLs), a pinned template set, severity and tag
filters.

**Output** — JSONL, one line per match: template ID, severity, the exact URL that
matched, CVE/CWE classification, and the evidence.

> Note: templates are executable code, not data. We pin them to a specific version in
> the Dockerfile and upgrade them through a reviewed PR, exactly like any dependency.

---

## 2. OWASP ZAP

**Purpose** — The core scanner. It proxies HTTP traffic to build a map of the
application, then replays every endpoint it knows about with real attack payloads and
watches how the responses differ.

**Why it matters in security** — It is the only tool here that can find a flaw unique
to *our* code — SQL injection, cross-site scripting, broken access control, missing
security headers. No signature database can know about a bug we wrote last week.

**Where we run it** — In the DAST stage, as a long-lived sidecar container that the
pipeline drives over its REST API.

**When we run it** — Two modes. *Passive* (observes traffic only, sends no attacks,
~2 minutes) on every deploy. *Active* (sends real attacks, 30–60 minutes) nightly,
against staging only — never production.

**Input** — Target URL, an OpenAPI spec or recorded traffic to seed the map, an auth
token, and a scan policy.

**Output** — Alerts carrying both a risk level and a confidence level, plus the exact
request and response that prove it, and a CWE ID. JSON or SARIF.

> Critical: ZAP only attacks URLs already in its map. It discovers nothing by itself.
> An unseeded scan reports zero findings and exits successfully — a false all-clear.
> Seeding it properly is most of the work.

---

## 3. Schemathesis

**Purpose** — Reads our OpenAPI spec and generates thousands of requests from it —
both valid ones and deliberately malformed ones — then checks the API responds the way
the spec promises.

**Why it matters in security** — It catches what signature tools cannot see: unhandled
500 errors (unvalidated input reaching our code, often leaking a stack trace),
endpoints that answer without authentication, and responses that violate their own
declared schema.

**Where we run it** — Against the API. Best run *through ZAP as a proxy*, so a single
execution both reports its own failures and fills ZAP's map with real, authenticated
traffic for the active scanner to work on.

**When we run it** — Every deploy with a fixed random seed so results are
reproducible; unseeded in the nightly run, where exploring new cases is the point.

**Input** — OpenAPI or GraphQL schema (URL or file), base URL, auth token.

**Output** — Failing cases per endpoint, each with the exact request needed to
reproduce it. JSON or JUnit XML.

---

## 4. sqlmap

**Purpose** — Confirms SQL injection and characterises it. It turns "ZAP thinks this
parameter might be injectable" into "it is, the database is PostgreSQL 15, and here is
what's reachable."

**Why it matters in security** — SQL injection remains one of the most damaging flaws
there is, since it can mean full read and write access to the database. Scanners guess;
sqlmap proves. That difference is what makes a finding worth blocking a release for.

**Where we run it** — As a verification step, pointed only at the specific parameters
ZAP has already flagged. Never broadly.

**When we run it** — In the nightly deep scan only, never on the fast per-deploy path.

**Input** — A URL with a parameter, or a saved HTTP request file. Always `--batch`
(no interactive prompts) with low `--level` and `--risk`.

**Output** — Whether the parameter is injectable, which technique worked, and the DBMS
and version.

> Detection only. Data-extraction flags never run in the pipeline.

---

## 5. testssl.sh

**Purpose** — Audits the HTTPS layer itself: which TLS protocol versions and cipher
suites are accepted, and whether the certificate is valid and current.

**Why it matters in security** — Every other tool on this list assumes the connection
is trustworthy. An expired certificate, TLS 1.0 still enabled, or a weak cipher makes
traffic interceptable no matter how clean the application code is.

**Where we run it** — Against the **real** staging or production hostname. Not against
the ephemeral per-commit container, which has no TLS at all — that gets terminated
upstream at the load balancer, so scanning the container would always report clean.

**When we run it** — Weekly, and whenever a certificate or ingress configuration
changes. It is not a per-commit check.

**Input** — Hostname and port.

**Output** — An OK / WARN / CRITICAL verdict per check, covering protocol versions,
cipher suites, and certificate expiry. JSON.

---

## At a glance

| Tool | Layer | Speed | Safe in prod? | Runs on |
|---|---|---|---|---|
| Nuclei | Known issues | Seconds | Yes | Every deploy + schedule |
| ZAP passive | App (observation) | ~2 min | Yes | Every deploy |
| Schemathesis | API contract | ~5 min | Staging | Every deploy |
| ZAP active | App (attack) | 30–60 min | **No** | Nightly |
| sqlmap | Proof | Minutes | **No** | Nightly, on flagged params |
| testssl.sh | Transport | ~2 min | Yes | Weekly |

**Rules of engagement:** active scans send real attack traffic and can corrupt data —
staging only, and tell on-call before scheduled runs. Only ever scan systems we own.
