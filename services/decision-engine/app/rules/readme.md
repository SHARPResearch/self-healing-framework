# Rule Engine — Explained Simply

Forget the code for a moment. Start with the story.

## The core question

At 10:00 AM, your system has 15 services. Suddenly, `auth-service` starts misbehaving.

```text
10:00:00  auth-service CPU spikes to 95%
10:00:01  Detection layer (Component 1) fires an AnomalySignal
10:00:02  The Rule Engine asks one question:

          "What should we do about this?"
```

That is the whole purpose of the Rule Engine: to decide which action is appropriate based on the current facts.

To answer correctly, the engine needs to know:

- What is happening? → the anomaly details
- Where is it in the graph? → is it a leaf or a hub?
- Who else is affected? → isolated or cascading?
- What rules apply? → restart, scale, or do nothing?

Each of the four files below answers one of these questions.

---

## 1. `context.py` — The fact sheet

Think of this as a patient's medical chart.

When a service enters the rule engine, it needs a full summary of the situation:

- identity and metadata
- recent anomaly history
- upstream and downstream relationships
- telemetry and health data
- graph importance and blast radius

`context.py` builds that context in one place.

### In the story

```text
Anomaly fires at 10:00:02 for auth-service.
context.py asks:
- What's auth-service's CPU? -> 95%
- What does auth-service call? -> user-service, postgres, redis
- Who calls auth-service? -> web-bff, mobile-bff
- Are those neighbors healthy? -> postgres is down
- How important is it? -> centrality 1.72
- If it fails, who else is affected? -> blast radius 5 services
```

The output is an `AnomalyContext` object: a single structured fact sheet.

### Why it exists

Without this layer, every rule would need to manually query telemetry, graph data, and centrality values. That would be messy, repetitive, and slow. `context.py` gathers everything once and hands it to the engine.

### Key fields

| Field          | Meaning                                                   |
| -------------- | --------------------------------------------------------- |
| `anomaly.*`    | raw anomaly details such as score, severity, and metric   |
| `service.*`    | service metadata such as layer, team, runtime, and health |
| `infra.*`      | CPU, memory, disk, and infrastructure health              |
| `app.*`        | latency, RPS, and error metrics                           |
| `upstream`     | services this service depends on                          |
| `downstream`   | services that depend on this service                      |
| `centrality`   | graph importance score (roughly 1.0–2.0)                  |
| `blast_factor` | how much impact a failure would cause                     |
| `kind`         | `NORMAL`, `ISOLATED`, `UPSTREAM`, or `CASCADING`          |

### One-line summary

`context.py` gives the engine everything it needs to reason about the anomaly in one object.

---

## 2. `classifier.py` — The diagnosis

Once the chart is built, the next question is: what kind of problem is this?

`classifier.py` examines the graph neighbors and classifies the situation.

| Diagnosis   | Meaning                                             | Example                                              |
| ----------- | --------------------------------------------------- | ---------------------------------------------------- |
| `NORMAL`    | no meaningful anomaly                               | nothing is actually wrong                            |
| `ISOLATED`  | only this service is affected                       | a single service is slow but neighbors are fine      |
| `UPSTREAM`  | this service depends on something unhealthy         | `auth-service` is failing because `postgres` is down |
| `CASCADING` | the problem is spreading through dependent services | `auth-service` failure impacts `web-bff`             |

### In the story

```text
10:00:03  classifier checks the chart
- upstream (postgres) is DOWN
- downstream (web-bff) is HEALTHY

Result: UPSTREAM
```

That means: do not restart `auth-service`; fix the dependency causing the issue.

### Why it exists

A naive engine sees a high CPU spike and immediately restarts the service. That is often wrong. If the real problem is an upstream dependency, restarting the service only masks the symptom.

### Correct responses by classification

| Classification | Correct response                                         |
| -------------- | -------------------------------------------------------- |
| `ISOLATED`     | restart or scale the service itself                      |
| `UPSTREAM`     | fix the upstream dependency                              |
| `CASCADING`    | identify the root cause rather than treating the symptom |

### One-line summary

`classifier.py` answers: is this a local issue, an upstream issue, or a cascade?

---

## 3. `engine.py` — The rule evaluator

Now the engine knows what kind of problem it is. The next step is to evaluate the rules.

