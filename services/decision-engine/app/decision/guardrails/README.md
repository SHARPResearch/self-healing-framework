# Safety Guardrails — Runtime Protection Layer

The **Safety Guardrails** are the last automated checkpoint before a
recovery action reaches the executor. They answer one question:

> **"Has this action already been tried too recently, too often, or with
> the same intent?"**

They do **not** re-evaluate confidence or risk — that's the Validation
Layer's job. They enforce **temporal and rate limits** that the policy
matrix cannot express on its own.

The guardrails are the concrete implementation of **§5.7 Safety
Guardrails** of the Component 2 report.

---

## 1. What this subsystem does

For every `RecoveryAction` that survived the Validation Layer with
outcome `AUTO_EXECUTE`, the guardrails run three independent checks:

1. **Cooldown** — has this service had _any_ action in the last
   `cooldown_seconds`? (`cooldown.py`)
2. **Action counter** — has this service hit its `max_per_hour` cap in
   the last 60 minutes? (`action_counter.py`)
3. **Idempotency** — has this exact `(service, action, intent)` already
   been executed? (`idempotency.py`)

If **any** check blocks, the decision is downgraded from `AUTO_EXECUTE`
to `BLOCK` with the guardrail's reason. If **all** pass, the guardrails
`mark()` the side effects (start cooldown, record idempotency key) so the
next decision sees them.

The layer is **stateless logic over stateful storage**. Redis (or an
in-memory fallback) is a cache; Postgres is the source of truth. All
three checks **fail open** on infrastructure errors — a working
guardrail is a nice-to-have, a permanently blocked pipeline is not.

---

## 2. Where it lives

```

app/decision/guardrails/
├── **init**.py Re-exports check() and mark()
├── store.py RedisStore + InMemoryStore, unified via KeyValueStore protocol
├── verdict.py GuardrailVerdict, GuardrailCheck, allow(), block()
├── cooldown.py Per-service cooldown check + mark
├── action_counter.py Per-service per-hour cap (from action_history)
├── idempotency.py Intent-level dedup (from idempotency_keys)
└── guardrails.py Orchestrator — check() and mark() entry points

```

---

## 3. Key data structures

### `GuardrailCheck`

One guardrail's verdict:

```python
@dataclass
class GuardrailCheck:
    name: str                       # "cooldown" | "action_counter" | "idempotency"
    blocked: bool                   # True = this guardrail vetoes
    reason: str                     # human-readable one-liner
    detail: dict[str, Any]          # machine-readable trace
```

### `GuardrailVerdict`

The aggregate return value of `check()`:

```python
@dataclass
class GuardrailVerdict:
    allowed: bool                    # True iff every check passed
    blocker: str | None              # Name of the first blocking guardrail (None = allowed)
    reason: str                      # One-liner from the blocker (or "all guardrails passed")
    checks: list[GuardrailCheck]     # All checks that ran, in order
    decided_at: datetime             # UTC timestamp
```

`GuardrailVerdict.to_dict()` is JSON-safe; callers can log it verbatim
or store it in `decision_log.context.guardrails`.

### Backend protocol

```python
@runtime_checkable
class KeyValueStore(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl_sec: int | None = None) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def incr(self, key: str, ttl_sec: int | None = None) -> int: ...
    async def exists(self, key: str) -> bool: ...
```

Two implementations:

- `RedisStore` — production; uses `redis.asyncio`.
- `InMemoryStore` — dev/test; single-process; loses state on restart.

Selection is automatic via `get_store()`:

- If `settings.REDIS_URL` is set and the client connects, use Redis.
- Otherwise, use `InMemoryStore` and log at `INFO`.

`set_store(...)` and `reset_store()` exist for tests.

---

## 4. How it fits in the pipeline

```
job.py :: poll_and_decide()
  │
  ├─ validate(recovery_action, ctx)                    → ValidationResult
  │
  └─ if result.outcome == PolicyOutcome.AUTO_EXECUTE:
       │
       └─ guardrails.check(recovery_action, anomaly_id)   ◄── THIS LAYER
            │
            ├─ 1. cooldown.check()                        ← cooldown.py
            ├─ 2. action_counter.check()                  ← action_counter.py
            ├─ 3. idempotency.check()                     ← idempotency.py
            │
            └─ if verdict.allowed:
                 guardrails.mark(...)                    ← side effects
                 executor.execute(decision)              ← next layer
               else:
                 decision.policy_outcome = BLOCK
                 decision.policy_reason = verdict.reason
```

