# Decision Package — Component 2 Pipeline

The `app/decision/` package is the **runtime brain** of Component 2. It
consumes anomaly signals from Component 1, evaluates the rule set, picks
a recovery action, validates it through the Trust & Safety layer,
enforces safety guardrails, and routes the outcome to one of four paths:

- **execute** (via the Kubernetes / Noop executor)
- **shadow** (via the counterfactual observer)
- **escalate** (via the human-in-the-loop queue)
- **block** (log only)

This package is where the rule engine's abstract output becomes a
concrete, auditable **decision**. It is the concrete implementation of
**§3 (Decision and Strategy Engine)** of the Component 2 report.

Three sub-packages have their own READMEs:

- [`validation/`](validation/README.md) — Trust & Safety gate
- [`guardrails/`](guardrails/README.md) — cooldown, counters, idempotency
- [`escalation/`](escalation/README.md) — human-in-the-loop delivery

This README covers everything else in `app/decision/` **and** the
end-to-end pipeline that ties the three sub-packages together with the
rule engine, persistence, and API layers.

---

## 1. What this package does

Every decision goes through five stages:

| Stage            | Input                                                | What happens                                                                                               | Output             |
| ---------------- | ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | ------------------ |
| **1. Compose**   | `AnomalyContext` + `RuleCandidate[]`                 | Compute severity, select the winning candidate, wrap it in a `RecoveryAction` with a blast-radius analysis | `Decision` (draft) |
| **2. Validate**  | `RecoveryAction` + `AnomalyContext`                  | Confidence + risk + conflict → policy matrix → one of 4 outcomes                                           | `ValidationResult` |
| **3. Guardrail** | `RecoveryAction` + `anomaly_id`                      | Cooldown / counter / idempotency — only for `AUTO_EXECUTE`                                                 | `GuardrailVerdict` |
| **4. Route**     | `Decision` + `ValidationResult` + `GuardrailVerdict` | Persist + dispatch to executor / shadow / escalation / block                                               | side effects       |
| **5. Observe**   | Persisted rows                                       | Background jobs fill in shadow verdicts and fire escalation attempts                                       | metrics / emails   |

The package is **stateless** — all state lives in Postgres, TimescaleDB,
Neo4j, or Redis. Every job can run in any order, and every attempt is
idempotent. Restart-safe by construction.

---

## 2. Where it lives

```

app/decision/
├── README.md ← this file
├── models.py Decision, PolicyOutcome, SeverityBreakdown, ActionSelection
├── severity.py base × centrality × blast → normalized severity
├── action_selector.py picks the winning RuleCandidate; wraps in RecoveryAction
├── blast_analysis.py decision-facing blast-radius view (LOW/MED/HIGH risk)
├── log.py persist_decision, build_decision, row_to_decision
├── job.py the pipeline — poll_and_decide, start_decision_pipeline
├── executor.py Executor protocol + NoopExecutor + get_executor factory
├── executor_kubernetes.py real Kubernetes executor (RESTART/SCALE/ROLLBACK/YARP)
├── shadow_observer.py fills shadow counterfactual verdicts
├── validation/ Trust & Safety (see validation/README.md)
├── guardrails/ safety rails (see guardrails/README.md)
└── escalation/ human-in-the-loop (see escalation/README.md)

```

Adjacent packages this one consumes:

| Package            | Role in the pipeline                                                 | README                                                                  |
| ------------------ | -------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `app/rules/`       | Builds `AnomalyContext`, evaluates rules, produces `RuleCandidate[]` | (no dedicated README — see `app/rules/readme.md` for the rule language) |
| `app/core/`        | GraphStore, CentralityCalculator, BlastRadiusAnalyzer                | (covered inline)                                                        |
| `app/persistence/` | Postgres, Timescale, Neo4j clients                                   | (covered in §7)                                                         |
| `app/ingestion/`   | Telemetry puller, anomaly sink, ring buffer                          | (covered in §7)                                                         |
| `app/api/routes/`  | HTTP surface                                                         | (covered in §8)                                                         |

---

## 3. Key data structures

### `Decision`

The full record that flows through the pipeline. Every field is
persisted in `decision_log`:

```python
class Decision(BaseModel):
    decision_id: str                  # DEC-YYYYMMDD-HHMMSS-xxxx
    anomaly_id: str
    service_id: str
    rule_id: str
    rule_version: int
    action: ActionType
    action_params: dict
    detection_conf: float
    rule_conf: float
    final_conf: float
    severity: SeverityBreakdown
    base_risk: RiskLevel
    blast_factor: float
    centrality: float
    guardrails: RuleGuardrail
    selection: ActionSelection      # winner + rejected candidates
    service_health: str
    anomaly_kind: str                # ISOLATED / UPSTREAM / CASCADING / NORMAL
    upstream: list[str]
    downstream: list[str]
    blast_members: list[str]
    policy_outcome: PolicyOutcome    # filled by validation layer
    policy_reason: str
    created_at: datetime
```

### `PolicyOutcome`

The four-way routing decision from §3.3:

```python
class PolicyOutcome(str, Enum):
    AUTO_EXECUTE       = "AUTO_EXECUTE"        # confidence ≥ 0.85 AND risk = LOW
    SHADOW_MODE        = "SHADOW_MODE"         # 0.60 ≤ confidence < 0.85
    HUMAN_LOOP         = "HUMAN_LOOP"          # risk = HIGH or repeat-failure ≥ 2
    BLOCK              = "BLOCK"               # confidence < 0.60 or conflict
    NO_RULE_MATCHED    = "NO_RULE_MATCHED"     # terminal negative outcome
    PENDING_VALIDATION = "PENDING_VALIDATION"  # reserved
```

### `SeverityBreakdown`

Full severity trace: `base_severity × centrality × blast_factor`, then
normalized to `[0, 1]` and mapped to `LOW/MEDIUM/HIGH/CRITICAL`.

### `RecoveryAction`

Phase 1 wrapper — a `RuleCandidate` plus its blast-radius analysis:

```python
@dataclass
class RecoveryAction:
    rule_id: str
    rule_version: int
    action: ActionType
    params: dict
    service_id: str
    confidence: float                 # blended
    base_risk: RiskLevel              # from the rule
    blast: BlastRadiusAnalysis        # decision-facing view
    guardrails: dict
    rationale: str
    # property: effective_risk = max(base_risk, blast.recommended_risk)
```

This is what `validate(...)` and `guardrails.check(...)` operate on.

### `ExecutionResult`

Returned by every executor. `status` is one of `SUCCESS / FAILED /
DRY_RUN / SKIPPED / NOT_IMPLEMENTED`, and `message` is a human-readable
one-liner. Persisted in `execution_log` for the §8.2 metrics.

---

## 4. How it fits in the pipeline

### Startup (`main.py::lifespan`)

```
1. Connect Neon, Tiger, Neo4j
2. Run migrations (idempotent, batched)
3. Load runtime settings from DB → apply to settings singleton
4. Load static topology into GraphStore → mirror to Neo4j
5. Seed rules (first boot) → load registry from DB
6. Select executor (Noop if KUBERNETES_DRY_RUN=true)
7. Start APScheduler
8. Register jobs:
     telemetry_puller    (10s)   → ring buffer
     anomaly_sink        (5s)    → anomaly_events + 2-phase snapshots
     decision_pipeline   (10s)   → THIS PACKAGE  ◄──
     escalation_worker   (30s)   → fire due escalations
     shadow_observer     (60s)   → fill shadow verdicts
9. Resume pending snapshots + do one immediate telemetry pull
```

