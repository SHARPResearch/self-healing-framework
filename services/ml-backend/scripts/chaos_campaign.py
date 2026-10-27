"""
Chaos campaign on the live Online Boutique: real faults with ground truth, for evaluating the
detector and CADAL on a running Kubernetes cluster (Doc3 Phase 8).

For every (service, fault) it injects one Chaos Mesh fault, waits for the fault plus a recovery
gap, and records the fault window. At the end it exports every service's feature rows for the
whole campaign (plus a warm-up hour before it) from Prometheus, so the evaluation can be replayed
offline as often as needed (ml-pipeline/evaluate_live_chaos.py).

Run from services/ml-backend while the cluster is up (infrastructure/online-boutique/up.ps1):

    uv run python scripts/chaos_campaign.py                      # 3 services x 4 faults, ~2 h
    uv run python scripts/chaos_campaign.py --services paymentservice --faults cpu_stress --recover 120

Prometheus keeps 6 hours, so the export must run within 6 hours of the warm-up start; the script
does it automatically at the end (or `--export-only <dir>` to redo it).
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from app.config import settings  # noqa: E402
from app.live_actions import FAULTS, LiveActions  # noqa: E402
from app.prom import OnlineBoutiqueTelemetry, PrometheusClient  # noqa: E402

OUT_ROOT = Path(__file__).resolve().parents[3] / "ml-pipeline" / "outputs" / "live_chaos"
DEFAULT_SERVICES = ("paymentservice", "cartservice", "productcatalogservice")
POD_KILL_WINDOW_S = 300                        # the restarts feature looks back 5 min after a kill


def iso(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def export(run_dir: Path, start: float, end: float, warmup_min: float) -> None:
    tel = OnlineBoutiqueTelemetry(PrometheusClient(settings.prometheus_url), settings.k8s_namespace)
    services = tel.services()
    data = tel.between(services, datetime.fromtimestamp(start - warmup_min * 60, timezone.utc),
                       datetime.fromtimestamp(end, timezone.utc), settings.live_scrape_seconds)
    frames = []
    for svc, rows in data.items():
        if rows:
            df = pd.DataFrame([r for _, r in rows])
            df.insert(0, "time", [t for t, _ in rows])
            df.insert(1, "service", svc)
            frames.append(df)
    pd.concat(frames).to_parquet(run_dir / "telemetry.parquet", index=False)
    print(f"exported {sum(len(f) for f in frames)} rows for {len(frames)} services to {run_dir}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--services", nargs="*", default=list(DEFAULT_SERVICES))
    ap.add_argument("--faults", nargs="*", default=list(FAULTS), choices=FAULTS)
    ap.add_argument("--fault-seconds", type=int, default=180)
    ap.add_argument("--recover", type=int, default=420, help="seconds of calm after each fault")
    ap.add_argument("--warmup-minutes", type=float, default=30,
                    help="clean history before the first fault that the evaluation trains on")
    ap.add_argument("--delay-minutes", type=float, default=0,
                    help="wait this long first, e.g. so the warm-up window misses a fresh cluster's startup")
    ap.add_argument("--export-only", type=Path, default=None)
    args = ap.parse_args()

    if args.export_only:
        meta = json.loads((args.export_only / "meta.json").read_text())
        export(args.export_only, meta["start"], meta["end"], meta["warmup_minutes"])
        return 0

    run_dir = OUT_ROOT / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=True)
    actions = LiveActions(settings.k8s_namespace, fault_seconds=args.fault_seconds)
    plan = [(svc, fault) for fault in args.faults for svc in args.services]
    total = len(plan) * (args.fault_seconds + args.recover)
    print(f"{len(plan)} faults, about {timedelta(seconds=total)}; results in {run_dir}")

    if args.delay_minutes:
        print(f"waiting {args.delay_minutes} min before the first fault", flush=True)
        time.sleep(args.delay_minutes * 60)
    start = time.time()
    with open(run_dir / "windows.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["service", "fault", "start", "end", "start_iso", "chaos"])
        for i, (svc, fault) in enumerate(plan, 1):
            t0 = time.time()
            try:
                info = actions.run(fault, svc)
            except Exception as exc:  # noqa: BLE001 - one failed fault must not end a 2 h run
                print(f"[{i}/{len(plan)}] {fault} on {svc} FAILED: {getattr(exc, 'reason', exc)}", flush=True)
                time.sleep(5)
                continue
            t1 = t0 + (POD_KILL_WINDOW_S if fault == "pod_kill" else args.fault_seconds)
            w.writerow([svc, fault, round(t0, 3), round(t1, 3), iso(t0), info.get("chaos")])
            f.flush()
            print(f"[{i}/{len(plan)}] {iso(t0)} {fault} on {svc}", flush=True)
            time.sleep(max(0.0, t0 + args.fault_seconds + args.recover - time.time()))
    end = time.time()

    (run_dir / "meta.json").write_text(json.dumps({
        "start": start, "end": end, "warmup_minutes": args.warmup_minutes,
        "fault_seconds": args.fault_seconds, "recover_seconds": args.recover,
        "scrape_seconds": settings.live_scrape_seconds, "namespace": settings.k8s_namespace,
        "services": args.services, "faults": args.faults}, indent=2))
    removed = actions.cleanup()
    print(f"campaign done, removed {removed} finished chaos objects")
    export(run_dir, start, end, args.warmup_minutes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
