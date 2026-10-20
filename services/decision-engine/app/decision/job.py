"""
Decision pipeline background job.

Every N seconds:
    1. Fetch anomalies from the last WINDOW seconds that have no decision yet
    2. For each: build context → classify → evaluate → build decision → save
    3. Log each step

Idempotent: an anomaly only gets ONE decision row (checked via LEFT JOIN
in get_anomalies_without_decisions).
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.api.routes.mock_data import _app, _infra, SERVICES
from app.config import settings
from app.decision.log import build_decision, persist_decision
from app.persistence.postgres import postgres_store
from app.rules.classifier import classify
from app.rules.context import ContextBuilder
from app.rules.engine import rule_engine

log = logging.getLogger(__name__)


async def poll_and_decide():
    """
    One cycle of the pipeline:
      - Find anomalies without decisions
      - Decide on each
      - Persist results
    """
    try:
        # ── 1. Fetch new anomalies ──────────────────────────────
        window = getattr(settings, "DECISION_WINDOW_SEC", 300)
        anomalies = await postgres_store.get_anomalies_without_decisions(
            window_sec=window,
            limit=100,
        )
        if not anomalies:
            return

        log.info("Pipeline: %d new anomalies without decisions", len(anomalies))

        # ── 2. For each anomaly ─────────────────────────────────
        for anomaly in anomalies:
            try:
                sid = anomaly.get("service_id")
                if not sid or sid not in SERVICES:
                    log.warning("Pipeline: unknown service %s, skipping", sid)
                    continue

                # Build context
                builder = ContextBuilder()
                builder.set_services_catalog(SERVICES)
                ctx = builder.build(
                    anomaly,
                    infra=_infra(sid),
                    app=_app(sid),
                    recent_anomalies=anomalies,
                )
                classify(ctx)

                # Evaluate rules
                candidates = rule_engine.evaluate(ctx)

                if not candidates:
                        # Write a NO_RULE_MATCHED decision so we don't retry
                    # this anomaly forever. This IS a decision — just a
                    # negative one.
                    import secrets
                    from datetime import datetime as _dt, timezone as _tz

                    now = _dt.now(_tz.utc)
                    no_match_row = {
                        "id": f"DEC-{now.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
                        "anomaly_id": anomaly.get("id"),
                        "service_id": sid,
                        "rule_id": None,
                        "rule_version": None,
                        "action": "NOOP",
                        "action_params": {},
                        "detection_conf": float(anomaly.get("confidence", 0.0)),
                        "rule_conf": 0.0,
                        "final_conf": 0.0,
                        "base_risk": "LOW",
                        "blast_factor": ctx.blast_factor,
                        "centrality": ctx.centrality,
                        "effective_severity": 0.0,
                        "policy_outcome": "NO_RULE_MATCHED",
                        "policy_reason": f"no rule matched {ctx.kind} anomaly for {sid}",
                        "context": ctx.to_dict(),
                    }
                    saved = await postgres_store.save_decision(no_match_row)
                    log.info(
                        "Pipeline: NO_MATCH recorded for %s (%s, kind=%s, saved=%s)",
                        anomaly.get("id"), sid, ctx.kind, saved,
                    )
                    continue

                # Build decision
                decision = build_decision(ctx, candidates)
                if decision is None:
                    log.warning(
                        "Pipeline: build_decision returned None for %s",
                        anomaly.get("id"),
                    )
                    continue

                # Persist
                saved = await persist_decision(decision)
                if saved:
                    log.info(
                        "Pipeline: DECIDED anomaly=%s service=%s action=%s conf=%.3f sev=%.2f(%s)",
                        anomaly.get("id"),
                        sid,
                        decision.action.value,
                        decision.final_conf,
                        decision.severity.effective_severity,
                        decision.severity.label,
                    )
                else:
                    log.warning(
                        "Pipeline: failed to persist decision for %s",
                        anomaly.get("id"),
                    )

            except Exception:
                log.exception(
                    "Pipeline: error processing anomaly %s",
                    anomaly.get("id"),
                )
                continue

    except Exception:
        log.exception("Pipeline: poll_and_decide crashed")


def start_decision_pipeline(scheduler: AsyncIOScheduler):
    """Register the pipeline job on the scheduler."""
    interval = getattr(settings, "DECISION_POLL_INTERVAL_SEC", 10)
    scheduler.add_job(
        poll_and_decide,
        "interval",
        seconds=interval,
        id="decision_pipeline",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    log.info("Decision pipeline scheduled (every %ss)", interval)