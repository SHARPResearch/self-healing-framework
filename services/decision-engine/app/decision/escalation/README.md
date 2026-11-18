# Escalation — Human-in-the-Loop Delivery

The **Escalation** subsystem is how the framework asks a human for
permission. It answers one question:

> **"When the Validation Layer says HUMAN_LOOP, how do we actually
> reach a person, and what happens if they don't respond?"**

The answer is a **three-attempt Gmail escalation flow** over a persistent
queue, driven by a background worker. The subsystem tracks every attempt,
schedules the next one, and terminates cleanly when the incident is
resolved — by the operator, or by exhaustion of attempts.

The escalation subsystem is the concrete implementation of **§3.5.3
Human-in-the-Loop** and **§3.6 Human Escalation State Machine** of the
Component 2 report.

---

## 1. What this subsystem does

When the Validation Layer returns `PolicyOutcome.HUMAN_LOOP` for a
decision, the pipeline calls `escalate(...)` to create a persistent
escalation row. A background worker (`worker.py`) polls for due
escalations and fires attempts on this schedule:

| Attempt | Fires at   | Email template    | Next attempt scheduled |
| ------- | ---------- | ----------------- | ---------------------- |
| 1       | T + 0      | **Initial**       | T + 5 min              |
| 2       | T + 5 min  | **Reminder**      | T + 10 min             |
| 3       | T + 15 min | **Final failure** | — (terminal)           |

An operator can **acknowledge** any escalation at any point in the flow
via `POST /api/decisions/escalations/{id}/ack`. Acknowledgement marks
the escalation `RESOLVED` and stops the schedule immediately.

If no acknowledgement arrives by the third attempt, the escalation is
marked `MANUAL_REQUIRED` and the incident is handed off to manual
intervention. The final email summarises the unresolved action and lists
the recommended manual steps.

The subsystem is **idempotent** and **crash-safe**: every attempt is
recorded in `notifications[]` before the next is scheduled, so a restart
mid-flow resumes from the correct state.

---

## 2. Where it lives

```
app/decision/escalation/
├── __init__.py      Public API: escalate(), ack(), list_pending()
├── queue.py         Persistence + state machine (Escalation, EscalationStatus)
├── templates.py     Three email templates (initial, reminder, final_failure)
└── worker.py        APScheduler job — fires due attempts on schedule
```

Plus an API surface:

```
app/api/routes/escalations.py    GET/POST endpoints for the operator UI
```

Plus DDL:

```
app/persistence/schemas.py       ESCALATIONS_DDL, ESCALATIONS_ALTER_DDL
```

Plus Postgres methods:

```
app/persistence/postgres.py      save_escalation, get_escalation,
                                 list_escalations, list_escalations_due,
                                 get_escalation_by_decision
```

---

## 3. Key data structures

### `Escalation`

The full escalation record — one row per escalation, mirrors the
`escalations` table:

```python
@dataclass
class Escalation:
    id: str                                      # ESC-YYYYMMDD-HHMMSS-xxxx
    decision_id: str                             # links to decision_log
    anomaly_id: str                              # links to anomaly_events
    service_id: str
    status: EscalationStatus = PENDING
    attempt: int = 0                             # 0 before first send
    max_attempts: int = 3
    next_attempt_at: datetime | None = None
    notifications: list[dict] = []               # every attempt, ordered
    response: dict | None = None                 # ack payload
    failure_report: str | None = None            # populated on MANUAL_REQUIRED
    created_at: datetime = ...
    updated_at: datetime = ...
```

### `EscalationStatus`

The state machine:

```python
class EscalationStatus(str, Enum):
    PENDING          = "PENDING"          # created; first email not yet sent
    AWAITING_HUMAN   = "AWAITING_HUMAN"   # at least one attempt sent
    RESOLVED         = "RESOLVED"         # operator acked (terminal)
    MANUAL_REQUIRED  = "MANUAL_REQUIRED"  # 3 attempts exhausted (terminal)
```

### Notification entry (inside `notifications[]`)

Each attempt appends one entry:

```json
{
    "attempt": 1,
    "sent_at": "2026-11-18T17:45:00+00:00",
    "subject": "[SHARP] ⚠ Human approval required: RESTART_POD on metrics-collector",
    "sent": true,
    "error": null
}
```

`sent = false` distinguishes DRY-RUN (SMTP not configured) from a real
delivery failure (same field, different `error` string). The full email
body is logged separately in the `notifications` table.

---

## 4. How it fits in the pipeline

