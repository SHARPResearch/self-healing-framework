# Validation Layer — Trust & Safety Gate

The **Validation Layer** sits between _action selection_ and _execution_.
It answers one question:

> **"Is this recovery action safe to execute right now?"**

It does not execute. It does not persist decisions. It does not send
emails. It **reasons** — and returns a `ValidationResult` that the
decision pipeline (`app/decision/job.py`) consumes.

The layer is the concrete implementation of **§3.5 (Trust & Safety /
Decision Validation)** of the Component 2 report, and it drives the
**§3.3 Decision Policy Matrix** verbatim.

---

## 1. What this subsystem does

For every `RecoveryAction` selected by the rule engine, the layer:

1. **Blends confidence** — combines detection confidence and rule
   confidence with a graph-certainty multiplier (`confidence.py`).
2. **Classifies risk** — combines the rule's base risk and the
   blast-radius analysis into a final `LOW` / `MEDIUM` / `HIGH` band
   (`risk_classifier.py`).
3. **Detects conflicts** — three independent checks: an in-flight action
   on the same service, an in-flight action on a _neighbour_, or a
   repeated failed action on this service (`conflict_detector.py`).
4. **Applies the policy matrix** — maps `(confidence, risk, conflict)`
   to one of four outcomes: `AUTO_EXECUTE`, `SHADOW_MODE`, `HUMAN_LOOP`,
   `BLOCK` (`policy_matrix.py`).
5. **Builds optional payloads** — the shadow-mode counterfactual record
   (`shadow.py`) and the escalation envelope — when the outcome requires
   them.
6. **Returns a `ValidationResult`** — one object that fully explains the
   verdict in human-readable and machine-readable form
   (`validator.py`).

The whole layer is **pure** and **fail-open**. If Postgres is unreachable,
conflict detection degrades to "no conflict"; confidence and risk
classifications still run. The pipeline never stalls on a validation
error.

---

## 2. Where it lives

```

app/decision/validation/
├── **init**.py Re-exports the public API (validate, ValidationResult)
├── result.py ValidationResult, ConfidenceBreakdown, ConflictReport
├── confidence.py Blended confidence + graph certainty → band (LOW/MED/HIGH)
├── risk_classifier.py Combines base_risk + blast.recommended_risk → final RiskLevel
├── conflict_detector.py In-flight / dependency / repeat-failure checks
├── policy_matrix.py §3.3 matrix — decides AUTO_EXECUTE / SHADOW / HUMAN_LOOP / BLOCK
├── shadow.py Builds the §4.4 counterfactual record
└── validator.py Orchestrator — the one function callers use

```

---

## 3. Key data structures

### `ConfidenceBreakdown`

Every number that fed the final confidence, for audit:

| Field             | Range  | Meaning                                                    |
| ----------------- | ------ | ---------------------------------------------------------- |
| `detection`       | [0, 1] | Confidence from Component 1's anomaly detector             |
| `rule_base`       | [0, 1] | The rule's declared `base_confidence`                      |
| `blended`         | [0, 1] | `0.6 × detection + 0.4 × rule_base` (from `RuleCandidate`) |
| `graph_certainty` | [0, 1] | 1.0 when graph data is complete and fresh                  |
| `effective`       | [0, 1] | `blended × graph_certainty`                                |
| `band`            | string | `LOW` / `MEDIUM` / `HIGH` (from `effective`)               |

### `ConflictReport`

| Field          | Meaning                                                   |
| -------------- | --------------------------------------------------------- |
| `has_conflict` | `True` if any of the three checks fired                   |
| `kind`         | `IN_FLIGHT` / `DEPENDENCY` / `REPEAT_FAILURE` (or `None`) |
| `details`      | List of human-readable reasons (one per conflicting row)  |

### `ValidationResult`

The single object the pipeline consumes:

```python
@dataclass
class ValidationResult:
    outcome: PolicyOutcome                       # AUTO_EXECUTE | SHADOW_MODE | HUMAN_LOOP | BLOCK
    reason: str                                  # human-readable one-liner
    confidence: ConfidenceBreakdown              # full confidence trace
    risk: RiskLevel                              # final risk band
    conflict: ConflictReport                     # conflict trace
    shadow_payload: dict | None = None           # set only for SHADOW_MODE
    escalation_payload: dict | None = None       # set only for HUMAN_LOOP
    validated_at: datetime = ...                 # UTC timestamp
```

