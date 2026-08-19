"""Live DAST smoke test: drive the real ZAP sidecar against OWASP Juice Shop.

Why this bypasses ``ZapAdapter.scan()``: the adapter deliberately refuses to run
without an OpenAPI spec to seed from and a working canary route (both are part of
the Phase 2 trust model). Juice Shop serves neither, so a full ``run_scan`` against
it honestly reports two ``incomplete`` entries. To exercise the *real* ZAP REST
wiring and our pure ``parse()`` against live alerts, this driver seeds with the
spider instead of a spec and skips the canary gate — the same thing integration
task 9.1 does, adapted for a target that lacks our canary/spec.

Usage (with the compose harness up):
    docker compose -f docker-compose.juiceshop.yml up -d
    python scripts/live_zap_juiceshop.py [--active]

It talks to ZAP on 127.0.0.1:8090 (host) and points ZAP at http://juiceshop:3000
(the target's name on the compose network).
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter

import httpx

from dast.adapters.zap_adapter import ZapAdapter
from dast.adapters.zap_client import ZapClient
from dast.intelligence import consolidate

# ZAP is reachable on the host; the target is reachable from ZAP by its compose name.
ZAP_HOST = "127.0.0.1"
ZAP_PORT = 8090
TARGET_URL = "http://juiceshop:3000"
LOGOUT_EXCLUDE = r".*/logout.*"


def _wait_for_zap(client: ZapClient, *, attempts: int = 30, delay: float = 2.0) -> None:
    """Poll the daemon until its REST API answers (the container takes a bit to boot)."""
    for i in range(1, attempts + 1):
        try:
            client.reachable()
            return
        except Exception as exc:  # noqa: BLE001 - retry until the daemon is warm
            print(f"  waiting for ZAP daemon ({i}/{attempts})... {exc}")
            time.sleep(delay)
    raise SystemExit("ZAP daemon never became reachable on 127.0.0.1:8090")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--active",
        action="store_true",
        help="Also run an active scan (sends attack payloads; slow). Passive-only by default.",
    )
    parser.add_argument(
        "--queue",
        action="store_true",
        help="Throttled per-endpoint active scan: scan site-tree URLs one at a time "
        "with low thread count (laptop-safe). Implies --active.",
    )
    parser.add_argument(
        "--threads-per-host",
        type=int,
        default=1,
        help="ZAP active-scan threads per host (concurrency cap; default 1 = serial).",
    )
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=100,
        help="Delay between active-scan requests in ms (rate throttle; default 100).",
    )
    parser.add_argument(
        "--max-endpoints",
        type=int,
        default=0,
        help="In --queue mode, cap how many endpoints to scan (0 = all). Useful for a smoke test.",
    )
    args = parser.parse_args()
    if args.queue:
        args.active = True

    # No API key: the live harness starts ZAP with api.disablekey=true.
    # Inject a long-timeout httpx client: under active-scan load the single ZAP
    # daemon can be slow to answer a status poll, and the client's default 30s
    # per-call timeout would otherwise abort the whole scan. This exercises the
    # constructor's injectable-client seam rather than changing production code.
    base_url = f"http://{ZAP_HOST}:{ZAP_PORT}"
    http = httpx.Client(base_url=base_url, timeout=180.0)
    client = ZapClient(host=ZAP_HOST, port=ZAP_PORT, api_key=None, client=http)

    print(f"[1/7] Connecting to ZAP at {ZAP_HOST}:{ZAP_PORT} ...")
    _wait_for_zap(client)
    print("      reachable.")

    print("[2/7] Starting a fresh session ...")
    client.new_session(f"juiceshop-live-{int(time.time())}")

    print(f"[3/7] Excluding logout URLs ({LOGOUT_EXCLUDE}) ...")
    client.exclude_from_scan(LOGOUT_EXCLUDE)

    print(f"[4/7] Seeding the site tree by spidering {TARGET_URL} ...")
    client.spider(TARGET_URL)
    seeded = client.urls(base_url=TARGET_URL)
    print(f"      {len(seeded)} URL(s) on the site tree.")

    print("[5/7] Passive scan (waiting for the queue to drain) ...")
    client.passive_scan_wait()

    if args.queue:
        # Throttle ZAP's active scanner first: 1 thread/host ~= one attack request
        # in flight at a time, plus a small inter-request delay. This is what keeps
        # a laptop Docker Desktop from being pegged for the whole run.
        client.set_active_scan_options(
            thread_per_host=args.threads_per_host,
            host_per_scan=1,
            delay_ms=args.delay_ms,
        )
        targets = [u for u in seeded if "/logout" not in u]
        if args.max_endpoints > 0:
            targets = targets[: args.max_endpoints]
        print(
            f"[6/7] Queued active scan: {len(targets)} endpoint(s), "
            f"threads/host={args.threads_per_host}, delay={args.delay_ms}ms ..."
        )
        for i, url in enumerate(targets, 1):
            try:
                # recurse=False: attack only THIS node, so peak load stays bounded.
                # tolerate_timeouts: ride out brief REST stalls under scan load.
                client.active_scan(url, recurse=False, tolerate_timeouts=5)
                print(f"      [{i}/{len(targets)}] done: {url[:72]}")
            except Exception as exc:  # noqa: BLE001 - one endpoint failing != whole run
                print(f"      [{i}/{len(targets)}] FAILED ({exc}); continuing: {url[:60]}")
    elif args.active:
        print(f"[6/7] Active scan against {TARGET_URL} (whole tree; this is slow) ...")
        client.active_scan(TARGET_URL, tolerate_timeouts=5)
    else:
        print("[6/7] Skipping active scan (pass --active or --queue to enable).")

    print("[7/7] Collecting alerts + request evidence ...")
    alerts = client.alerts(base_url=TARGET_URL)
    requests_made = client.requests_made(base_url=TARGET_URL)
    request_errors = client.request_errors()
    timeouts = client.timeouts()

    # Run the LIVE alerts through our pure parser — the real point of this test.
    findings = ZapAdapter.parse(
        alerts,
        scanner_name="zap-active" if args.active else "zap-passive",
        advisory=args.active,
    )

    # Run the parsed findings through the shared normalize -> dedupe chain so the
    # 400-URLs-one-rule explosion collapses to stable finding_ids, exactly as the
    # real service does before baselining.
    consolidated = consolidate(tuple(findings))
    deduped = consolidated.findings

    print("\n" + "=" * 68)
    print("LIVE ZAP SCAN RESULT — OWASP Juice Shop")
    print("=" * 68)
    print(f"  requests_made   : {requests_made}")
    print(f"  request_errors  : {request_errors}")
    print(f"  timeouts        : {timeouts}")
    print(f"  raw alerts      : {len(alerts)}")
    print(f"  parsed findings : {len(findings)}")
    print(f"  deduped findings: {len(deduped)}  (via consolidate -> stable finding_id)")

    by_sev = Counter(f.severity.name for f in deduped)
    if by_sev:
        print("\n  deduped findings by severity:")
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            if by_sev.get(sev):
                print(f"    {sev:<9}: {by_sev[sev]}")

    # Advisory is a Finding-level flag; report it from the pre-normalize findings
    # since Normalized_Finding does not carry it (that is wired in a later phase).
    advisory_findings = sum(1 for f in findings if getattr(f, "advisory", False))
    print(f"  advisory (active): {advisory_findings} of {len(findings)} parsed findings")

    print("\n  sample deduped findings (first 15):")
    for f in deduped[:15]:
        print(f"    [{f.severity.name:<6}] {f.rule_identity:<10} {f.message[:66]}")

    print("\n" + "=" * 68)
    if requests_made and request_errors < requests_made:
        print("RESULT: ZAP reached the target and produced real request evidence. PASS.")
        return 0
    print("RESULT: no usable request evidence — check the harness/network. FAIL.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