```
job.py :: poll_and_decide()
  │
  ├─ validate(recovery_action, ctx)                    → HUMAN_LOOP
  │
  ├─ persist_decision(decision)
  │
  └─ if decision.policy_outcome == HUMAN_LOOP:
       │
       └─ escalate(
            decision_id=decision.decision_id,
            anomaly_id=str(anomaly["id"]),
            service_id=sid,
          )                                             ◄── THIS LAYER
            │
            └─ enqueue() → INSERT escalations (status=PENDING, next_attempt_at=now)

                              (background worker)
                              ↓
              fire_due_attempts() runs every 30s:
                ├─ SELECT * FROM escalations
                │    WHERE next_attempt_at <= NOW()
                │      AND status IN ('PENDING','AWAITING_HUMAN')
                │
                ├─ for each due row:
                │    ├─ load decision + anomaly
                │    ├─ pick template (1=initial, 2=reminder, 3=final)
                │    ├─ emailer._send(...)                ← reuses SMTP transport
                │    ├─ record_attempt(...)               ← updates status, next_attempt_at
                │    └─ save_notification(...)            ← also writes to notifications table
                │
                └─ if attempt == 3: status = MANUAL_REQUIRED (terminal)
```

**Where the human comes in:**

```
Operator reads email
   ↓
POST /api/decisions/escalations/{id}/ack?decision=APPROVED&actor=ops@example.com
   ↓
queue.ack() → status = RESOLVED, response = {...}, next_attempt_at = None
   ↓
Worker sees status is terminal → skips forever
```

---

## 5. Public API

### Orchestrator (used by `job.py`)

| Function                                                          | Module        | Purpose                                    |
| ----------------------------------------------------------------- | ------------- | ------------------------------------------ |
| `escalate(decision_id, anomaly_id, service_id) -> Escalation`     | `__init__.py` | Convenience wrapper over `queue.enqueue()` |
| `ack(escalation_id, actor, decision, note) -> Escalation \| None` | `__init__.py` | Re-export of `queue.ack()`                 |
| `list_pending() -> list[Escalation]`                              | `__init__.py` | Re-export of `queue.list_pending()`        |

### Queue internals (used by worker and tests)

| Function                                                          | Module     | Purpose                            |
| ----------------------------------------------------------------- | ---------- | ---------------------------------- |
| `enqueue(...) -> Escalation`                                      | `queue.py` | Create PENDING escalation          |
| `ack(escalation_id, actor, decision, note) -> Escalation \| None` | `queue.py` | Mark RESOLVED with response        |
| `list_due(now=None) -> list[Escalation]`                          | `queue.py` | Rows with `next_attempt_at <= now` |
| `record_attempt(esc, subject, body, sent, error) -> Escalation`   | `queue.py` | Advance state after a send         |

### Worker

| Function                             | Module      | Purpose                                     |
| ------------------------------------ | ----------- | ------------------------------------------- |
| `fire_due_attempts() -> int`         | `worker.py` | One cycle; returns number of attempts fired |
| `start_escalation_worker(scheduler)` | `worker.py` | Register APScheduler job                    |

### Templates

| Function                                                         | Module         | Returns                    |
| ---------------------------------------------------------------- | -------------- | -------------------------- |
| `initial(esc, decision, anomaly) -> (subject, text, html)`       | `templates.py` | Attempt 1 email            |
| `reminder(esc, decision, anomaly) -> (subject, text, html)`      | `templates.py` | Attempt 2 email            |
| `final_failure(esc, decision, anomaly) -> (subject, text, html)` | `templates.py` | Attempt 3 email (terminal) |

### HTTP

| Method | Path                                   | Purpose                         |
| ------ | -------------------------------------- | ------------------------------- |
| GET    | `/api/decisions/escalations`           | List (filterable by status)     |
| GET    | `/api/decisions/escalations/pending`   | List PENDING + AWAITING_HUMAN   |
| GET    | `/api/decisions/escalations/{id}`      | Fetch one                       |
| POST   | `/api/decisions/escalations/{id}/ack`  | Operator acknowledgement        |
| POST   | `/api/decisions/escalations/{id}/fire` | Force-fire next attempt (debug) |

---

## 6. Configuration

### A. Env vars

| Env var                        | Type  | Default | Purpose                                        |
| ------------------------------ | ----- | ------- | ---------------------------------------------- |
| `ESCALATION_POLL_INTERVAL_SEC` | `int` | `30`    | How often the worker scans for due escalations |