`ValidationResult.to_dict()` is JSON-safe and is stored verbatim in
`decision_log.context` so the entire reasoning chain is auditable.

---

## 4. How it fits in the pipeline

```
job.py :: poll_and_decide()
  │
  ├─ ContextBuilder.build(anomaly)           ← rules/context.py
  ├─ classify(ctx)                           ← rules/classifier.py
  ├─ rule_engine.evaluate(ctx)               ← rules/engine.py
  ├─ select_recovery_action(candidates)      ← decision/action_selector.py
  │
  └─ validate(recovery_action, ctx)          ◄── THIS LAYER
       │
       ├─ 1. compute_confidence()            ← confidence.py
       ├─ 2. count_recent_failures()          ← postgres_store (via validator)
       ├─ 3. classify_risk()                 ← risk_classifier.py
       ├─ 4. detect_conflicts()              ← conflict_detector.py
       ├─ 5. decide_outcome()                ← policy_matrix.py
       ├─ 6. build_shadow_payload()          ← shadow.py (if SHADOW_MODE)
       └─ 7. build_escalation_payload()      ← inline (if HUMAN_LOOP)
       ↓
     ValidationResult
       ↓
     job.py persists decision + triggers:
       AUTO_EXECUTE → guardrails.check() → executor.execute()
       SHADOW_MODE  → postgres_store.save_shadow_record()
       HUMAN_LOOP   → escalation.escalate()
       BLOCK        → log only
```

The `validation` package **never imports** `guardrails`, `escalation`, or
`executor`. Dependencies point **one way**: `job.py → validation → {rules,
persistence, models}`. This makes each layer independently testable.

---

## 5. Public API

### `validate(recovery_action, ctx) -> ValidationResult`

The single entry point. Async because it queries Postgres for the
repeat-failure count and conflict checks.

```python
from app.decision.validation import validate

result = await validate(recovery_action, ctx)
if result.outcome == PolicyOutcome.AUTO_EXECUTE:
    ...
elif result.outcome == PolicyOutcome.SHADOW_MODE:
    await postgres_store.save_shadow_record(result.shadow_payload)
elif result.outcome == PolicyOutcome.HUMAN_LOOP:
    await escalate(
        decision_id=decision.decision_id,
        anomaly_id=str(ctx.anomaly.get("id")),
        service_id=recovery_action.service_id,
    )
```

### Individual components (testable in isolation)

| Function                                                               | Module                 | Returns                               |
| ---------------------------------------------------------------------- | ---------------------- | ------------------------------------- |
| `compute_confidence(blended, detection, rule_base, ctx)`               | `confidence.py`        | `ConfidenceBreakdown`                 |
| `classify_risk(base_risk, blast, repeat_failure_count=0)`              | `risk_classifier.py`   | `tuple[RiskLevel, str]`               |
| `detect_conflicts(service_id, action, ctx)`                            | `conflict_detector.py` | `ConflictReport`                      |
| `decide_outcome(confidence, risk, conflict)`                           | `policy_matrix.py`     | `tuple[PolicyOutcome, str]`           |
| `build_shadow_payload(...)`                                            | `shadow.py`            | `dict` (payload for `shadow_records`) |
| `observe_shadow_outcome(row, resolved_naturally, resolution_time_sec)` | `shadow.py`            | `dict` (completed record)             |

---

## 6. Configuration

The layer reads **three** sources of tunables:

### A. Constants in `confidence.py` (rarely changed)

| Constant      | Default | Meaning                                              |
| ------------- | ------- | ---------------------------------------------------- |
| `CONF_HIGH`   | `0.85`  | Effective confidence threshold for the `HIGH` band   |
| `CONF_MEDIUM` | `0.60`  | Effective confidence threshold for the `MEDIUM` band |

### B. Constants in `risk_classifier.py`

| Constant                   | Default | Meaning                                                |
| -------------------------- | ------- | ------------------------------------------------------ |
| `REPEAT_FAILURE_THRESHOLD` | `2`     | Number of FAILED outcomes that forces `RiskLevel.HIGH` |

### C. Constants in `conflict_detector.py`

