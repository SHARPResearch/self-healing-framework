# self-healing-framework

A closed-loop, autonomous reliability system for Kubernetes-hosted microservices: it ingests
operational telemetry, predicts imminent failures with online streaming ML (`river`
Half-Space Trees + ADWIN drift detection), triggers graduated remediation through a
policy-aware .NET decision engine, and surfaces all activity on a real-time React dashboard.

## Layout

| Path                        | What lives there                                                             |
| --------------------------- | ---------------------------------------------------------------------------- |
| `services/ml-backend/`      | FastAPI telemetry ingestion + streaming ML engine + MLflow client            |
| `services/decision-engine/` | .NET 8 Worker Service — policy evaluation, dependency graph, action dispatch |
| `services/yarp-gateway/`    | YARP reverse proxy — executes traffic-shifting recovery actions              |
| `services/llm-copilot/`     | LangChain RCA + copilot service                                              |
| `services/shared/`          | Cross-service shared code                                                    |
| `services/target-services/` | Sample microservices for chaos-injection demos                               |
| `frontend/`                 | React 18 + Vite + Tailwind observability dashboard                           |
| `ml-pipeline/`              | Standalone HST warm-up + drift-detection research pipeline                   |
| `infrastructure/`           | Helm charts, Kubernetes manifests, Terraform                                 |
| `datasets/`                 | Dataset download/preprocessing scripts (raw data itself is gitignored)       |
| `docs/`                     | Architecture, monorepo structure, execution guide, and per-topic docs        |

## Getting started

See `docs/Doc3_Execution_Guide.md` for the full phased build order (Phase 0 workstation setup
through Phase 9 CI/CD). Short version:

```bash
make dev          # starts local Redis + TimescaleDB via docker-compose
```

Claude Code users: read `CLAUDE.md` first — it indexes which docs are authoritative and which
are still empty scaffolding, plus the `local-dev-stack` and `scaffold-service` skills.

## Docs

- `docs/Doc1_Technical_Architecture.md` — architecture, data flow, ML config, decision policy
- `docs/Doc2_GitHub_Monorepo_Structure.md` — the folder layout this repo follows
- `docs/Doc3_Execution_Guide.md` — chronological build phases
- `docs/Component_1_2_Technical_Guide.md` — the `ml-pipeline/` research prototype walkthrough

## Run everything with one command

```powershell
# dry run: decisions are made, executions recorded as NOT_IMPLEMENTED
powershell -ExecutionPolicy Bypass -File scripts/run-live.ps1

# live: AUTO_EXECUTE really restarts pods in online-boutique
powershell -ExecutionPolicy Bypass -File scripts/run-live.ps1 -Live

## if this is not work - use this
pwsh -ExecutionPolicy Bypass -File scripts/run-live.ps1 -Live

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