This is the actual decision-making layer. It reads the rule set and checks whether the current context matches any of the rule conditions.

### In the story

```text
10:00:04  engine evaluates 7 rules

Rule 1: restart_pod_high_cpu
- severity in [high, medium]
- score >= 0.6
- service degraded/down
- cpu >= 0.75

Check against auth-service:
- severity = high
- score = 0.92
- health = degraded
- cpu = 0.95

Result: MATCH
Candidate: RESTART_POD, confidence 0.83
```

Other rules may fail because of missing conditions, lower saturation, or unrelated deployment state. The engine keeps only valid matches and ranks them by priority and confidence.

### Why it exists

This is the heart of the module. Everything else supports the decision this file makes.

It does four main things:

1. filters rules by `applies_to`
2. evaluates the `when` condition tree against the context
3. creates `RuleCandidate` objects with blended confidence
4. sorts results by priority and confidence

### One-line summary

`engine.py` asks: which rules match this situation, and which candidate action should rank highest?

---

## 4. `root_cause.py` — The common ancestor finder

This file deals with the bigger picture: not one failing service, but several failing services at once.

It tries to answer: among many simultaneous anomalies, which one is the real source?

### In the story

```text
10:00:05  five anomalies are being processed
- auth-service (0.92)
- user-service (0.72)
- web-bff (0.74)
- mobile-bff (0.71)
- api-gateway (0.68)
```

`root_cause.py` walks the graph and asks:

- Is the upstream neighbor sick?
- Is the downstream neighbor sick?
- Is this the actual root, or just a propagated symptom?

It identifies the true root service and avoids noisy, conflicting actions.

### Why it exists

Without this file, the system could trigger multiple recovery actions at once: restart `auth-service`, restart `web-bff`, restart `api-gateway`, and so on. That leads to chaos and redundant actions.

### One-line summary

`root_cause.py` answers: among multiple failures, which one is the actual source?

---

## Full story: the flow in order

```text
10:00:00  auth-service CPU spikes to 95%
10:00:01  Component 1 fires AnomalySignal
10:00:02  context.py builds the fact sheet
          (upstream, downstream, centrality, blast radius, telemetry)
10:00:03  classifier.py reads the chart -> kind = UPSTREAM
          (because postgres is down)
10:00:04  engine.py evaluates rules -> matches 2
          Top candidate: RESTART_POD (confidence 0.83)
10:00:05  root_cause.py sees 5 anomalies -> root = auth-service
```

Result:

```text
We recommend RESTART_POD on auth-service with 0.83 confidence.
```

That is the Rule Engine in one flow.

---

## Architecture diagram

```mermaid
flowchart TD
    A[AnomalySignal from Component 1] --> B[context.py]
    B --> C[AnomalyContext]
    C --> D[classifier.py]
    D --> E{Problem type}
    E -->|ISOLATED| F[Restart or scale service]
    E -->|UPSTREAM| G[Fix upstream dependency]
    E -->|CASCADING| H[root_cause.py]
    H --> I[Find true root service]
    I --> J[engine.py]
    J --> K[RuleCandidate[]]
    K --> L[Priority + confidence ranking]
    L --> M[Recommended action]

    subgraph Rule Engine
        B
        D
        J
        H
    end

    M --> N[Validation / Action Layer]
```

This diagram shows the actual flow: the engine gathers facts, classifies the anomaly, evaluates rules, and finds the real root cause before producing a recommendation.

---

## Why each file matters

| File            | What if it did not exist?                                |
| --------------- | -------------------------------------------------------- |
| `context.py`    | every rule would need custom graph and telemetry queries |
| `classifier.py` | the engine would fire the wrong action on cascades       |
| `engine.py`     | no rules would be evaluated at all                       |
| `root_cause.py` | multiple anomalies would cause conflicting actions       |

Each file solves a different problem that the others cannot solve alone.

---

## Data flow

```text
AnomalySignal from Component 1
        ↓
┌─────────────────────┐
│   context.py        │  Build the fact sheet
│   → AnomalyContext  │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│  classifier.py      │  Diagnose: isolated / upstream / cascade
│   → ctx.kind        │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│    engine.py        │  Evaluate rules and rank candidates
│  → RuleCandidate[]  │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│  root_cause.py      │  Find the true source service
│   → service_id      │
└─────────────────────┘
```

