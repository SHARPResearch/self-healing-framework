# self-healing-framework

A closed-loop, autonomous reliability system for Kubernetes-hosted microservices: it ingests
operational telemetry, predicts imminent failures with online streaming ML, triggers graduated
remediation through a policy-aware decision engine, and surfaces all activity on a real-time
dashboard.

## Source of truth

- `docs/Doc1_Technical_Architecture.md` — the architecture: components, data flow, ML config,
  decision policy, security. Read this first for *why* things are shaped the way they are.
- `docs/Doc2_GitHub_Monorepo_Structure.md` — the folder layout this repo follows (see below).
- `docs/Doc3_Execution_Guide.md` — chronological build phases (Phase 0 workstation setup through
  Phase 9 CI/CD). Each phase lists manual tasks before coding tasks; don't start phase N+1 before
  phase N's verification passes.
- `docs/Component_1_2_Technical_Guide.md` — the standalone HST anomaly-detection + drift-detection
  research prototype (now at `ml-pipeline/`), written to be lifted into `services/ml-backend` later.
- The other files under `docs/` (`CodingStandards.md`, `Services.md`, `Architecture.md`, `API.md`,
  `Database.md`, `Deployment.md`, `DevelopmentGuide.md`, `ResearchMapping.md`) are still empty
  section-header scaffolding — not yet authoritative. Don't treat them as settled decisions.

## Core design principles (Doc1 §1)

- **Online learning first** — no batch retrain cycles; `river` processes every scrape as a stream
  event.
- **Language-native strengths** — Python/FastAPI owns ML inference, C#/.NET owns stateful
  orchestration and policy enforcement, React owns observability UX.
- **Kubernetes-native recovery** — remediation is always a Kubernetes API call, never a bespoke
  restart script or SSH agent.
- **YARP as the intelligent proxy** — traffic-shifting recovery actions execute through YARP,
  controlled by the .NET Decision Engine's internal admin API.

## Repo layout

| Path | Component (Doc1 §2) | Tech |
|---|---|---|
| `services/ml-backend/` | Telemetry Ingestion API + Streaming ML Engine + Model Registry client | FastAPI, river, MLflow |
| `services/decision-engine/` | Decision Engine (policy evaluation, dependency graph, action dispatch) | .NET 8 Worker Service |
| `services/yarp-gateway/` | Execution Layer (traffic control) | YARP reverse proxy |
| `services/llm-copilot/` | LLM Copilot / RCA Engine | LangChain, RAG |
| `services/shared/` | Cross-service shared code | — |
| `services/target-services/` | Sample microservices for chaos-injection demos | Node/Python/Go |
| `frontend/` | Observability Dashboard | React 18, Vite, Tailwind |
| `ml-pipeline/` | Standalone HST warm-up + drift-detection research pipeline (Component 1-2). Component 1 (train/evaluate/tune/calibrate) is done — see `ml-pipeline/RESULTS.md`; Component 2 (streaming + drift) is reserved (`src/data_pipeline.py`/`src/mlflow_lifecycle.py` stubs) for a teammate. | Python, river, MLflow |
| `adaptive-pipeline/` | Standalone RL research pipeline (Component 4 — Adaptive Learning Decision Engine). Scaffold only, no code yet, no `.venv` installed yet — see `adaptive-pipeline/CLAUDE.md` for the open state/action/reward design questions that need answering first. | Python, Stable-Baselines3, Gymnasium, MLflow |
| `infrastructure/` | Helm charts, Kubernetes manifests, Terraform | Helm, kubectl, Terraform |
| `datasets/` | SMD/NAB dataset download + preprocessing scripts (not the raw data itself) | — |

Each service/area folder has its own short `CLAUDE.md` with specifics.

## Conventions

- **Commits**: Conventional Commits style already in use in history — `feat:`, `fix:`, `chore:`,
  `refactor:`, `docs:`. Keep them atomic and real; don't pad with no-op commits.
- **Branches**: `feat/...`, `chore/...`, `init/...` — merged into `main` via PR (see closed PR#1,
  PR#2 for the existing pattern).
- **Anomaly severity thresholds** (used consistently across ml-backend and decision-engine):
  `< 0.5` watch, `0.5–0.7` warn, `0.7–0.85` degrade, `> 0.85` critical. `ml-pipeline/RESULTS.md`
  found HST score distributions differ enough per machine that a single global threshold does
  not transfer well across them (mean F1 nearly 5x worse across 28 entities than on the one
  entity it was tuned on) — worth re-checking before assuming these fixed cutoffs generalize
  across real services too. `ml-pipeline/calibrate.py` implements a validated fix (per-entity
  percentile-based threshold calibration instead of one shared absolute cutoff) that
  `services/decision-engine`'s `PolicyEvaluator` should probably adopt the same idea for, not
  just `ml-backend`.

## Local dev

Use the `local-dev-stack` skill to start/stop Redis, TimescaleDB, and MLflow locally, and the
`scaffold-service` skill when adding a new service under `services/`.

CI workflows (`.github/workflows/`) are intentionally not set up yet — they'd fail on every push
until a service has real buildable code and tests (Doc3 Phase 9 covers this).
