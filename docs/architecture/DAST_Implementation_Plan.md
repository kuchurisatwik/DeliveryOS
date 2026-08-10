# DAST Pipeline — Implementation Plan

A standalone service. It does not touch the SAST pipeline.

---

## What we're building

SAST reads the recipe. DAST tastes the food. We already have the first one; this is
the second — a service that attacks a **running** copy of the app and reports what it
found.

```
  deploy finishes ──► POST /scan  { target_url, commit_sha }
                            │
                       [  queue  ]
                            │
         ┌──────────────────┴──────────────────┐
         │ 1. Preflight   is it up? auth ok?   │
         │ 2. Safe scans  nuclei, ZAP passive  │  ← run together
         │ 3. Deep scans  Schemathesis, ZAP    │  ← one at a time
         │ 4. Verify      sqlmap               │
         └──────────────────┬──────────────────┘
                            │
              normalize → dedupe → gate → report
```

**Why standalone?** DAST needs a deployed app; SAST needs a git commit. They start at
different moments and run at different speeds — a 45-minute ZAP scan sitting in the
SAST queue would block every code scan behind it. Two kitchens, not one.

We **reuse** the `Finding` / `Normalized_Finding` models and the normalize → dedupe →
score chain by importing them. Same plates, different kitchen.

---

## Before you start

Four things must exist, or nothing below works:

1. **A deployed target with a URL** — staging, reachable from the scanner.
2. **A scan account + token** — a real login the scanner can use. Without it we only
   ever test the login page.
3. **The OpenAPI spec URL** — FastAPI gives us this free. It is how ZAP and
   Schemathesis learn what endpoints exist.
4. **A canary route** — a deliberately vulnerable endpoint in the staging build, behind
   a build flag so it never ships. Explained in Phase 2.

---

## Phase 1 — Skeleton + one tool

**Goal:** a trigger goes in, a report comes out. One tool only.

**Why start with nuclei:** it's a single binary, needs no login, holds no state, and
prints clean JSON. Build the assembly line with the simplest product before you run the
complicated one down it.

**Build**
- New service `deliveryos-dast`: FastAPI, its own container, its own queue (copy the
  `ScanQueue` pattern — key on target URL, not commit SHA).