---

## One-word summary of each file

| File            | One-word summary |
| --------------- | ---------------- |
| `context.py`    | Gatherer         |
| `classifier.py` | Diagnoser        |
| `engine.py`     | Matcher          |
| `root_cause.py` | Detective        |

---

## What the Rule Engine does not do

The Rule Engine is only the reasoning layer. It does not directly execute actions.

| Rule Engine does                             | Not Rule Engine               |
| -------------------------------------------- | ----------------------------- |
| match rules against the anomaly              | restart the pod               |
| produce recommendations like `RuleCandidate` | call the Kubernetes API       |
| compute blended confidence                   | send escalation notifications |
| classify the problem context                 | validate risk or safety gates |

In other words:

> The Rule Engine decides which rules match the facts. It does not perform the action itself.

---

## The correct mental model

Think of it like a hospital triage system:

| Concept           | Hospital equivalent                            |
| ----------------- | ---------------------------------------------- |
| `AnomalySignal`   | patient arrives at the ER                      |
| `context.py`      | nurse collects vitals and history              |
| `classifier.py`   | doctor diagnoses the problem                   |
| `engine.py`       | protocol book matches the diagnosis            |
| `root_cause.py`   | identifies the real source of a group outbreak |
| `RuleCandidate[]` | treatment options                              |

The Rule Engine is the thinking part. Everything else acts on its output.

---

## How the Rule Engine uses the graph manager

`context.py` uses the graph manager to gather structural context when building the anomaly context.

```python
from app.core.graph_store import GraphStore
from app.core.centrality import CentralityCalculator
from app.core.blast_radius import BlastRadiusAnalyzer
```

The outputs are fed into the context:

| Graph output                                   | Stored in context                |
| ---------------------------------------------- | -------------------------------- |
| `GraphStore().graph()`                         | `ctx.upstream`, `ctx.downstream` |
| `CentralityCalculator().compute()`             | `ctx.centrality`                 |
| `BlastRadiusAnalyzer().factor(sid)`            | `ctx.blast_factor`               |
| `BlastRadiusAnalyzer().reverse_reachable(sid)` | `ctx.blast_members`              |

This means the rules can reason about dependency structure, service importance, and blast radius in a consistent way.

### Example

```yaml
when:
    all:
        - metric: centrality
          op: ">="
          value: 1.5
        - metric: blast_radius.factor
          op: ">="
          value: 1.30
        - metric: graph.downstream
          op: "contains"
          value: "web-bff"
```

---

## Why this matters

Two services can have the same CPU spike, but different decisions.

| Scenario                                 | Centrality | Blast factor | Engine decision                |
| ---------------------------------------- | ---------: | -----------: | ------------------------------ |
| `notification-service` (leaf)            |       1.05 |         1.00 | low risk, restart safely       |
| `postgres-primary` (critical dependency) |       1.95 |         1.39 | high risk, requires validation |

Same anomaly score. Different decision. The difference is the graph context.

---

## Final takeaway

The Rule Engine is not the executor. It is the reasoning layer.

- `context.py` gathers facts
- `classifier.py` diagnoses the issue
- `engine.py` matches applicable rules
- `root_cause.py` identifies the true source

Together, they answer the question:

> Given the anomaly and the system graph, what rules should fire?

This is the Rule Engine's real job.

---

## TL;DR

| Question                                             | Answer                                       |
| ---------------------------------------------------- | -------------------------------------------- |
| Does the Rule Engine use the graph manager?          | Yes, through `context.py`                    |
| Does it use centrality?                              | Yes, via `ctx.centrality`                    |
| Does it use blast radius?                            | Yes, via `ctx.blast_factor`                  |
| Does it use upstream/downstream relationships?       | Yes, via `ctx.upstream` and `ctx.downstream` |
| Is the core flow already wired?                      | Yes                                          |
| Are Redis, sharding, and versioning implemented now? | No, those are future work                    |

The Rule Engine is already the decision layer. The rest of the system is responsible for turning those decisions into real action.

---

# Part 2 — Hybrid Rule Management (as built)

The conceptual walkthrough above covers the four reasoning files. This part
documents what actually exists in `app/rules/` today: the hybrid rule model,
the persistence layer, the REST API, and how to exercise it from Swagger.