The layer has **no knowledge of the executor**. It is a pure veto gate.
Any extension to execution (e.g. a new executor, a new backend) does
not touch guardrails; any extension to guardrails (e.g. a new check) does
not touch execution.

---

## 5. Public API

### Orchestrator

```python
from app.decision.guardrails import check, mark

verdict: GuardrailVerdict = await check(recovery_action, anomaly_id)
if verdict.allowed:
    await mark(recovery_action, anomaly_id, decision_id)
    # → executor.execute(...)
else:
    # decision.policy_outcome = BLOCK with verdict.reason
```

### Individual checks (testable in isolation)

| Function                                         | Module              | Returns          |
| ------------------------------------------------ | ------------------- | ---------------- |
| `check(service_id, guardrails)`                  | `cooldown.py`       | `GuardrailCheck` |
| `mark(service_id, decision_id, guardrails)`      | `cooldown.py`       | `None`           |
| `check(service_id, guardrails)`                  | `action_counter.py` | `GuardrailCheck` |
| `check(recovery_action, anomaly_id)`             | `idempotency.py`    | `GuardrailCheck` |
| `mark(recovery_action, anomaly_id, decision_id)` | `idempotency.py`    | `None`           |

### Store management (test helpers)

| Function           | Module     | Purpose                                 |
| ------------------ | ---------- | --------------------------------------- |
| `get_store()`      | `store.py` | Return the process-wide singleton store |
| `set_store(store)` | `store.py` | Override (tests)                        |
| `reset_store()`    | `store.py` | Drop the singleton (tests)              |

---

## 6. Configuration

### A. Env vars

| Env var     | Type  | Default | Purpose                                           |
| ----------- | ----- | ------- | ------------------------------------------------- |
| `REDIS_URL` | `str` | `""`    | Redis connection URL. Empty → in-memory fallback. |

**Format examples:**

```dotenv
# Local Redis
REDIS_URL=redis://localhost:6379/0

# Redis Cloud (TLS)
REDIS_URL=rediss://default:PASSWORD@HOST:PORT
```

### B. Per-rule guardrails (from `RuleGuardrail`)

These come from the rule's own `guardrails` block and are evaluated per
action, not globally.

| Field              | Range  | Default | Meaning                                                   |
| ------------------ | ------ | ------- | --------------------------------------------------------- |
| `cooldown_seconds` | `≥0`   | `300`   | Minimum time between actions on the same service          |
| `max_per_hour`     | `≥1`   | `3`     | Max actions on the same service in a rolling hour         |
| `idempotency_key`  | `str?` | `None`  | Template; defaults to `idem:{service}:{action}:{anomaly}` |

`cooldown_seconds = 0` is valid — it disables the cooldown check for
that rule. This is intentional (some emergencies require rapid retries).
The `_resolve_window_sec` helper uses an **explicit `None` check**, not a
truthy check, so `0` is honoured. (This was a real bug fixed in Phase 3:
the original `or DEFAULT` fallback silently overrode `0` with `300`.)

### C. Constants

| Constant               | Module              | Default | Meaning                               |
| ---------------------- | ------------------- | ------- | ------------------------------------- |
| `DEFAULT_COOLDOWN_SEC` | `cooldown.py`       | `300`   | Used if rule omits `cooldown_seconds` |
| `DEFAULT_MAX_PER_HOUR` | `action_counter.py` | `3`     | Used if rule omits `max_per_hour`     |
| `DEFAULT_TTL_SEC`      | `idempotency.py`    | `86400` | Idempotency key TTL (24h)             |

### D. Storage layout

| Key pattern                   | Backend  | TTL                | Source of truth table  |
| ----------------------------- | -------- | ------------------ | ---------------------- |
| `cooldown:{service_id}`       | Redis/KV | `cooldown_seconds` | `cooldowns` (Postgres) |
| `idem:{service}:{action}:...` | Redis/KV | `86400s`           | `idempotency_keys`     |

**Action counter has no cache.** It's a `SELECT COUNT(*)` on
`action_history` per check — cheap because the table is indexed on
`(service_id, action, occurred_at DESC)`.

---

## 7. Failure modes

The guardrails are designed to **fail open** on infrastructure errors and
**fail closed** on real guardrail violations.

