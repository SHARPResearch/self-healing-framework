# Component 1 ⇄ Component 2 — live integration, mismatches and test path

Status: implementation + test guide for **live mode** (Online Boutique on
minikube). Replay/SMD mode still works and is the fallback.

---

## 1. Mismatches: the report vs the code

`docs/.../Component 2 - Context-Aware…docx` describes a design. Several claims
did not hold in the implementation. Fixed ones are marked ✅, design-only ones
are listed honestly as ⚠️.

| # | Report says | Code did | Status |
|---|---|---|---|
| 1 | Rules are **context-aware** and apply to any service | Rules were scoped `layers: ["domain","bff"]` / `services: ["api-gateway","waf-proxy"]` — nothing matched on a real cluster | ✅ **Fixed** — 5 service-agnostic rules added (`generic_rules.py`), scoped `services: ["*"]`, driven only by score / classification / blast radius |
| 2 | The dependency graph is an **input** ("Graph Query"), owned by the graph manager | C2 loaded a private `seeds/topology.yaml` describing a synthetic fleet that does not exist in the cluster | ✅ **Fixed** — C1 serves `GET /api/topology`; C2 loads it at boot + every 60 s, seed only as fallback |
| 3 | Live topology = the deployed microservices | Seed graph had `waf-proxy → api-gateway → orders-service`, none of which are in `online-boutique` | ✅ **Fixed** — C1 serves the real Online Boutique call graph in live mode, filtered to running deployments |
| 4 | Anomalies arrive from Component 1 | Ingestion iterated only the 16 hardcoded demo services → every live anomaly was skipped | ✅ **Fixed** — ingestion iterates C1's fleet ∪ local catalog |
| 5 | Engine accepts any service | `job.py` skipped `sid not in SERVICES`; `_infra("frontend")` raised `KeyError` | ✅ **Fixed** — merged catalog (local + graph nodes) and a neutral telemetry fallback |
| 6 | BLOCK → **re-query graph + telemetry, re-evaluate with fresh context** | BLOCK is terminal; the decision is logged and never re-evaluated | ⚠️ **Not implemented.** Needs a retry counter per incident and a second decision row per anomaly. Deliberate scope decision — flag it in the report or ask for it |
| 7 | Guardrails: cooldown → **idempotency** → **rate limiter** → **circuit breaker** | cooldown → counter → idempotency. No circuit breaker | ⚠️ **Partial.** Rate limiting exists as `max_per_hour`; no breaker. A breaker needs consecutive-failure tracking on `action_history` |
| 8 | Anomaly Receiver = **Redis Stream** | `anomaly_sink` polls Postgres/table + C1 every 5 s | ⚠️ **Design differs.** Redis is used for guardrail state and the event bus in replay, not as the anomaly transport |
| 9 | Dashboard fed by **WebSocket** | REST polling (5 s in the UI) | ⚠️ **Partial.** ml-backend has `/ws/events`; the decision-engine UI polls its REST API |
| 10 | Horizontal sharding, async queue + worker pool, Redis graph cache | One APScheduler job, in-process, single graph store | ⚠️ **Design only.** Documented as a design claim, not implemented. Say so in the report |
| 11 | Shadow verdicts: HELPED / NEUTRAL / UNNECESSARY | Emits `ACTION_WOULD_HAVE_HELPED`, `ACTION_WOULD_HAVE_BEEN_UNNECESSARY`, `ANOMALY_STILL_ACTIVE`, `UNKNOWN`, `HARMFUL` | ⚠️ **Naming differs** (`NEUTRAL` absent). Cosmetic |
| 12 | Evaluation metrics: unnecessary action rate, MTTR, root-cause rate, P50/P95/P99 | `unnecessary_action_rate` + mean resolution time exist; MTTR / latency percentiles not computed | ⚠️ **Partial** |

The three that would sink a demo — rules never matching, graph describing
non-existent services, live anomalies never entering the pipeline — are fixed.

---

## 2. What changed for live mode

```
C1 (ml-backend, :8002)                          C2 (decision-engine, :8000)
  /api/services  → score/status/model state  ──► anomaly_sink: one anomaly per incident
  /api/topology  → OB call graph             ──► GraphStore → centrality / blast radius
  /api/live/...  → real Chaos Mesh faults         catalog = local + graph nodes
                                                 rules = generic (any service)
                                                 executor → namespace online-boutique
```