## Files in this folder

| File            | Role                                                                                                            |
| --------------- | --------------------------------------------------------------------------------------------------------------- |
| `context.py`    | Builds the `AnomalyContext` fact sheet (see Part 1).                                                            |
| `classifier.py` | Classifies the anomaly: `NORMAL` / `ISOLATED` / `UPSTREAM` / `CASCADING`.                                       |
| `engine.py`     | Evaluates `when` trees against the context, emits ranked `RuleCandidate[]`.                                     |
| `root_cause.py` | Among many anomalies, finds the true source service.                                                            |
| `models.py`     | Pydantic models: `Rule`, `RuleAction`, condition tree (`All`/`Any`/`Leaf`), enums.                              |
| `seeds.py`      | `SEED_RULES` (8 defaults) + `SEED_TEMPLATES` (3 read-only starters).                                            |
| `repository.py` | Postgres CRUD: `upsert`, `patch_rule`, `toggle_rule`, `create_custom_rule`, `delete_custom_rule`, audit writes. |
| `validation.py` | `validate_rule_payload()` / `count_matches()` — pre-flight checks for the UI builder.                           |
| `registry.py`   | In-memory `rule_registry`: loads evaluatable rules, hot-reloadable.                                             |

## The three levels (hybrid model)

The UI is built on a three-level mental model, and the data model enforces it:

| Level         | Who      | Can do                                                                            | Columns                                      |
| ------------- | -------- | --------------------------------------------------------------------------------- | -------------------------------------------- |
| 1. Default    | SHARP    | toggle on/off, customize thresholds                                               | `is_default = TRUE`                          |
| 2. Customized | Operator | edit priority/description/`applies_to`/guardrails. **Condition & action frozen.** | `is_default = TRUE`, `parent_rule_id` set    |
| 3. Custom     | Operator | full control: build condition tree, pick action                                   | `is_default = FALSE`, `created_by = <actor>` |
| — Templates   | SHARP    | read-only starting points; **never fire**                                         | `is_template = TRUE`                         |

Key invariants enforced in code:

- **Defaults and templates cannot be deleted.** `DELETE /api/rules/{id}` returns
  `403` for either. The frontend hides the delete button behind a "Protected"
  badge. Default rules can still be _disabled_ (toggled off).
- **Templates never fire.** `registry.all()` only returns rules where
  `enabled AND NOT is_template AND status == ACTIVE`.
- **Default rule action is frozen.** PATCH rejects a change to `then`/`id` with
  `400 "Cannot change action of default rule"` — not silently ignored.
- **Only custom rules are deletable**, and only those owned by the actor's org
  (ownership guard in `repository.delete_custom_rule`).

### Rule status lifecycle

```
DRAFT ──activate──▶ ACTIVE ──archive──▶ ARCHIVED
  ▲                    │
  └────── re-activate ─┘
```

Only `ACTIVE` rules are evaluated. `DRAFT` is what the "Save as Draft" button
in the builder writes; the builder's "Activate" runs validation first and only
saves on success.

## Seed set

On boot, `registry.seed_if_empty()` inserts **any seed/template whose `id` is
not already present** (idempotent per-id — existing rows are never overwritten,
so operator edits survive restarts). If the table is already populated, the
migration also backfills `is_default = TRUE` for legacy rows with
`created_by = 'system' AND is_template = FALSE`.

**8 default rules** (`is_default = TRUE`):

1. `restart_pod_high_cpu` — cpu high, service degraded
2. `scale_deployment_high_rps` — saturation high, latency rising
3. `open_circuit_breaker` — downstream error rate high
4. `flush_cache_stale` — cache hit low, memory high
5. `increase_db_pool` — pool near max, p95 high
6. `scale_kafka_consumers` — queue depth high
7. `rollback_bad_deploy` — anomaly within 5 min of a deploy
8. `restart_pod_crash_loop` — repeated restarts, unhealthy

**3 templates** (`is_template = TRUE`): `template_scale_on_latency`,
`template_restart_on_error_rate`, `template_scale_consumers_on_lag`.

## REST API

Base path `/api/rules`. All endpoints are tagged `rules` and appear in Swagger.
Write endpoints accept an optional `X-Actor` header (default `unknown`) used to
attribute the change in the audit log.