| Constant                    | Default | Meaning                               |
| --------------------------- | ------- | ------------------------------------- |
| `REPEAT_FAILURE_THRESHOLD`  | `2`     | Same as above — first conflict wins   |
| `REPEAT_FAILURE_WINDOW_MIN` | `30`    | Lookback window for counting failures |

**No env vars.** Changing any of these requires editing the constants and
restarting. Rationale: these are safety thresholds, not operator knobs —
if they need tuning mid-incident, the design is wrong.

### D. Graph certainty heuristic (in `confidence.py`)

| Penalty                      | Multiplier | Applied when                      |
| ---------------------------- | ---------- | --------------------------------- |
| Service not in graph         | `0.5`      | `sid not in GraphStore().graph()` |
| Neighbour-anomaly burst > 10 | `0.9`      | `ctx.neighbor_anomaly_count > 10` |

The neighbourless penalty (`0.7`) from earlier versions has been
**removed** — leaf services legitimately have no neighbours, and
penalising them for it caused false `BLOCK` outcomes. See §7.

---

## 7. Failure modes

The layer is designed to **fail-open** on infrastructure errors, and
**fail-closed** on safety conditions. That distinction matters:

| Condition                            | Behaviour                                                                                                  |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| Postgres unavailable (conflicts)     | Log, treat as "no conflict", proceed → decision is still safe because risk + confidence checks already ran |
| Postgres unavailable (repeat)        | Log, treat as `0` failures → no forced escalation                                                          |
| GraphStore unavailable               | `graph_certainty = 0.5`, confidence drops but decision runs                                                |
| Unknown service (not in graph)       | `graph_certainty = 0.5` → forces `SHADOW_MODE` or `BLOCK`                                                  |
| Effective confidence < `CONF_MEDIUM` | Outcome = `BLOCK`                                                                                          |
| Any conflict detected                | Outcome = `BLOCK` (highest-precedence veto)                                                                |
| Risk = HIGH                          | Outcome = `HUMAN_LOOP`                                                                                     |

### Why fail-open on infra errors?

A permanently blocked pipeline is worse than a slightly sloppy decision
during a brief DB outage. The design chooses:

- **fail-closed on safety** (low confidence → block; high risk → escalate)
- **fail-open on infrastructure** (DB down → skip that check)

### Known limitations

1. **`_graph_certainty` cannot distinguish "leaf" from "missing."**
   A leaf service (size 0 blast radius) and a service absent from the
   graph both have `upstream=[]` and `downstream=[]`. The current fix
   returns `0.5` when `sid not in g` (hard cap) and no penalty when
   `sid in g` but has no neighbours. This is correct as of the leaf-service
   patch, but a service that _should_ have neighbours and doesn't still
   slips through undetected.

2. **Shadow verdict thresholds are heuristic.** The
   `ACTION_WOULD_HAVE_HELPED` vs `ACTION_WOULD_HAVE_BEEN_UNNECESSARY`
   decision uses `resolution_time_sec ≤ expected_sec × 1.5`. Real
   anomalies resolve in wildly variable timeframes, so this is a
   _relative_ signal, not an absolute one. Document as a limitation in
   §8.2 of the report — the counterfactual is directional, not precise.

3. **No second-order confidence.** Rule confidence and detection
   confidence are treated as independent signals. If a rule fires on
   a single noisy metric, the detection confidence absorbs all the
   uncertainty. This is correct for now but would benefit from a
   Bayesian combination later.

---

## 8. Tests

All tests run without a live Postgres — the store is monkeypatched with
an in-memory fake. Expected green count: **20**.

| File                                    | What it proves                                                 |
| --------------------------------------- | -------------------------------------------------------------- |
| `tests/test_validation_confidence.py`   | Graph-certainty penalties, band thresholds                     |
| `tests/test_validation_risk.py`         | Risk-level `max()` semantics, repeat-failure bump              |
| `tests/test_validation_policy.py`       | Every row of the §3.3 policy matrix                            |
| `tests/test_validation_shadow.py`       | The §4.4 JSON shape, verdict logic                             |
| `tests/test_validation_orchestrator.py` | Full flow: AUTO / SHADOW / HUMAN / BLOCK + conflict precedence |

Run all:

```bash
cd services/decision-engine
uv run pytest tests/test_validation_*.py -v
```

### Live verification (leaf-service AUTO_EXECUTE)

After the leaf-service scenario is added to the mock catalog:

