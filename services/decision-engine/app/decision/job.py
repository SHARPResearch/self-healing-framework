# services/decision-engine/app/decision/job.py
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
from datetime import datetime, timezone
from time import perf_counter

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.api.routes.mock_data import _app, _infra, SERVICES
from app.config import settings
from app.decision.log import build_decision, persist_decision
from app.persistence.postgres import postgres_store
from app.rules.classifier import classify
from app.rules.context import ContextBuilder
from app.rules.engine import rule_engine
from app.decision.executor import ExecutionStatus

log = logging.getLogger(__name__)


def _ms(start: float) -> float:
    """Milliseconds elapsed since `start`, rounded for stable JSON output."""
    return round((perf_counter() - start) * 1000.0, 3)


async def poll_and_decide():
    """
    One cycle of the pipeline: validation → guardrails → execute / shadow / escalate.
    """
    try:
        window = getattr(settings, "DECISION_WINDOW_SEC", 300)
        anomalies = await postgres_store.get_anomalies_without_decisions(
            window_sec=window,
            limit=100,
        )
        if not anomalies:
            return

        log.info("Pipeline: %d new anomalies without decisions", len(anomalies))

        for anomaly in anomalies:
            try:
                sid = anomaly.get("service_id")
                if not sid or sid not in SERVICES:
                    log.warning("Pipeline: unknown service %s, skipping", sid)
                    continue

                # Per-stage wall clock, persisted into decision_log.context.timings
                # so the UI can show measured durations instead of guessing.
                timings: dict[str, float] = {}
                detected = anomaly.get("detected_at")
                if hasattr(detected, "tzinfo"):
                    if detected.tzinfo is None:
                        detected = detected.replace(tzinfo=timezone.utc)
                    timings["queue_ms"] = round(
                        (datetime.now(timezone.utc) - detected).total_seconds() * 1000.0,
                        3,
                    )

                # ── 1. Build context ─────────────────────────────
                t0 = perf_counter()
                builder = ContextBuilder()
                builder.set_services_catalog(SERVICES)
                ctx = builder.build(
                    anomaly,
                    infra=_infra(sid),
                    app=_app(sid),
                    recent_anomalies=anomalies,
                )
                timings["context_ms"] = _ms(t0)

                t0 = perf_counter()
                classify(ctx)
                timings["classify_ms"] = _ms(t0)

                # ── 2. Evaluate rules ────────────────────────────
                t0 = perf_counter()
                candidates = rule_engine.evaluate(ctx)
                timings["rules_ms"] = _ms(t0)

                if not candidates:
                    # NO_RULE_MATCHED — unchanged from before
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
                        "context": {**ctx.to_dict(), "timings": timings},
                    }
                    await postgres_store.save_decision(no_match_row)
                    log.info("Pipeline: NO_MATCH recorded for %s (%s)", anomaly.get("id"), sid)
                    continue

                # ── 3. Build decision (Phase 1) ──────────────────
                from app.decision.action_selector import select_recovery_action
                t0 = perf_counter()
                recovery_action = select_recovery_action(candidates, sid)
                timings["selection_ms"] = _ms(t0)
                if recovery_action is None:
                    log.warning("Pipeline: select_recovery_action returned None for %s", anomaly.get("id"))
                    continue

                t0 = perf_counter()
                decision = build_decision(ctx, candidates)
                timings["severity_ms"] = _ms(t0)
                if decision is None:
                    log.warning("Pipeline: build_decision returned None for %s", anomaly.get("id"))
                    continue

                # ── 4. Validation (Phase 2) ──────────────────────
                from app.decision.validation import validate
                t0 = perf_counter()
                validation = await validate(recovery_action, ctx)
                timings["validation_ms"] = _ms(t0)

                decision.policy_outcome = validation.outcome
                decision.policy_reason = validation.reason

                # ── 5. Guardrails (Phase 3) — only for AUTO_EXECUTE ──
                from app.decision.models import PolicyOutcome
                from app.decision.guardrails import check as guardrails_check, mark as guardrails_mark

                if validation.outcome == PolicyOutcome.AUTO_EXECUTE:
                    t0 = perf_counter()
                    verdict = await guardrails_check(recovery_action, str(anomaly.get("id")))
                    if not verdict.allowed:
                        decision.policy_outcome = PolicyOutcome.BLOCK
                        decision.policy_reason = f"guardrail blocked: {verdict.reason}"
                        log.info(
                            "Pipeline: guardrail BLOCKED %s → %s",
                            anomaly.get("id"), verdict.blocker,
                        )
                    else:
                        # Pass — mark side effects
                        await guardrails_mark(
                            recovery_action, str(anomaly.get("id")), decision.decision_id
                        )
                    timings["guardrails_ms"] = _ms(t0)

                decision.timings = timings

                # ── 6. Persist decision ──────────────────────────
                saved = await persist_decision(decision)
                if not saved:
                    log.warning("Pipeline: failed to persist decision for %s", anomaly.get("id"))
                    continue

                # ── 7. Side effects by outcome ───────────────────
                if decision.policy_outcome == PolicyOutcome.AUTO_EXECUTE:
                    # get_executor(), not the module-level `executor` singleton:
                    # that singleton is always NoopExecutor, so the old import
                    # silently ignored KUBERNETES_DRY_RUN.
                    from app.decision.executor import get_executor
                    result = await get_executor().execute(decision)
                    log.info(
                        "Pipeline: EXECUTED %s → %s status=%s msg=%s",
                        anomaly.get("id"), decision.action.value,
                        result.status.value, result.message,
                    )
                    # Record execution row (Phase B — audit trail)
                    try:
                        await postgres_store.save_execution(result.to_dict())
                    except Exception:
                        log.exception("Pipeline: save_execution failed")

                    # Record outcome for the action_counter/repeat-failure bumps
                    try:
                        outcome_map = {
                            ExecutionStatus.SUCCESS: "SUCCESS",
                            ExecutionStatus.DRY_RUN: "NEUTRAL",
                            ExecutionStatus.SKIPPED: "NEUTRAL",
                            ExecutionStatus.NOT_IMPLEMENTED: "NEUTRAL",
                            ExecutionStatus.FAILED: "FAILED",
                        }
                        await postgres_store.record_action_outcome(
                            decision_id=decision.decision_id,
                            service_id=decision.service_id,
                            action=decision.action.value,
                            outcome=outcome_map.get(result.status, "UNKNOWN"),
                        )
                    except Exception:
                        log.exception("Pipeline: record_action_outcome failed")

                elif decision.policy_outcome == PolicyOutcome.SHADOW_MODE:
                    if validation.shadow_payload:
                        validation.shadow_payload["DECISION_ID"] = decision.decision_id
                        await postgres_store.save_shadow_record(validation.shadow_payload)

                elif decision.policy_outcome == PolicyOutcome.HUMAN_LOOP:
                    from app.decision.escalation import escalate
                    await escalate(
                        decision_id=decision.decision_id,
                        anomaly_id=str(anomaly.get("id")),
                        service_id=sid,
                    )

                log.info(
                    "Pipeline: DECIDED anomaly=%s service=%s action=%s outcome=%s conf=%.3f sev=%.2f(%s)",
                    anomaly.get("id"), sid, decision.action.value,
                    decision.policy_outcome.value,
                    decision.final_conf,
                    decision.severity.effective_severity,
                    decision.severity.label,
                )

                # ── 8. Notify (existing) ─────────────────────────
                try:
                    from app.notifications.emailer import notify_decision_made
                    from app.decision.log import row_to_decision
                    await notify_decision_made(
                        row_to_decision(decision.to_log_row()), anomaly
                    )
                except Exception:
                    log.exception("notify_decision_made failed for %s", anomaly.get("id"))

            except Exception:
                log.exception("Pipeline: error processing anomaly %s", anomaly.get("id"))
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