### Runtime (`job.py::poll_and_decide`, every 10s)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Fetch anomalies without decisions                            │
│    get_anomalies_without_decisions(window_sec, limit=100)       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. For each anomaly:                                            │
│    - Build AnomalyContext (graph + telemetry)                   │
│    - classify(ctx)                                              │
│    - rule_engine.evaluate(ctx) → candidates                     │
│    - If empty → NO_RULE_MATCHED decision + continue             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. select_recovery_action(candidates, sid)  → RecoveryAction    │
│ 4. build_decision(ctx, candidates)          → Decision (draft)  │
│ 5. validate(recovery_action, ctx)           → ValidationResult  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. If AUTO_EXECUTE:                                             │
│      guardrails.check(...) → verdict                            │
│      if not allowed: downgrade to BLOCK                         │
│      else: guardrails.mark(...)                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. persist_decision(decision) → decision_log                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. Route by outcome:                                            │
│    AUTO_EXECUTE → executor.execute(decision)                    │
│                  → save_execution + record_action_outcome        │
│    SHADOW_MODE  → save_shadow_record(shadow_payload)            │
│    HUMAN_LOOP   → escalate(decision_id, anomaly_id, service_id) │
│    BLOCK        → nothing (decision_log is the record)          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. Notify (emailer.notify_decision_made) — fire-and-forget      │
└─────────────────────────────────────────────────────────────────┘
```

### Background observation

After the pipeline returns, two independent workers close the loop:

- **`escalation.worker`** — fires due escalations (initial → reminder →
  final). See `escalation/README.md`.
- **`shadow_observer.observe_once`** — watches shadow records, fills in
  `ACTUAL_OUTCOME` and `VERDICT` once the anomaly resolves. See §8.2 of
  the proposal for the metrics this produces.

---

## 5. Public API

### Pipeline entry

| Function                             | Module   | Purpose                   |
| ------------------------------------ | -------- | ------------------------- |
| `poll_and_decide() -> None`          | `job.py` | One cycle of the pipeline |
| `start_decision_pipeline(scheduler)` | `job.py` | Register APScheduler job  |

### Composition (Phase 1)

| Function                                              | Module               | Returns                   |
| ----------------------------------------------------- | -------------------- | ------------------------- |
| `compute_severity(anomaly, centrality, blast_factor)` | `severity.py`        | `SeverityBreakdown`       |
| `select_action(candidates)`                           | `action_selector.py` | `ActionSelection \| None` |
| `select_recovery_action(candidates, service_id, ...)` | `action_selector.py` | `RecoveryAction \| None`  |
| `enrich_with_blast(candidate, service_id, ...)`       | `action_selector.py` | `RecoveryAction`          |
| `blast_analysis.analyze(service_id, action, ...)`     | `blast_analysis.py`  | `BlastRadiusAnalysis`     |

### Persistence

| Function                          | Module   | Returns            |
| --------------------------------- | -------- | ------------------ |
| `make_decision_id()`              | `log.py` | `str` (`DEC-...`)  |
| `build_decision(ctx, candidates)` | `log.py` | `Decision \| None` |
| `persist_decision(decision)`      | `log.py` | `bool`             |
| `row_to_decision(row)`            | `log.py` | `dict` (JSON-safe) |

### Executor

| Function                               | Module                   | Returns                                |
| -------------------------------------- | ------------------------ | -------------------------------------- |
| `get_executor() -> Executor`           | `executor.py`            | `NoopExecutor` or `KubernetesExecutor` |
| `KubernetesExecutor.execute(decision)` | `executor_kubernetes.py` | `ExecutionResult`                      |
| `NoopExecutor.execute(decision)`       | `executor.py`            | `ExecutionResult` (`NOT_IMPLEMENTED`)  |

### Shadow observer

| Function                                           | Module               | Returns                     |
| -------------------------------------------------- | -------------------- | --------------------------- |
| `observe_once() -> int`                            | `shadow_observer.py` | Number of shadows finalized |
| `resolve_manually(shadow_id, ...) -> dict \| None` | `shadow_observer.py` | Updated shadow row          |
| `start_shadow_observer(scheduler)`                 | `shadow_observer.py` | `None`                      |

### Sub-package entry points

| Function                                         | Import                                              | README                                       |
| ------------------------------------------------ | --------------------------------------------------- | -------------------------------------------- |
| `validate(recovery_action, ctx)`                 | `from app.decision.validation import validate`      | [validation/README.md](validation/README.md) |
| `guardrails.check(...)` / `guardrails.mark(...)` | `from app.decision.guardrails import check, mark`   | [guardrails/README.md](guardrails/README.md) |
| `escalate(...)` / `ack(...)`                     | `from app.decision.escalation import escalate, ack` | [escalation/README.md](escalation/README.md) |

---

## 6. Configuration

Every tunable in this package is either an env var or a runtime setting
(the latter can be changed live via `/api/settings`). Full env template
is in `.env.example` at the service root.

### A. Pipeline tuning

| Env var                      | Type  | Default | Runtime-tunable | Purpose                                 |
| ---------------------------- | ----- | ------- | --------------- | --------------------------------------- |
| `DECISION_POLL_INTERVAL_SEC` | `int` | 10      | ✅              | Pipeline cycle interval                 |
| `DECISION_WINDOW_SEC`        | `int` | 300     | ✅ (premium)    | Lookback for new anomalies              |
| `INCIDENT_RECOVERY_HOLD_SEC` | `int` | 30      | ❌              | How long healthy before incident closes |

### B. Executor tuning

| Env var                          | Type   | Default   | Purpose                                          |
| -------------------------------- | ------ | --------- | ------------------------------------------------ |
| `KUBERNETES_DRY_RUN`             | `bool` | `1`       | `1` → `NoopExecutor`; `0` → `KubernetesExecutor` |
| `KUBERNETES_NAMESPACE`           | `str`  | `default` | Namespace for all API calls                      |
| `KUBERNETES_IN_CLUSTER`          | `bool` | `0`       | `1` → ServiceAccount; `0` → kubeconfig           |
| `KUBERNETES_REQUEST_TIMEOUT_SEC` | `int`  | 20        | API timeout                                      |
| `KUBERNETES_DEFAULT_GRACE_SEC`   | `int`  | 30        | Pod delete grace period                          |

### C. Shadow observer tuning

| Env var                       | Type  | Default | Runtime-tunable | Purpose                                  |
| ----------------------------- | ----- | ------- | --------------- | ---------------------------------------- |
| `SHADOW_OBSERVE_INTERVAL_SEC` | `int` | 60      | ✅              | Observer cycle                           |
| `SHADOW_MIN_AGE_SEC`          | `int` | 300     | ✅ (premium)    | Minimum age before observing             |
| `SHADOW_MAX_WAIT_MIN`         | `int` | 60      | ✅ (premium)    | Max time before declaring `STILL_ACTIVE` |

### D. Constants in code (not runtime-tunable)

| Constant                 | Module              | Value                     | Meaning                                             |
| ------------------------ | ------------------- | ------------------------- | --------------------------------------------------- |
| `_MAX_EFFECTIVE`         | `severity.py`       | `2.7`                     | Max severity before normalization (0.9 × 2.0 × 1.5) |
| `_LABEL_THRESHOLDS`      | `severity.py`       | `[0.75, 0.55, 0.35, 0.0]` | CRITICAL/HIGH/MEDIUM/LOW cutoffs                    |
| `HUB_THRESHOLD`          | `blast_analysis.py` | `4`                       | Reverse-reachable size ≥ 4 = hub                    |
| `MEDIUM_FACTOR`          | `blast_analysis.py` | `1.15`                    | Blast factor for MEDIUM risk                        |
| `_ACTION_INTRINSIC_RISK` | `blast_analysis.py` | (dict)                    | Per-action baseline risk (0.0–0.8)                  |

These are design-doc-derived constants, not operator knobs. Changing
them requires a code change and a restart, which is intentional.

---

## 7. Failure modes

The package is **fail-open on infra errors, fail-closed on safety
violations**. Every layer documents its own failure mode; this section
documents the ones that span multiple layers.

### Pipeline-level

| Condition                           | Behaviour                                                                              |
| ----------------------------------- | -------------------------------------------------------------------------------------- |
| Anomaly references unknown service  | Log warning, skip. Anomaly is orphaned but not lost.                                   |
| `rule_engine.evaluate` returns `[]` | Persist `NO_RULE_MATCHED` decision (terminal, no retry).                               |
| `build_decision` returns `None`     | Log warning, skip. Rare — means the winning candidate's payload was malformed.         |
| `persist_decision` fails            | Log warning, continue. The anomaly will be retried next cycle (still no decision row). |
| Exception during one anomaly        | Logged, `continue` — one bad anomaly doesn't stall the batch.                          |
| Exception at batch level            | Logged — next cycle retries everything.                                                |

### Executor-level

| Condition                                 | Behaviour                                                                                                           |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `KUBERNETES_DRY_RUN=true`                 | `NoopExecutor` returns `NOT_IMPLEMENTED`. `save_execution` still runs.                                              |
| `KUBERNETES_DRY_RUN=false` but no cluster | `KubernetesExecutor.__init__` raises; `get_executor()` catches and falls back to `NoopExecutor`. **The app boots.** |
| K8s API call fails (timeout, 403)         | `ExecutionResult(status=FAILED)`. `record_action_outcome(outcome=FAILED)` feeds the repeat-failure bump.            |
| Action handler raises                     | Caught by `execute()` → `FAILED` with exception message.                                                            |

### Shadow observer

| Condition                                         | Behaviour                                                                          |
| ------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Anomaly resolves naturally within expected window | `VERDICT = ACTION_WOULD_HAVE_BEEN_UNNECESSARY`                                     |
| Anomaly resolves slowly (>1.5× expected)          | `VERDICT = ACTION_WOULD_HAVE_HELPED`                                               |
| Escalation acked `APPROVED`                       | `resolution_path = ESCALATION_APPROVED`                                            |
| Escalation acked `REJECTED`                       | `force_verdict = UNKNOWN`                                                          |
| Anomaly still active past `SHADOW_MAX_WAIT_MIN`   | `mark_shadow_abandoned` → `VERDICT = ANOMALY_STILL_ACTIVE` (excluded from metrics) |
| Postgres unavailable                              | Logged, retry next cycle                                                           |

### Cross-cutting known limitations

1. **The 4-outcome matrix can starve `AUTO_EXECUTE`.** In a topology
   where every service has dependents, `blast.recommended_risk` is never
   `LOW`, so no decision reaches `AUTO_EXECUTE`. This is _correct_
   (the framework defers when uncertain) but requires at least one
   **leaf service** (e.g. `metrics-collector`) to demo the executor
   path end-to-end.

2. **`layers: ["*"]` in a rule's `applies_to` requires the `RuleAppliesTo`
   wildcard fix.** Fixed in `models.py::RuleAppliesTo.matches` — the
   check is now `if self.layers and "*" not in self.layers and layer not in self.layers`.
   Any rule added with `layers: ["*"]` before this fix will silently
   not match — worth auditing existing rules if in doubt.

3. **`save_execution` + `record_action_outcome` are two writes, not one
   transaction.** If the first succeeds but the second fails, the
   execution is logged but the repeat-failure counter doesn't see it.
   Acceptable: the counter is defensive, not authoritative.

---

## 8. Tests

All tests run without external dependencies except where noted. Expected
green count across the whole package: **~65** (Phase 1 + 2 + 3 + 4 + A + B).

| Test file                                | Covers                                                          |
| ---------------------------------------- | --------------------------------------------------------------- |
| `tests/test_blast_analysis.py`           | `BlastRadiusAnalyzerDecision` — leaf/hub/intrinsic-risk logic   |
| `tests/test_action_selector_recovery.py` | `select_recovery_action`, `enrich_with_blast`, `effective_risk` |
| `tests/test_executor.py`                 | `NoopExecutor` status + detail                                  |
| `tests/test_validation_confidence.py`    | Graph-certainty, band thresholds                                |
| `tests/test_validation_risk.py`          | Risk `max()`, repeat-failure bump                               |
| `tests/test_validation_policy.py`        | Full §3.3 policy matrix                                         |
| `tests/test_validation_shadow.py`        | §4.4 JSON shape, verdict logic                                  |
| `tests/test_validation_orchestrator.py`  | Full validate() flow                                            |
| `tests/test_guardrails_store.py`         | `InMemoryStore`                                                 |
| `tests/test_guardrails_cooldown.py`      | Cooldown, `cooldown_seconds=0`                                  |
| `tests/test_guardrails_counter.py`       | Per-hour cap                                                    |
| `tests/test_guardrails_idempotency.py`   | Key rendering, idempotency                                      |
| `tests/test_guardrails_orchestrator.py`  | All checks + short-circuit                                      |
| `tests/test_escalation_queue.py`         | State machine transitions                                       |
| `tests/test_escalation_templates.py`     | Three templates                                                 |
| `tests/test_escalation_routes.py`        | HTTP layer                                                      |
| `tests/test_shadow_observer.py`          | Verdict classification, `observe_once`                          |
| `tests/test_shadow_routes.py`            | Shadow HTTP + manual resolve                                    |
| `tests/test_executor_factory.py`         | `get_executor()` selection + fallback                           |
| `tests/test_executor_kubernetes.py`      | Handlers against mocked K8s client                              |

Run all:

```bash
cd services/decision-engine
uv run pytest tests/ -v
```

### End-to-end live verification

**1. Full pipeline, SHADOW path:**

```bash
curl -X POST http://localhost:8000/api/mock/scenario/all_healthy
sleep 40
curl -X POST http://localhost:8000/api/mock/scenario/isolated_orders_slow
sleep 25
curl "http://localhost:8000/api/decisions/recent?limit=1"
# → decision with policy.outcome = SHADOW_MODE
curl http://localhost:8000/api/decisions/shadow
# → at least one shadow record with verdict=null
```

**2. Full pipeline, HUMAN_LOOP path:**

```bash
curl -X POST http://localhost:8000/api/mock/scenario/payment_slowdown
sleep 25
curl http://localhost:8000/api/decisions/escalations
# → escalation rows exist
```

**3. Full pipeline, AUTO_EXECUTE path (requires leaf-service scenario):**

```bash
curl -X POST http://localhost:8000/api/mock/scenario/all_healthy
sleep 40
curl -X POST http://localhost:8000/api/mock/scenario/metrics_collector_slow
sleep 25
curl "http://localhost:8000/api/decisions/recent?limit=1"
# → decision with policy.outcome = AUTO_EXECUTE (requires restart_isolated_leaf_service rule)
curl http://localhost:8000/api/executions
# → {"count": 1, "executions": [{"status": "NOT_IMPLEMENTED", ...}]}
```

**4. BLOCK path (guardrail):**

```bash
# Immediately re-trigger the same scenario from step 3
curl -X POST http://localhost:8000/api/mock/scenario/metrics_collector_slow
sleep 25
curl "http://localhost:8000/api/decisions/recent?limit=1"
# → decision with policy.outcome = BLOCK and reason starting with "guardrail blocked:"
```

---

## 9. Research mapping

This package implements §3 and §4 of the Component 2 report, and §3.4,
§4.3, §7, §8.2 of the research proposal.

### Component 2 report

| Report section                                                         | Implemented in                                             |
| ---------------------------------------------------------------------- | ---------------------------------------------------------- |
| §3.1 Input processing (anomaly receiver, graph query, telemetry fetch) | `app/ingestion/` + `app/rules/context.py`                  |
| §3.2 Dependency graph manager                                          | `app/core/` + `app/topology/`                              |
| §3.3 Rule engine (isolated / upstream / cascading / root cause)        | `app/rules/`                                               |
| §3.4 Severity + action selection                                       | `severity.py` + `action_selector.py`                       |
| §3.5 Blast radius analysis                                             | `blast_analysis.py` + `app/core/blast_radius.py`           |
| §3.6 Trust & Safety validation layer                                   | `validation/`                                              |
| §3.7 Safety guardrails                                                 | `guardrails/`                                              |
| §3.8 Human escalation + Gmail 3-attempt                                | `escalation/`                                              |
| §4.1 What is Shadow Mode                                               | `validation/shadow.py`                                     |
| §4.2 Why Shadow Mode matters                                           | `shadow_observer.py`                                       |
| §4.3 Shadow mode decision flow                                         | `validation/policy_matrix.py` + `shadow_observer.py`       |
| §4.4 Shadow mode counterfactual record                                 | `validation/shadow.build_shadow_payload`                   |
| §5.4 Blast radius scenarios                                            | `blast_analysis.py` (§5.4 regression tests)                |
| §5.5 K8s API auth (in-cluster SA)                                      | `executor_kubernetes.py` + `infrastructure/helm/.../rbac/` |
| §5.6 Shadow mode analysis                                              | `shadow_observer.py`                                       |
| §8.2 System-level evaluation metrics                                   | `execution_log` + shadow metrics                           |

### Proposal

| Proposal section                         | Implementation                                            |
| ---------------------------------------- | --------------------------------------------------------- |
| §3.4 Decision and Strategy Engine        | This entire package                                       |
| §4.3 Validation + escalation + execution | `validation/` + `escalation/` + `executor*.py`            |
| §4.5 LLM copilot (downstream consumer)   | Decision logs are consumed by Component 4 (not yet built) |
| §5.5 K8s auth (ServiceAccount, RBAC)     | `executor_kubernetes.py` + Helm RBAC manifests            |
| §7 Governed autonomy                     | Full 4-outcome matrix + guardrails + escalation           |
| §8.2 Unnecessary Action Rate             | `shadow_observer.py` + `shadow_metrics()`                 |
| §8.2 MTTR / availability                 | `execution_log` (once real executor is live)              |
| §8.2 Decision scalability                | `decision_log` (once sharding is added — future work)     |

### What this package does **not** implement

| Concern                           | Where it lives                               |
| --------------------------------- | -------------------------------------------- |
| Telemetry ingestion               | `app/ingestion/`                             |
| Rule language / registry          | `app/rules/`                                 |
| Graph management                  | `app/core/` + `app/topology/`                |
| Persistence                       | `app/persistence/`                           |
| HTTP surface                      | `app/api/routes/`                            |
| LLM post-mortem generation        | Component 4 (Member 4 — out of this package) |
| Adaptive learning decision engine | Component 3 (Member 3 — out of this package) |

---

## 10. The four outcomes in one glance

For quick reference when reading a `decision_log` row:

| `policy_outcome`  | Means          | Trigger                                                              | Side effects                                                                                    |
| ----------------- | -------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `AUTO_EXECUTE`    | Safe to run    | confidence ≥ 0.85 AND risk = LOW AND no conflict AND guardrails pass | Executor runs; `execution_log` written; `action_history` written; cooldown + idempotency marked |
| `SHADOW_MODE`     | Observe only   | 0.60 ≤ confidence < 0.85 OR (HIGH confidence + MEDIUM risk)          | `shadow_records` written; observer fills `VERDICT` later                                        |
| `HUMAN_LOOP`      | Needs approval | risk = HIGH OR repeat-failure ≥ 2                                    | `escalations` row created; 3-attempt email schedule starts                                      |
| `BLOCK`           | Do nothing     | confidence < 0.60 OR any conflict OR guardrail failure               | Logged only                                                                                     |
| `NO_RULE_MATCHED` | Nothing to do  | No rule fired                                                        | Logged only (terminal, never retried)                                                           |

---

## Summary

| Question                                             | Answer                                                                                                    |
| ---------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| What is the `app/decision/` package responsible for? | Turning an anomaly into a routed, auditable recovery decision                                             |
| Does it execute anything?                            | No — the executor does                                                                                    |
| Does it validate anything?                           | Yes, via `validation/` (separate README)                                                                  |
| Does it enforce safety limits?                       | Yes, via `guardrails/` (separate README)                                                                  |
| Does it escalate?                                    | Yes, via `escalation/` (separate README)                                                                  |
| Does it observe counterfactuals?                     | Yes — `shadow_observer.py`                                                                                |
| Does it survive restart?                             | Yes — every job is idempotent; state is in Postgres                                                       |
| Where is the outcome recorded?                       | `decision_log` (one row per decision) + `execution_log` / `shadow_records` / `escalations` (side effects) |
| Which layer comes first?                             | Validation (safe?) → Guardrails (recent?) → Executor (do it)                                              |
| Which layers can veto?                               | Validation (any outcome), Guardrails (downgrades to BLOCK)                                                |
| What happens if a layer is down?                     | Fail-open on infra; fail-closed on safety                                                                 |
| Is the pipeline tunable at runtime?                  | Yes — most intervals and thresholds are runtime-editable                                                  |
| Are the design-doc constants tunable?                | No — they are deliberate, require code change                                                             |

```

---

## Documentation map

| If you want to understand… | Read |
|---|---|
| **How unsafe actions are prevented** | [`validation/README.md`](validation/README.md) |
| **Why the same action can't fire twice** | [`guardrails/README.md`](guardrails/README.md) |
| **How a human is notified and given a decision** | [`escalation/README.md`](escalation/README.md) |
| **How the decision pipeline is composed end-to-end** | This file |
| **How the rule engine produces candidates** | `app/rules/readme.md` + `app/rules/models.py` |
| **What the API endpoints are** | `/docs` (Swagger) or `app/api/routes/` |
| **What the DB schema is** | `app/persistence/schemas.py` |
| **How the app boots** | `app/main.py` (the `lifespan` function) |
```
