# Decision Engine — Mermaid diagrams

Renders in GitHub, VS Code Markdown Preview, or <https://mermaid.live>.
The full implementation diagram is [`decision-engine-full.mmd`](decision-engine-full.mmd);
this file holds the focused views used in the report.

| # | Diagram | Use |
|---|---|---|
| 1 | Live incident sequence | shows the C1 → C2 handoff end to end |
| 2 | Decision pipeline | the seven stages, one line each |
| 3 | Outcome tree | the policy matrix as a decision tree |
| 4 | Escalation state machine | PENDING → AWAITING_HUMAN → RESOLVED / MANUAL_REQUIRED |
| 5 | Component deployment | ports, processes, datastores |

---

## 1. Live incident sequence

```mermaid
sequenceDiagram
    autonumber
    participant OP as Operator
    participant C1 as Component 1<br/>ml-backend :8002
    participant K8S as Kubernetes<br/>Online Boutique
    participant PROM as Prometheus :9090
    participant C2 as Component 2<br/>decision-engine :8000
    participant DB as Postgres + Timescale
    participant UI as Dashboard :5173

    OP->>C1: POST /api/live/frontend/cpu_stress
    C1->>K8S: Chaos Mesh experiment
    K8S-->>PROM: cpu rises on frontend
    loop every scrape
        C1->>PROM: query service features
        C1->>C1: score + drift check
    end
    C2->>C1: GET /api/services (every 5 s)
    C1-->>C2: frontend status=critical score=0.91
    C2->>C2: unhealthy, no open incident
    C2->>DB: INSERT anomaly_events (ANM-frontend-...)
    C2->>DB: capture evidence window (infra + app snapshots)
    C2->>C1: GET /api/topology (every 60 s)
    C1-->>C2: Online Boutique call graph
    C2->>C2: context: telemetry + graph + centrality + blast radius
    C2->>C2: classify, rules, severity, action
    C2->>C2: validate: confidence, risk, conflict
    alt AUTO_EXECUTE
        C2->>C2: guardrails pass
        C2->>K8S: restart pod (namespace online-boutique)
        K8S-->>C2: ExecutionResult
    else SHADOW_MODE
        C2->>DB: shadow_records counterfactual
    else HUMAN_LOOP
        C2->>DB: escalations row
        C2->>OP: email attempt 1 / 2 / 3
        OP->>C2: POST /ack APPROVED
        C2->>K8S: run executor for the decision
    else BLOCK
        C2->>DB: decision_log only
    end
    C2->>DB: decision_log + execution_log + notifications
    UI->>C2: poll decisions, escalations, executions
    C2-->>UI: run graph, timings, notifications
```

---

## 2. Decision pipeline

```mermaid
flowchart LR
    A["Anomaly<br/>from C1"] --> B["Context<br/>telemetry + graph"]
    B --> C["Classify<br/>isolated / upstream<br/>cascading"]
    C --> D["Rules<br/>candidates"]
    D --> E["Severity<br/>base × centrality × blast"]
    E --> F["Action<br/>select + blast risk"]
    F --> G{"Validation<br/>confidence, risk,<br/>conflict"}
    G -->|"conf ≥ 0.85<br/>risk LOW"| H{"Guardrails<br/>cooldown, counter,<br/>idempotency"}
    G -->|"0.60 – 0.85"| I["SHADOW<br/>counterfactual"]
    G -->|"risk HIGH or<br/>repeat ≥ 2"| J["HUMAN<br/>escalation"]
    G -->|"conf < 0.60<br/>or conflict"| K["BLOCK"]
    H -->|"pass"| L["Execute<br/>K8s / YARP"]
    H -->|"veto"| K
    L --> M["execution_log"]
    I --> N["shadow_records"]
    J --> O["escalations"]
    O -->|"APPROVED"| L
    K --> P["decision_log only"]
```

---

## 3. Outcome tree (policy matrix)

```mermaid
flowchart TD
    S{"Conflict<br/>in-flight, neighbour,<br/>or repeat failure?"}
    S -->|"yes"| BLOCK1["BLOCK<br/>dependency conflict"]
    S -->|"no"| R{"Risk band"}
    R -->|"HIGH"| HUMAN["HUMAN_LOOP<br/>operator approval"]
    R -->|"LOW or MEDIUM"| C{"Effective confidence"}
    C -->|"< 0.60"| BLOCK2["BLOCK<br/>low confidence"]
    C -->|"0.60 – 0.844"| SHADOW["SHADOW_MODE<br/>simulate only"]
    C -->|"≥ 0.85 and risk LOW"| GUARD{"Guardrails"}
    C -->|"≥ 0.85 but risk MEDIUM"| SHADOW
    GUARD -->|"pass"| AUTO["AUTO_EXECUTE"]
    GUARD -->|"veto"| BLOCK3["BLOCK<br/>guardrail"]
```

---

## 4. Escalation state machine

```mermaid
stateDiagram-v2
    [*] --> PENDING : HUMAN_LOOP decision
    PENDING --> AWAITING_HUMAN : attempt 1 sent
    AWAITING_HUMAN --> AWAITING_HUMAN : attempt 2 sent (reminder, T+5m)
    AWAITING_HUMAN --> MANUAL_REQUIRED : attempt 3 sent (final, T+15m)
    AWAITING_HUMAN --> RESOLVED : operator acks APPROVED
    AWAITING_HUMAN --> RESOLVED : operator acks REJECTED
    PENDING --> RESOLVED : operator acks before first send
    RESOLVED --> [*] : APPROVED ran the executor
    MANUAL_REQUIRED --> [*]
```

---

## 5. Deployment view

```mermaid
flowchart LR
    subgraph HOST["Developer machine"]
        subgraph K8S["minikube profile 'sharp'"]
            OB["Online Boutique<br/>namespace: online-boutique<br/>12 deployments"]
            MON["monitoring<br/>Prometheus + Grafana"]
            CHAOS["Chaos Mesh"]
        end
        subgraph PROC["processes"]
            C1["ml-backend<br/>:8002<br/>TELEMETRY_MODE=prometheus"]
            C2["decision-engine<br/>:8000"]
            WEB["frontend<br/>:5173"]
        end
        DB[("Postgres<br/>anomalies, decisions,<br/>escalations, executions")]
        TS[("TimescaleDB<br/>infra + app snapshots")]
    end

    OB --> MON
    MON --> C1
    CHAOS --> OB
    C1 -->|"/api/services, /api/topology"| C2
    C2 --> DB
    C2 --> TS
    C2 -->|"restart / scale"| OB
    WEB --> C2
    C2 -->|"SMTP"| MAIL["Gmail"]
```

---

## 6. Where each diagram comes from in code

| Diagram element | Source |
|---|---|
| anomaly creation, dedupe, capture window | `app/ingestion/anomaly_sink.py` |
| topology load + 60 s refresh | `app/integration/topology.py` |
| catalog (local ∪ graph) | `app/integration/catalog.py` |
| telemetry + provenance | `app/integration/telemetry.py`, `build_telemetry` |
| classify / rules / severity / action | `app/rules/`, `app/decision/{severity,action_selector,blast_analysis}.py` |
| validation + policy matrix | `app/decision/validation/{confidence,risk_classifier,conflict_detector,policy_matrix}.py` |
| guardrails | `app/decision/guardrails/{cooldown,action_counter,idempotency}.py` |
| escalation + approval execution | `app/decision/escalation/{queue,worker,approval}.py` |
| execution | `app/decision/executor_kubernetes.py` |
| timings + C1 provenance | `app/decision/job.py` |
| dashboard rendering | `frontend/src/features/decisions/` |