| Condition                             | Behaviour                                                                       |
| ------------------------------------- | ------------------------------------------------------------------------------- |
| Redis unreachable                     | Fall back to in-memory store; log `INFO` on startup                             |
| Postgres unreachable (cooldown check) | Log `ERROR`, return `blocked=False` (fail-open)                                 |
| Postgres unreachable (counter check)  | Log `ERROR`, return `blocked=False` (fail-open)                                 |
| Postgres unreachable (idempotency)    | Log `ERROR`, return `blocked=False` (fail-open)                                 |
| Redis write fails during `mark()`     | Log `ERROR`; Postgres write is still attempted                                  |
| Both stores fail during `mark()`      | Log `ERROR`; action proceeds. Cooldown may not be recorded — a known trade-off. |
| Cooldown active                       | `blocked=True`; decision downgraded to `BLOCK`                                  |
| Counter at/above cap                  | `blocked=True`; decision downgraded to `BLOCK`                                  |
| Idempotency key already exists        | `blocked=True`; decision downgraded to `BLOCK`                                  |

### Why fail-open?

Three reasons:

1. **The alternative is worse.** Blocking every decision because Redis
   is down would turn a cache outage into a recovery outage.
2. **Confidence + risk already ran.** The Validation Layer already
   filtered out anything unsafe. A duplicate action is annoying; a
   _never_-executed action is exactly what the framework exists to
   prevent.
3. **Idempotency is preserved by the executor's own idempotency keys
   where they exist** (see `executor_kubernetes.py` — every K8s action
   is naturally idempotent: `patch` twice = same state).

### Known limitations

1. **Cooldown and counter are per-service, not per-(service, action).**
   Two _different_ actions on the same service will still hit the
   cooldown. This is deliberate: two decisions on the same service in
   quick succession is a burst, regardless of action type. If a future
   use case needs per-action cooldowns, that's a schema change to
   `cooldowns`.

2. **Idempotency default key uses `anomaly_id`.**
   The default `idem:{service}:{action}:{anomaly_id}` means the _same
   anomaly_ cannot trigger the _same action_ twice. But _two different
   anomalies_ on the same service will produce different keys — which
   is correct. It does mean, however, that "anomaly_id never repeats"
   is a load-bearing assumption. Component 1's anomaly IDs must remain
   deterministic per incident.

3. **No cross-worker coordination without Redis.**
   If you run multiple uvicorn workers _without_ `REDIS_URL`, each
   worker has its own `InMemoryStore`. Cooldowns and counters will be
   inconsistent across workers. **Production must set `REDIS_URL`.**
   In dev (single worker) the in-memory fallback is fine.

4. **`mark()` is not transactional across stores.**
   If Redis succeeds but Postgres fails, the cache holds a cooldown
   that the DB doesn't know about. On restart, the cache is lost. This
   is acceptable because Postgres is the source of truth and the cache
   is regenerated on demand. But it means cooldown may be _forgotten_
   on a full restart even if it was recently set.

---

## 8. Tests

All tests run without Redis and without Postgres. `InMemoryStore` is
used by default, and the Postgres store is monkeypatched with a fake.
Expected green count: **20**.

| File                                    | What it proves                                              |
| --------------------------------------- | ----------------------------------------------------------- |
| `tests/test_guardrails_store.py`        | `InMemoryStore` semantics (TTL, incr, exists)               |
| `tests/test_guardrails_cooldown.py`     | Cooldown logic, `cooldown_seconds=0` disables (the bug fix) |
| `tests/test_guardrails_counter.py`      | Cap enforcement, DB-error fail-open                         |
| `tests/test_guardrails_idempotency.py`  | Default + templated keys, idempotency across calls          |
| `tests/test_guardrails_orchestrator.py` | All-pass, cooldown-first, counter-first, idempotency-first  |

Run all:

```bash
cd services/decision-engine
uv run pytest tests/test_guardrails_*.py -v
```

### Live verification

After an AUTO_EXECUTE decision has fired (see
`validation/README.md` §8 for the leaf-service scenario):

```bash
# 1. Confirm the execution was recorded
curl http://localhost:8000/api/executions
# → {"count": 1, "executions": [{"status": "NOT_IMPLEMENTED", ...}]}

# 2. Trigger the SAME scenario again immediately
curl -X POST http://localhost:8000/api/mock/scenario/metrics_collector_slow
sleep 25
curl "http://localhost:8000/api/decisions/recent?limit=1"
# → The new decision should have:
#     "policy": {"outcome": "BLOCK", "reason": "guardrail blocked: service 'metrics-collector' acted on within the last 300s"}
```