| File | Change |
|---|---|
| `services/decision-engine/app/rules/generic_rules.py` | **new** — 5 service-agnostic rules covering AUTO / SHADOW / HUMAN |
| `app/rules/registry.py` | seeds those rules idempotently on boot |
| `app/integration/catalog.py` | **new** — catalog = demo entries ∪ graph nodes |
| `app/integration/topology.py` | **new** — load from C1, 60 s refresh, seed fallback |
| `app/integration/telemetry.py` | neutral fallback so an unknown service never raises |
| `app/decision/job.py` | accepts any catalog service |
| `app/ingestion/anomaly_sink.py` | iterates C1's fleet ∪ local catalog |
| `app/main.py` | loads topology from C1, schedules refresh |
| `app/api/routes/graph.py` | `POST /api/graph/refresh`, `GET /api/graph/source` |
| `services/ml-backend/app/topology.py` | **new** — SMD fleet topology (generated from the seed) |
| `services/ml-backend/app/topology_ob.py` | **new** — real Online Boutique call graph |
| `services/ml-backend/app/api/routes.py` | `GET /api/topology` (live → OB, replay → SMD) |
| `scripts/run-live.ps1` | **new** — one command for C1 + C2 + dashboard |

---

## 3. Run everything with one command

```powershell
# dry run: decisions are made, executions recorded as NOT_IMPLEMENTED
powershell -ExecutionPolicy Bypass -File scripts/run-live.ps1

# live: AUTO_EXECUTE really restarts pods in online-boutique
powershell -ExecutionPolicy Bypass -File scripts/run-live.ps1 -Live

# backends only
powershell -ExecutionPolicy Bypass -File scripts/run-live.ps1 -NoWeb
```

It preflights (ports, kubectl namespace, Prometheus on :9090), starts the three
processes, prefixes their logs `[C1] [C2] [WEB]`, and stops everything on Ctrl+C.
Full logs: `.run\C1.log`, `.run\C2.log`, `.run\WEB.log`.

**Prerequisites** (once per session):

```powershell
# cluster + Prometheus port-forward (the runner checks this)
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
```

---

## 4. A → Z test path

Every step has an expected result. Stop at the first mismatch.

### A. Topology is Component 1's

```powershell
curl http://localhost:8002/api/topology | ConvertFrom-Json | Select mode, version
curl http://localhost:8000/api/graph/source  | ConvertFrom-Json
```

- `mode` = `live`, `version` = a 12-char hash
- `/api/graph/source` → `source: "component1"`, `nodes: 12`, `edges: 16`

If it says `"seed"`, C2 started before C1: it self-corrects within 60 s, or
`curl -X POST http://localhost:8000/api/graph/refresh`.

### B. The graph is the real call graph

```powershell
curl http://localhost:8000/api/graph/ | ConvertFrom-Json | Select -Expand nodes | Select id, name
curl "http://localhost:8000/api/graph/blast-radius/frontend" | ConvertFrom-Json
```

- node ids are `frontend, checkoutservice, cartservice, …` (no `orders-service`)
- `frontend` blast radius size = 0 (nothing depends on it), `criticality` ≈ 2.0
- `productcatalogservice` blast radius size ≥ 3 (frontend, checkout, recommendation)

### C. Rules match a live service

```powershell
curl http://localhost:8000/api/rules | ConvertFrom-Json | Select -Expand rules |
  Where-Object { $_.id -like "generic_*" } | Select id, priority, enabled
```

Expect 5 rows, all enabled. Priorities 110–130, above the demo rules (≤ 100).

### D. Component 1 sees the fleet

```powershell
curl http://localhost:8002/api/services | ConvertFrom-Json |
  Select serviceId, status, anomalyScore, modelVersion
```

12 rows, all `status: watch` while healthy.

### E. Inject a real fault

```powershell
# a CPU fault on the frontend, via Component 1's live action endpoint
curl -X POST http://localhost:8002/api/live/frontend/cpu_stress -H "Content-Type: application/json"
```

C1 starts a Chaos Mesh experiment. Watch its status climb:

```powershell
1..12 | % { (curl http://localhost:8002/api/services | ConvertFrom-Json |
  Where-Object serviceId -eq "frontend").status; sleep 5 }
```

Expect `watch → warn → degrade → critical`.

### F. Anomaly is created by C2 from C1's signal