| Method   | Path                            | Purpose                                                                                |
| -------- | ------------------------------- | -------------------------------------------------------------------------------------- |
| `GET`    | `/api/rules`                    | List rules. Filters: `?type=default\|custom\|templates\|all`, `?status=`, `?enabled=`. |
| `GET`    | `/api/rules/templates`          | List only templates.                                                                   |
| `GET`    | `/api/rules/meta/stats`         | Registry counts (total/evaluatable/default/custom/templates).                          |
| `GET`    | `/api/rules/{rule_id}`          | Fetch one rule.                                                                        |
| `GET`    | `/api/rules/{rule_id}/audit`    | Audit history (`?limit=`).                                                             |
| `POST`   | `/api/rules/custom`             | Create a custom rule (body may include `status`).                                      |
| `PATCH`  | `/api/rules/{rule_id}`          | Customize a rule (priority/description/`applies_to`/guardrails).                       |
| `POST`   | `/api/rules/{rule_id}/toggle`   | Enable/disable (`?enabled=` forces a value).                                           |
| `POST`   | `/api/rules/{rule_id}/validate` | Validate a payload; `?test=true` also dry-runs against recent anomalies.               |
| `POST`   | `/api/rules`                    | Upsert a rule by id (admin/seed path).                                                 |
| `DELETE` | `/api/rules/{rule_id}`          | Delete a **custom** rule (403 for default/template).                                   |
| `POST`   | `/api/rules/reload`             | Hot-reload the in-memory registry from Postgres.                                       |

`validate` returns:

```json
{
    "valid": true,
    "errors": [],
    "warnings": ["unknown metric root 'foo'"],
    "rule": { "...": "normalized rule" },
    "match_preview": {
        "total_anomalies": 15,
        "matched_count": 2,
        "message": "matched 2 of 15 recent anomalies"
    }
}
```

## Swagger / API checker

FastAPI serves an interactive API checker with **no extra dependency**:

| URL                                  | What it is                                                                                                                                                                      |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `http://localhost:8000/docs`         | **Swagger UI** — expand any endpoint, click "Try it out", send a real request, see the live response. Use this to exercise rule CRUD, toggle, validate and the debug endpoints. |
| `http://localhost:8000/redoc`        | ReDoc — clean read-only reference built from the same schema.                                                                                                                   |
| `http://localhost:8000/openapi.json` | Raw OpenAPI 3 schema (feed to Postman/Insomnia or codegen).                                                                                                                     |

Start the server, then open `/docs`:

```bash
cd services/decision-engine
uv run uvicorn app.main:app --reload --port 8000
# then browse http://localhost:8000/docs
```

Endpoints are grouped by tag (`rules`, `decisions`, `anomalies`, `graph`,
`history`, `mock`, `health`). To attribute a change in the audit log, set the
`X-Actor` header on the request in Swagger.

### Quick checks from `/docs`

1. `GET /api/rules/meta/stats` — confirm the registry is loaded.
2. `GET /api/rules?type=custom` — custom rules only.
3. `POST /api/rules/{rule_id}/validate?test=true` — dry-run a payload against
   recent anomalies.
4. `DELETE /api/rules/restart_pod_high_cpu` — expect **403** (default rules are
   protected; only custom rules delete).
5. `GET /api/debug/db` — row counts for the connected Neon/Tiger stores.

## Tests

```bash
cd services/decision-engine
uv run pytest tests/test_rule_crud.py tests/test_rule_validation.py -v
```

These run without a live Postgres: the repository is monkeypatched with an
in-memory fake and the HTTP layer is driven through FastAPI's `TestClient`.

## Related files outside this folder

| File                          | Why it matters here                                                |
| ----------------------------- | ------------------------------------------------------------------ |
| `app/api/routes/rules.py`     | The HTTP layer over this module (12 endpoints + ownership guards). |
| `app/persistence/postgres.py` | `save_rule_audit()` / `list_rule_audit()`.                         |
| `app/persistence/schemas.py`  | `RULES_HYBRID_DDL` (columns + backfill) and `RULE_AUDIT_DDL`.      |
| `app/persistence/migrate.py`  | Runs the hybrid + audit DDL on boot.                               |