That's the guardrails doing their job: **the framework refuses to restart
the same pod twice in five minutes**, even if the anomaly detector fires
again. This is a concrete, demonstrable safety property.

### Quick manual verification (no auto-execute)

```bash
# Directly check the cooldown state
curl http://localhost:8000/api/debug/guardrails
# (endpoint TBD — add a debug route if you want to expose cooldown/counter state)
```

Currently the debug surface is limited to `/api/executions` and the log
trail. Adding a `/api/debug/guardrails` endpoint that dumps the current
cooldown map and idempotency keys is a small future enhancement (~30
lines); it would help during live demos.

---

## 9. Research mapping

The guardrails implement the safety rails referenced in several sections
of the Component 2 report and the research proposal.

### Component 2 report

| Report section                            | Implemented in                                                |
| ----------------------------------------- | ------------------------------------------------------------- |
| §5.7 Safety guardrails                    | This package                                                  |
| §5.7.1 Cooldowns and per-service caps     | `cooldown.py`, `action_counter.py`                            |
| §5.7.2 Idempotency keys                   | `idempotency.py`                                              |
| §3.5.3 Human-in-the-loop (gated by guard) | `escalation/` (next layer) — guardrails run first             |
| §7 Research novelty: governed autonomy    | The three-check veto is a concrete, auditable governance gate |

### Proposal

| Proposal section                                         | Implementation                                                                                                       |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| §3.4 Safety guardrails (cooldown, counters, idempotency) | This package                                                                                                         |
| §7 (Governed autonomy)                                   | Every auto-execution must pass all three guardrails, and every block is logged                                       |
| §8.2 (Unnecessary Action Rate)                           | A blocked duplicate action is _not_ an unnecessary action — the metric tracks guardrail-blocked decisions separately |

### Design rationale worth stating in the report

The guardrails exist because **the Validation Layer alone cannot prevent
duplicate actions**. Confidence + risk + conflict detection answer "is
this action safe?" — they do not answer "have we already done this?".
The guardrails layer supplies that missing temporal dimension.

This is a **specific, testable, non-obvious contribution**. Many "AI
self-healing" frameworks stop at "detect → predict → act"; the
guardrails are what turn a suggestion engine into a _governed recovery
system_.

### What this layer does **not** do (and where that lives)

| Concern                                       | Where it actually lives                    |
| --------------------------------------------- | ------------------------------------------ |
| Confidence + risk + conflict reasoning        | `app/decision/validation/`                 |
| Policy matrix (Auto / Shadow / Human / Block) | `app/decision/validation/policy_matrix.py` |
| Escalation queue + email delivery             | `app/decision/escalation/`                 |
| Kubernetes execution                          | `app/decision/executor_kubernetes.py`      |
| Decision persistence                          | `app/decision/log.py`                      |
| Counterfactual outcome observation            | `app/decision/shadow_observer.py`          |

---

## Summary

| Question                                             | Answer                                                            |
| ---------------------------------------------------- | ----------------------------------------------------------------- |
| What do the guardrails decide?                       | Allow / Block (binary)                                            |
| What triggers a block?                               | Cooldown, counter cap, or repeated idempotent intent              |
| Do they re-check confidence or risk?                 | No — that's the Validation Layer                                  |
| Do they execute actions?                             | No — that's the executor                                          |
| Do they persist anything?                            | Side effects to `cooldowns`, `idempotency_keys`, `action_history` |
| Do they fail open or closed on infra errors?         | Open (never block on a DB/cache outage)                           |
| Do they fail open or closed on violations?           | Closed (block, downgrade to `BLOCK`, log reason)                  |
| Is Redis required?                                   | No — in-memory fallback for dev/test                              |
| Is Redis required for production?                    | Yes — otherwise multi-worker cooldowns drift                      |
| Does a rule with `cooldown_seconds: 0` work?         | Yes — the bug is fixed; `0` correctly disables                    |
| Can the same action on two different anomalies fire? | Yes (different idempotency keys) — by design                      |
| Can two different actions on the same service fire?  | No (cooldown is per-service) — by design                          |

```

```
