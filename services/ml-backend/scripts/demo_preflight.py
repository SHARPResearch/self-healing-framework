"""
Pre-demo check: is the whole stack up and calm? Run from services/ml-backend:

    uv run python scripts/demo_preflight.py            # check only
    uv run python scripts/demo_preflight.py --reset    # also reset the fleet first (recommended)

Uses only the standard library. Exit code 0 means every check passed.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

BACKEND = "http://localhost:8002"
FRONTEND = "http://localhost:5173"
EXPECTED_SERVICES = 6
DEMO_SERVICES = {"service-a-auth", "service-c-inventory", "service-e-payments"}
TARGET_EPS = 60

results: list[tuple[str, bool, str]] = []


def call(url: str, method: str = "GET", timeout: float = 8.0):
    req = urllib.request.Request(url, method=method, data=b"{}" if method == "POST" else None,
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail else ""))
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="reset the fleet before checking")
    args = parser.parse_args()

    print("Backend")
    try:
        health = call(f"{BACKEND}/api/health")
    except (urllib.error.URLError, OSError) as exc:
        check("ml-backend reachable on :8002", False,
              f"{exc}. Start it: cd services/ml-backend; uv run uvicorn app.main:app --port 8002")
        return 1
    check("ml-backend reachable on :8002", True)
    check("TimescaleDB connected", bool(health["db"]),
          "" if health["db"] else "running on the in-memory fallback; start Docker and restart the backend")
    check("Redis connected", bool(health["redis"]),
          "" if health["redis"] else "running on the in-process fallback; start Docker and restart the backend")
    check(f"{EXPECTED_SERVICES} services loaded", health["services"] == EXPECTED_SERVICES, str(health["services"]))

    if args.reset:
        print("Reset")
        call(f"{BACKEND}/api/demo/reset", "POST", timeout=60)
        time.sleep(3)
        check("fleet reset", True)

    health = call(f"{BACKEND}/api/health")
    first = health["tick"]
    time.sleep(4)
    second = call(f"{BACKEND}/api/health")
    rate = (second["tick"] - first) / 4
    check("replay running at about 60 events/s", not second["paused"] and rate >= TARGET_EPS * 0.8,
          f"{rate:.0f} events/s" + (", paused" if second["paused"] else ""))

    print("Calm")
    models = call(f"{BACKEND}/api/models")
    services = call(f"{BACKEND}/api/services")
    queries = call(f"{BACKEND}/api/queries?status=open")
    check("no open operator queries", not queries, f"{len(queries)} open" if queries else "")
    # Only the services the script injects into have to be calm. Others (Shipping often opens a
    # harmless drift check right after a reset) can be mid-quarantine without affecting the demo.
    demo = [s for s in services if s["serviceId"] in DEMO_SERVICES]
    busy = [s["displayName"] for s in demo if s["phase"] != "stable" and s.get("quarantineTrigger") != "scheduled"]
    check("demo services (Auth, Inventory, Payments) not in a drift quarantine", not busy, ", ".join(busy))
    alarming = [s["displayName"] for s in demo if s["alarm"]]
    check("demo services not alarming right now", not alarming, ", ".join(alarming))
    others = [s["displayName"] for s in services if s not in demo and s["phase"] != "stable"
              and s.get("quarantineTrigger") != "scheduled"]
    if others:
        print(f"  [note] {', '.join(others)} in a drift check: normal after a reset, no action needed")
    high = [f"{m['serviceName']} v{m['productionVersion']}" for m in models if m["productionVersion"] > 12]
    check("model versions still low (reset recently)", not high,
          ", ".join(high) + " (checkpoints add a version every ~48 s; use --reset)" if high else "")

    print("Logs")
    try:
        logged = {s["service"] for s in call(f"{BACKEND}/api/logs/services")}
        for name in ("TimescaleDB", "Redis", "ml-backend"):
            check(f"{name} logs flowing", name in logged,
                  "" if name in logged else "container not found? check Docker, or LOG_CONTAINERS")
    except (urllib.error.URLError, OSError) as exc:
        check("logs api", False, str(exc))

    print("Frontend")
    try:
        proxied = call(f"{FRONTEND}/api/health")
        check("Vite dev server proxies /api to the backend", proxied["status"] == "ok")
    except (urllib.error.URLError, OSError) as exc:
        check("Vite dev server on :5173", False, f"{exc}. Start it: cd frontend; pnpm dev")

    failed = [n for n, ok, _ in results if not ok]
    print()
    if failed:
        print(f"{len(failed)} check(s) failed: " + "; ".join(failed))
        return 1
    print("All checks passed. Open http://localhost:5173/model-lifecycle")
    return 0


if __name__ == "__main__":
    sys.exit(main())