The **attempt delays** are fixed constants in `queue.py`:

```python
ATTEMPT_1_DELAY_SEC = 0      # initial is immediate
ATTEMPT_2_DELAY_SEC = 300    # 5 min after attempt 1
ATTEMPT_3_DELAY_SEC = 600    # 10 min after attempt 2 → T+15 total
```

These match §3.5.3 of the report exactly. Changing them requires an
edit + restart. If you ever want operator-tunable windows, promote them
to `runtime_settings.SETTINGS_SPEC`.

### B. SMTP (shared with `notifications.emailer`)

The escalation worker **reuses** `app.notifications.emailer._send()`, so
all SMTP settings (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
`SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS`, `NOTIFY_RECIPIENT`) are
shared with the general notifier. See `.env.example` for the full list.

**DRY-RUN:** if `SMTP_PASSWORD` is empty _or_ `SMTP_USER` is empty, the
emailer falls back to DRY-RUN mode (logs the attempt, records
`SKIPPED`, still schedules the next attempt). This means the escalation
worker functions without SMTP configured — useful in dev.

### C. Postgres schema

`ESCALATIONS_DDL` (in `persistence/schemas.py`) is in `BATCH1_DDL`. The
`next_attempt_at` column was added later via `ESCALATIONS_ALTER_DDL`,
also in `BATCH1_DDL` (immediately after `ESCALATIONS_DDL`). Both run
idempotently on every boot.

The escalations worker assumes the following tables exist:

- `escalations` (created by `ESCALATIONS_DDL`)
- `notifications` (created by `NOTIFICATIONS_DDL` in `BATCH3_DDL`)

Both are created before any decision fires, so ordering is safe.

---

## 7. Failure modes

The escalation subsystem is designed to **never silently lose an
incident**. Every failure path leads to either a retry, a fallback, or
an explicit terminal state.

| Condition                                       | Behaviour                                                                                                                                                                                                                                           |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| SMTP not configured (DRY-RUN)                   | `_send()` returns `(False, "smtp_not_configured")`. Attempt is recorded. Next attempt scheduled.                                                                                                                                                    |
| SMTP connection fails (auth, network)           | `_send()` returns `(False, error_string)`. Attempt is recorded with `sent: false`. Retry in 60s instead of 5 min.                                                                                                                                   |
| Decision referenced by escalation is missing    | Worker logs `WARNING` and skips. Escalation stays due — retried next cycle.                                                                                                                                                                         |
| Anomaly referenced by escalation is missing     | `templates.*` receives `anomaly=None`; still produces a valid email (uses `service_id`).                                                                                                                                                            |
| Worker crashes mid-cycle                        | Next cycle re-queries `list_due()`; idempotent because `verdict IS NULL` filter isn't relevant here — but `next_attempt_at` is. Escalation may fire twice if crash happened _after_ email send but _before_ `record_attempt`. **Known limitation.** |
| Operator acks after MANUAL_REQUIRED             | `ack()` detects terminal status and returns the existing row unmodified. Response is `RESOLVED` (idempotent-safe).                                                                                                                                  |
| Operator acks a non-existent escalation         | `ack()` returns `None`; route returns 404.                                                                                                                                                                                                          |
| Double ack                                      | First ack wins; second returns the already-RESOLVED row.                                                                                                                                                                                            |
| Unknown status in `ack` param                   | FastAPI `Query(... pattern="^(APPROVED                                                                                                                                                                                                              | REJECTED)$")` rejects with 422. |
| Postgres unavailable during `escalate()`        | Exception bubbles to `job.py`; decision persists but escalation isn't created. **Critical gap** — see below.                                                                                                                                        |
| Postgres unavailable during `fire_due_attempts` | Worker logs `ERROR`, next cycle retries. No incident is lost.                                                                                                                                                                                       |

### The critical gap (worth documenting in §8.3)

If `escalate()` fails because Postgres is unavailable _after_ the
decision is persisted, the incident has a `decision_log` row with
`policy_outcome = HUMAN_LOOP` but no matching `escalations` row. Nothing
retries the escalation.

**Mitigation:** a future sweep job should query
`decision_log WHERE policy_outcome = 'HUMAN_LOOP' AND id NOT IN (SELECT decision_id FROM escalations)`
and backfill. This is documented here so the gap is explicit, not
implicit. If the report wants to claim "no incident is ever lost," this
gap must either be closed or reframed.

### Known limitations