- `POST /scan` endpoint taking `{target_url, commit_sha, profile}`.
- Preflight step: target answers `/health`, and the SHA it reports matches the one we
  were asked to scan. *(Otherwise you spend a day chasing bugs in yesterday's build.)*
- `NucleiAdapter` — same shape as our SAST adapters: `scan()` runs the tool,
  `parse()` is a pure function over the JSON so it can be unit-tested with a saved
  file and no network.
- Results stored as JSON on disk; a one-page frontend like the SAST one.

**Two settings that matter**
- Pin the template version in the Dockerfile and upgrade via PR. Templates are code,
  not data — they run requests.
- Throttle the request rate. Our staging container is a single uvicorn worker; hitting
  it at full speed jams the door and everyone bounces off, which looks exactly like
  "nothing found."

**Done when:** a deploy triggers a scan and you get a findings list on a web page.

---

## Phase 2 — Make "zero findings" mean something

**Goal:** the pipeline can tell the difference between *clean* and *broken*.

**Why this comes before more tools:** every scanner returns an empty list when the app
is genuinely clean — and also when auth silently failed, or the target was still
booting, or a rate limiter started blocking us halfway through. A smoke detector with a
dead battery is just as quiet as a house that isn't on fire. Adding four more tools on
top of a foundation that can't tell those apart just gives you four more ways to be
falsely reassured.

**Build**
- **Canary route.** A deliberately vulnerable endpoint in the staging image. Every
  tool must find its own canary. This is the *test button on the fire alarm* — if
  pressing it produces no alarm, the alarm is broken, and you do not conclude there's
  no fire. Check it at the **start and the end** of the run: if it fires at the start
  and not at the end, something started blocking us mid-scan.
- **Liveness counts.** Each adapter records what it actually did. Be careful *which*
  number you record — this bit us on the very first live run. nuclei happily
  reported "6,915 templates loaded", exited 0, and found nothing, while **every
  single request failed DNS resolution and never left the machine**. Counting what
  a tool loads off disk proves nothing; only requests that reached the target are
  evidence. Record `requests_made` and `request_errors`, and treat
  "requests_made == 0" or "errors == requests" as a failed scan.
  *(Gotcha worth knowing: nuclei uses its own DNS resolver and cannot resolve
  `localhost` — always give scanners an IP or a real hostname.)*
- **URL normalization.** Collapse `/api/users/12345` and `/api/users/67890` into
  `/api/users/{id}` before hashing the finding ID. Otherwise one broken endpoint
  reports as ten thousand separate problems — like getting a new ticket for every car
  that runs the same broken traffic light.
- **Baseline.** Store the normalized findings per target so each run reports only
  what's *new*.

**Done when:** you can break the pipeline on purpose (wrong token, target down) and it
reports a failure instead of a green tick.

---

## Phase 3 — ZAP

**Goal:** find bugs specific to our own code.

**Why it's the big one:** nuclei checks a list of known problems. ZAP is the only tool
that can find a bug we wrote last week. It's also the hardest to set up, which is why
it comes third rather than first.

**The one thing to understand:** ZAP is a security guard who only checks doors that
are on his map. Hand him a map with three doors and he'll check three doors and report
"all secure" — while fifty doors go unchecked. **Filling in the map is most of the
work.** An unseeded ZAP scan reports zero findings and exits successfully.

**Build**
- ZAP as a **sidecar container** running in daemon mode; our adapter drives it over its
  REST API. Keeps the app warm and avoids a 30-second JVM start on every scan.
- Start every scan with a **fresh session**, or last week's findings haunt this week's
  report.
- **Auth:** inject the token as a header on every outgoing request. Simplest thing that
  works, and it covers every ZAP component at once.
- **Exclude the logout URL.** The scanner will happily fuzz `/logout`, log itself out,
  and run the rest of the scan as an anonymous user while reporting nothing.
- **Fill the map** from the OpenAPI spec.
- **Passive first.** Passive is looking at the building from the outside — free and
  safe. Active is actually trying every door and window — finds far more, but sets off
  alarms and can break things. Ship passive on every deploy; keep active nightly and
  advisory.

**Done when:** the tree has roughly as many endpoints as the spec declares, the canary
XSS fires, and passive scan runs on every deploy.

---

## Phase 4 — Schemathesis

**Goal:** catch crashes and contract breaks, and make ZAP much better at the same time.

**Why:** it reads the OpenAPI spec and throws thousands of valid and deliberately
malformed requests at the API. An unhandled 500 is a security finding, not just a bug —
it means unvalidated input reached our code, and it usually leaks a stack trace.

**The trick:** run it **through ZAP as a proxy**. One execution, two payoffs —
Schemathesis reports its own failures, and ZAP's map fills with real, logged-in,
valid traffic. The difference matters: ZAP guessing `id=1` mostly gets 404s, while a
request carrying an ID that actually exists reaches real business logic. It's the
difference between rattling the door handle and walking inside.

**Build**
- `SchemathesisAdapter` with `HTTP_PROXY` pointed at the ZAP sidecar.
- Fixed random seed on the per-deploy run so results are reproducible; unseeded on the
  nightly, where finding new cases is the point.

**Done when:** ZAP's endpoint count jumps after a Schemathesis run.

---

## Phase 5 — Proof, TLS, and turning the gate on

**Goal:** stop reporting maybes, and start blocking releases.

**sqlmap — the proof step.** ZAP flagging a parameter is the metal detector beeping.
sqlmap is opening the bag. It runs **only** against parameters ZAP already flagged,
nightly, in detection mode — never with data-extraction flags, and never on the fast
path. A confirmed SQL injection is worth blocking a release for; a suspected one isn't.

**testssl.sh — the transport check.** Point it at the **real staging hostname**, not
the ephemeral container. The container has no TLS at all — it's terminated upstream at
the load balancer — so scanning the container would report clean forever while the
actual certificate quietly expires. Weekly, not per-commit.

**The gate.** Two speeds:
- **Fast profile** (every deploy): nuclei + ZAP passive + Schemathesis, ~10 minutes.
- **Deep profile** (nightly): everything, advisory only.

Gate on **severity *and* confidence**, not severity alone. A smoke alarm that means
"the kitchen is on fire" and one that means "someone burnt toast" both say *fire* —
you respond to them differently. High severity + low confidence gets reported, not
blocked.

**Turn it on gradually:** nuclei can gate from day one — its checks are exact, so a
finding is almost always real. ZAP needs two to four weeks of observe-only first while
we build the ignore list. Gate too early and the team learns to ignore the pipeline,
which is worse than having no pipeline.

**Done when:** a deploy with a real vulnerability fails the gate, and a clean one
doesn't.

---

## Rules we won't break

- **Staging only** for active scans. They send real attacks and can corrupt data.
  Production gets nuclei and testssl only.
- **Only scan what we own.**
- **Tell on-call** before scheduled scans — they generate load and trip alerts.
- **Never dump data.** sqlmap detects; it does not extract.
- **Pin every tool version and template set**, exactly like the SAST Dockerfile.

---

## Rough sizing

| Phase | Scope | Feel |
|---|---|---|
| 1 | Service + nuclei | ~1 week |
| 2 | Trust layer | ~3 days |
| 3 | ZAP | ~1.5 weeks (auth is the slow part) |
| 4 | Schemathesis | ~3 days |
| 5 | sqlmap, testssl, gate | ~1 week + observation |

Phases 1 and 2 alone already deliver a working, trustworthy pipeline that catches known
vulnerabilities on every deploy. Everything after that is depth.