```powershell
curl "http://localhost:8000/api/anomalies/recent?limit=3" | ConvertFrom-Json |
  Select id, service_id, anomaly_score, severity, model_version
```

One row for `frontend`, `anomaly_score ≥ 0.5`, `model_version` filled in.
In C2's log: `NEW incident STARTED: ANM-frontend-…`.

### G. Context carries real telemetry + Component 1 provenance

```powershell
curl "http://localhost:8000/api/decisions/recent?limit=1" | ConvertFrom-Json |
  Select -Expand decisions | Select service_id, action, rule_id, @{n="outcome";e={$_.policy.outcome}},
  @{n="model";e={$_.component1.model_version}}, @{n="telemetry";e={$_.component1.telemetry_source}}
```

- `rule_id` starts with `generic_`
- `component1.model_version` is populated
- `telemetry.infra` = `snapshot` once the evidence window is captured, `mock`/neutral before that

### H. The decision follows the policy matrix

Expected by fault severity:

| Fault | Likely rule | Outcome |
|---|---|---|
| `frontend` cpu_stress | `generic_restart_isolated` (if isolated) | `AUTO_EXECUTE` (0.90, LOW) |
| `checkoutservice` incident | `generic_upstream_fallback` / `generic_cascading_scale` | `SHADOW_MODE` |
| fault on a service with many dependents | `generic_high_blast_scale` (risk HIGH) | `HUMAN_LOOP` |
| repeated fault inside the cooldown | guardrail veto | `BLOCK` |

### I. Open the dashboard

`http://localhost:5173/decisions` → newest row → the graph:

- **Anomaly received** shows a `C1 vN` badge and the model phase
- **Graph context** shows real upstream/downstream counts
- **Safety validation** shows confidence, risk and the outcome
- durations are milliseconds, not `—` (the timings instrumentation)

### J. AUTO_EXECUTE path

```powershell
curl http://localhost:8000/api/executions | ConvertFrom-Json | Select -Expand executions |
  Select decision_id, status, message
```

- dry run → `NOT_IMPLEMENTED` (expected, action recorded)
- `-Live` → `SUCCESS`; verify with `kubectl -n online-boutique get pods`

### K. SHADOW path

```powershell
curl "http://localhost:8000/api/decisions/shadow?limit=5" | ConvertFrom-Json |
  Select -Expand shadows | Select service_id, candidate_action, confidence, verdict
```

Nothing is executed. After the anomaly resolves (or 60 s), the observer fills
`verdict` with `ACTION_WOULD_HAVE_…`.

### L. HUMAN path + approval

```powershell
curl http://localhost:8000/api/decisions/escalations | ConvertFrom-Json |
  Select -Expand escalations | Select id, service_id, status, attempt
```

Then `http://localhost:5173/escalations` → pick it → **Approve & run**:

- status → `RESOLVED`
- panel shows **Action performed** with the execution status
- `/executions` gains a row for that decision

(The Gmail attempt will show `FAILED` until the SMTP app password is fixed —
that does not block the approval.)

### M. Guardrail veto

Re-inject the same fault on the same service within 180 s. The new decision
should be `BLOCK` with `policy.reason` starting `guardrail blocked:`. That is
the cooldown doing its job — the demo-able safety property.

### N. Reset for the next run

```powershell
curl -X POST http://localhost:8002/api/demo/reset
```

Stops the chaos experiments and clears Component 1's fleet state.

---

## 5. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `/api/graph/source` says `seed` | C2 booted before C1, or C1 is old code | restart C1, then `POST /api/graph/refresh` |
| `/api/topology` → 404 | C1 running pre-change code | restart C1 |
| No anomalies after a fault | C1 not in `prometheus` mode, or score < 0.5 | `TELEMETRY_MODE=prometheus`; check `/api/services` score rising |
| Decisions say `NO_RULE_MATCHED` | generic rules not seeded (old DB + no restart) | restart C2; confirm `/api/rules` lists `generic_*` |
| `component1` is `null` on decisions | decision made before the integration | only new decisions carry it |
| Execution `NOT_IMPLEMENTED` | dry run | `run-live.ps1 -Live` |
| Execution `FAILED: 403` | RBAC | apply the Role/RoleBinding from the report; check `KUBERNETES_NAMESPACE=online-boutique` |
| Emails all `FAILED` | Gmail app password | regenerate the 16-char app password; set `SMTP_FROM` = `SMTP_USER` |