1. **No email threading.** Each attempt is a standalone email with its
   own `Message-ID` (generated by `emailer._send()`). Gmail will not
   thread attempts for the same escalation. Adding `In-Reply-To` /
   `References` headers with the previous attempt's `Message-ID` is a
   small enhancement (~15 lines) but requires storing the message ID in
   `notifications[]` (which we do, just not the SMTP `Message-ID` —
   we store our own `NTF-*` ID).

2. **Reminder windows are not operator-tunable.** They're fixed at
   `T+5` / `T+15`. For a high-severity incident, 5 minutes may feel
   too long; for a low-severity one, too short. Making them tunable is
   a natural Phase 5 improvement.

3. **Terminal states are truly terminal.** A `RESOLVED` escalation
   cannot be un-resolved, and a `MANUAL_REQUIRED` escalation cannot be
   re-queued. This is intentional (audit integrity) but means a
   mistaken ack cannot be undone through the API. An admin SQL update
   is required. Consider adding a `POST /reset` route gated by admin
   role if this becomes a pain point.

4. **No "escalation reason" field.** The email template infers reason
   from the decision (action, risk, confidence). If the operator wants
   to know _why_ the framework chose HUMAN_LOOP (e.g. "risk=HIGH
   because blast radius = 5"), that's in `decision_log.context` but
   not surfaced in the email body. A one-line addition to the templates
   would fix this.

---

## 8. Tests

All tests run without SMTP and without Postgres. `postgres_store` is
monkeypatched with a fake; the emailer is called in DRY-RUN mode.
Expected green count: **13**.

| File                                 | What it proves                                                         |
| ------------------------------------ | ---------------------------------------------------------------------- |
| `tests/test_escalation_queue.py`     | State machine: enqueue → attempt → attempt → attempt → MANUAL_REQUIRED |
| `tests/test_escalation_queue.py`     | `ack()` on pending, resolved, and non-existent                         |
| `tests/test_escalation_templates.py` | Three templates produce valid subject + text + HTML                    |
| `tests/test_escalation_templates.py` | Attempt counts appear in body (1 of 3, 2 of 3, 3 of 3)                 |
| `tests/test_escalation_routes.py`    | List, get, ack (APPROVED + REJECTED), 404 paths                        |

Run all:

```bash
cd services/decision-engine
uv run pytest tests/test_escalation_*.py -v
```

### Live verification (end-to-end)

```bash
# 1. Set up the environment (single terminal)
cd services/decision-engine
uv run uvicorn app.main:app --reload --port 8000

# 2. In a second terminal — trigger a scenario that produces HUMAN_LOOP
curl -X POST http://localhost:8000/api/mock/scenario/all_healthy
sleep 40
curl -X POST http://localhost:8000/api/mock/scenario/payment_slowdown
sleep 25

# 3. Confirm decisions were made
curl "http://localhost:8000/api/decisions/recent?limit=5"
# → at least one decision with "policy": {"outcome": "HUMAN_LOOP", ...}

# 4. Confirm escalation rows were created
curl http://localhost:8000/api/decisions/escalations/pending
# → {"count": N, "escalations": [{...status: "PENDING"...}, ...]}

# 5. Watch the log for the worker firing attempt 1
# In terminal 1, you should see:
#   Escalation ESC-...: attempt 1/3 sent (status now AWAITING_HUMAN)
#   OR (if SMTP is not configured):
#   Email DRY-RUN (SMTP not configured) → to=... subject='[SHARP] ⚠ Human approval required: ...'

# 6. Acknowledge an escalation
ESC_ID=$(curl -s http://localhost:8000/api/decisions/escalations/pending | jq -r '.escalations[0].id')
curl -X POST "http://localhost:8000/api/decisions/escalations/$ESC_ID/ack?decision=APPROVED&actor=ops@example.com"

# 7. Confirm it's resolved
curl http://localhost:8000/api/decisions/escalations/$ESC_ID
# → {"status": "RESOLVED", "response": {"decision": "APPROVED", "by": "ops@example.com", ...}}
```

### Force-fire for demo

If you don't want to wait 5 minutes for the reminder:

```bash
curl -X POST "http://localhost:8000/api/decisions/escalations/$ESC_ID/fire"
# → forces next_attempt_at = now, then runs one worker cycle immediately
```

---

## 9. Research mapping

The escalation subsystem implements several distinct sections across
the report and proposal.

### Component 2 report

| Report section                                  | Implemented in                                             |
| ----------------------------------------------- | ---------------------------------------------------------- |
| §3.5.3 Human-in-the-Loop (3-attempt protocol)   | `queue.py` state machine + `templates.py` + `worker.py`    |
| §3.5.3.1 Attempt 1 — Initial notification       | `templates.initial()`                                      |
| §3.5.3.2 Attempt 2 — Reminder with warning flag | `templates.reminder()`                                     |
| §3.5.3.3 Attempt 3 — Final failure report       | `templates.final_failure()`                                |
| §3.5.4 AUTO-EXECUTE (negative case)             | Escalation is the alternative path when AUTO isn't granted |
| §3.6 Human Escalation State Machine             | `EscalationStatus` + transitions in `record_attempt()`     |

### Proposal

| Proposal section                           | Implementation                                                                |
| ------------------------------------------ | ----------------------------------------------------------------------------- |
| §3.4 (Validation layer — human escalation) | `HUMAN_LOOP` outcome → `escalate()` in `job.py`                               |
| §4.3 (Human-in-the-loop escalation)        | This entire package                                                           |
| §6 (Email channel explicitly)              | `emailer._send()` over SMTP; Gmail App Password in config                     |
| §7 (Governed autonomy)                     | Human override is mandatory for the high-risk subset                          |
| §9 (Known limitations: Gmail only)         | This subsystem only ships an SMTP transport — PagerDuty/Slack are future work |

### What this layer does **not** do (and where that lives)

| Concern                                 | Where it actually lives                       |
| --------------------------------------- | --------------------------------------------- |
| Deciding that HUMAN_LOOP is needed      | `app/decision/validation/policy_matrix.py`    |
| Confidence / risk reasoning             | `app/decision/validation/`                    |
| Cooldown / counter / idempotency checks | `app/decision/guardrails/`                    |
| Kubernetes execution                    | `app/decision/executor_kubernetes.py`         |
| Decision persistence                    | `app/decision/log.py`                         |
| SMTP transport implementation           | `app/notifications/emailer.py`                |
| Notification audit trail                | `notifications` table (shared with `emailer`) |

### Design rationale worth stating in the report

The three-attempt structure is not arbitrary. It reflects a **specific
operational claim**:

> A single email is easy to miss. A single escalation is easy to ignore.
> Two escalations may be dismissed as routine. The **third** — a formal
> final failure report marked "MANUAL_INTERVENTION_REQUIRED" — is the
> escalation that makes the incident **impossible to overlook**.

The research contribution is not "we send emails." It is:

1. Every attempt is **recorded** (`notifications[]`), so the audit trail
   is complete even if SMTP fails.
2. Every attempt is **scheduled deterministically** (`next_attempt_at`),
   so the flow survives restarts.
3. The **terminal state** (`MANUAL_REQUIRED`) explicitly declares the
   framework's limit — it stops trying, rather than silently dropping
   the incident.
4. The **operator can override** at any point via `POST /ack`, and the
   override is **permanent** (`RESOLVED` is terminal).

Together these are what let the report claim "human-in-the-loop
escalation" as a real capability rather than a marketing phrase.

---

## Summary

| Question                                                  | Answer                                                             |
| --------------------------------------------------------- | ------------------------------------------------------------------ |
| What triggers an escalation?                              | `PolicyOutcome.HUMAN_LOOP` from the Validation Layer               |
| How many attempts?                                        | 3 — initial, reminder, final failure                               |
| What's the timing?                                        | T+0, T+5min, T+15min                                               |
| What happens if the operator acks?                        | Status → `RESOLVED`; no further attempts                           |
| What happens if the operator ignores?                     | After 3 attempts → `MANUAL_REQUIRED` (terminal)                    |
| Does it survive restart?                                  | Yes — state is in Postgres                                         |
| Does it work without SMTP configured?                     | Yes — DRY-RUN mode logs + records but doesn't send                 |
| Can the operator un-ack?                                  | No (terminal by design) — requires SQL                             |
| Is the flow tunable at runtime?                           | No (poll interval yes; attempt windows no)                         |
| Does it re-send to multiple channels?                     | No — Gmail SMTP only (PagerDuty/Slack out of scope)                |
| Does it capture the operator's decision?                  | Yes — `response` field records who/what/when/note                  |
| Does it capture failure reasons?                          | Yes — every `notifications[]` entry has `sent`, `error`, `sent_at` |
| Is the escalation the _only_ way to resolve a HUMAN_LOOP? | Yes (until manual SQL intervention, which is discouraged)          |

```

```