```bash
curl -X POST http://localhost:8000/api/mock/scenario/all_healthy
sleep 40
curl -X POST http://localhost:8000/api/mock/scenario/metrics_collector_slow
sleep 25
curl "http://localhost:8000/api/decisions/recent?limit=1"
```

Expected in the decision:

```json
"rule_id": "restart_isolated_leaf_service",
"base_risk": "LOW",
"policy": {"outcome": "AUTO_EXECUTE", "reason": "auto: confidence ... ≥ 0.85 and risk=LOW"}
```

And in `execution_log`:

```bash
curl http://localhost:8000/api/executions
# → {"count": 1, "executions": [{"status": "NOT_IMPLEMENTED", ...}]}
```

`NOT_IMPLEMENTED` is the correct status when `KUBERNETES_DRY_RUN=true`
(the default). Flip the env var to `0` with a live cluster to see real
execution.

---

## 9. Research mapping

This layer is the implementation of several sections of the
Component 2 report and the top-level research proposal.

### Component 2 report

| Report section                           | Implemented in                                                     |
| ---------------------------------------- | ------------------------------------------------------------------ |
| §3.3 Decision Policy Matrix              | `policy_matrix.py:decide_outcome()` — the exact 4-outcome mapping  |
| §3.4 Full Decision Flow                  | `validator.py:validate()` — 7-step orchestration                   |
| §3.5.1 BLOCK (conflict / low confidence) | `conflict_detector.py` + `policy_matrix.py` (rows 1 & 3)           |
| §3.5.2 SHADOW MODE                       | `shadow.py` + `validator.py` (payload building)                    |
| §3.5.3 HUMAN-IN-THE-LOOP (escalation)    | `policy_matrix.py` (row 2) → `escalation/` (Phase 4)               |
| §3.5.4 AUTO-EXECUTE                      | `policy_matrix.py` (row 4) → `guardrails/` → `executor.py`         |
| §4 Shadow Mode — counterfactual record   | `shadow.py:build_shadow_payload()` — exact JSON shape in §4.4      |
| §4.2 Why Shadow Mode Matters             | `validation/shadow_observer.py` — produces the counterfactual data |

### Proposal

| Proposal section                                     | Implementation                                                   |
| ---------------------------------------------------- | ---------------------------------------------------------------- |
| §3.4 (Decision layer — hybrid)                       | This layer is the "validation / safety gate" half of that hybrid |
| §4.3 (Validation Layer between action and execution) | This entire package                                              |
| §7 (Research novelty: governed autonomy)             | `policy_matrix.py` — confidence × risk gate                      |
| §8.2 (Unnecessary Action Rate via shadow mode)       | `shadow.py` + `shadow_observer.py` produce the raw data          |

### What this layer does **not** do (and where that lives)

| Concern                                  | Where it actually lives               |
| ---------------------------------------- | ------------------------------------- |
| Cooldowns, rate limits, idempotency keys | `app/decision/guardrails/`            |
| Human escalation queue + email delivery  | `app/decision/escalation/`            |
| Kubernetes execution                     | `app/decision/executor_kubernetes.py` |
| Decision persistence                     | `app/decision/log.py`                 |
| Counterfactual outcome observation       | `app/decision/shadow_observer.py`     |

The clean split is why each subsystem is independently testable and why
the research can claim four distinct, verifiable contributions rather
than "one big blob".

---

## Summary

| Question                                        | Answer                                           |
| ----------------------------------------------- | ------------------------------------------------ |
| What does the Validation Layer decide?          | Auto-execute / Shadow / Human / Block            |
| Is it async?                                    | Yes — for conflict + repeat-failure queries      |
| Does it persist anything?                       | No — returns `ValidationResult`, caller persists |
| Does it execute anything?                       | No — that's `executor.py`                        |
| Does it send emails?                            | No — that's `escalation/worker.py`               |
| Does it fail-close on safety conditions?        | Yes (low confidence, conflict, high risk)        |
| Does it fail-open on infrastructure errors?     | Yes (DB down → skip that check)                  |
| Is it tested without a live DB?                 | Yes — fake store monkeypatched                   |
| Does it produce the §4.4 counterfactual record? | Yes — via `shadow.build_shadow_payload()`        |
| Does it match the §3.3 policy matrix?           | Yes — `policy_matrix.py` is that matrix          |

```

---
```
