# Document 2: GitHub Repository Structure
## Production-Ready Monorepo Architecture

---

## Repository: `self-healing-framework`

```
self-healing-framework/
│
├── .github/
│   ├── workflows/
│   │   ├── ci-ml-backend.yml          # FastAPI lint, test, Docker build
│   │   ├── ci-dotnet-engine.yml       # .NET build, unit test, Docker build
│   │   ├── ci-frontend.yml            # Vite build, Jest, Playwright E2E
│   │   ├── ci-k8s-manifests.yml       # kubeval + helm lint
│   │   └── cd-deploy-staging.yml      # ArgoCD sync trigger on main merge
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── CODEOWNERS
│
├── .vscode/
│   └── extensions.json                # Recommended: Pylance, C# Dev Kit, ESLint
│
├── docs/
│   ├── Doc1_Technical_Architecture.md
│   ├── Doc2_GitHub_Monorepo_Structure.md
│   ├── Doc3_Execution_Guide.md
│   ├── Doc4_Claude_Agent_Prompts.md
│   ├── adr/                           # Architecture Decision Records
│   │   ├── 001-river-over-sklearn.md
│   │   ├── 002-redis-streams-over-kafka.md
│   │   └── 003-yarp-for-traffic-control.md
│   └── diagrams/
│       └── architecture_v2.svg
│
├── datasets/
│   ├── README.md                      # Download instructions for SMD + NAB
│   ├── smd/
│   │   ├── download.sh                # Clones OmniAnomaly repo, extracts CSVs
│   │   ├── preprocess.py              # Normalises SMD to standard feature schema
│   │   └── .gitignore                 # Ignores raw CSV files (>100MB)
│   ├── nab/
│   │   ├── download.sh
│   │   ├── preprocess.py
│   │   └── .gitignore
│   └── schemas/
│       └── feature_vector.json        # Canonical feature schema used across services
│
├── services/
│   │
│   ├── ml-backend/                    # FastAPI ML Inference + Ingestion Service
│   │   ├── Dockerfile
│   │   ├── pyproject.toml             # uv/poetry project file
│   │   ├── requirements.txt
│   │   ├── .env.example
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                # FastAPI app factory + lifespan
│   │   │   ├── config.py              # Pydantic Settings
│   │   │   ├── api/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── routes/
│   │   │   │   │   ├── ingest.py      # POST /ingest/metrics
│   │   │   │   │   ├── predict.py     # GET /predict/{service_id}
│   │   │   │   │   ├── models.py      # GET/POST /models — MLflow model mgmt
│   │   │   │   │   └── health.py      # GET /health, GET /ready
│   │   │   │   └── websocket.py       # WebSocket event gateway /ws/events
│   │   │   ├── core/
│   │   │   │   ├── feature_extractor.py    # PromQL response → feature dict
│   │   │   │   ├── ring_buffer.py          # Thread-safe sliding window store
│   │   │   │   └── redis_client.py         # Redis Streams producer/consumer
│   │   │   ├── ml/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── hst_model.py            # HalfSpaceTrees wrapper + per-service registry
│   │   │   │   ├── adwin_detector.py       # ADWIN drift detector wrapper
│   │   │   │   ├── model_manager.py        # MLflow integration: log, load, rollback
│   │   │   │   ├── trainer.py              # SMD/NAB offline warm-up training script
│   │   │   │   └── evaluator.py            # NAB scorer + precision/recall metrics
│   │   │   ├── schemas/
│   │   │   │   ├── metrics.py              # Pydantic: MetricPayload, FeatureVector
│   │   │   │   ├── prediction.py           # AnomalyScore, DriftAlert
│   │   │   │   └── events.py               # AnomalyEvent, ActionReceipt (Redis)
│   │   │   └── services/
│   │   │       ├── ingestion_service.py    # Orchestrates ingest → feature → score
│   │   │       └── event_publisher.py      # Publishes to Redis Streams
│   │   └── tests/
│   │       ├── conftest.py
│   │       ├── unit/
│   │       │   ├── test_hst_model.py
│   │       │   ├── test_adwin_detector.py
│   │       │   ├── test_feature_extractor.py
│   │       │   └── test_model_manager.py
│   │       └── integration/
│   │           ├── test_ingest_endpoint.py
│   │           └── test_websocket_gateway.py
│   │
│   ├── decision-engine/               # .NET 8 Worker Service
│   │   ├── Dockerfile
│   │   ├── DecisionEngine.sln
│   │   ├── src/
│   │   │   └── DecisionEngine/
│   │   │       ├── DecisionEngine.csproj
│   │   │       ├── Program.cs             # Worker host builder
│   │   │       ├── appsettings.json
│   │   │       ├── appsettings.Development.json
│   │   │       ├── Workers/
│   │   │       │   ├── AnomalyConsumerWorker.cs   # Reads Redis Streams
│   │   │       │   └── HealthCheckWorker.cs        # Periodic dependency graph refresh
│   │   │       ├── Engine/
│   │   │       │   ├── PolicyEvaluator.cs          # Threshold + rule evaluation
│   │   │       │   ├── DependencyGraph.cs          # DAG of service dependencies
│   │   │       │   ├── ActionDispatcher.cs         # Selects and dispatches actions
│   │   │       │   └── RuleDefinitions/
│   │   │       │       ├── WatchRule.cs
│   │   │       │       ├── WarnRule.cs
│   │   │       │       ├── DegradeRule.cs
│   │   │       │       └── CriticalRule.cs
│   │   │       ├── Executors/
│   │   │       │   ├── IActionExecutor.cs
│   │   │       │   ├── YarpTrafficShifter.cs       # Patches YARP cluster weights
│   │   │       │   ├── KubernetesExecutor.cs       # Scale / restart / rollout undo
│   │   │       │   └── MlflowRollbackExecutor.cs  # Calls FastAPI /models/rollback
│   │   │       ├── Models/
│   │   │       │   ├── AnomalyEvent.cs
│   │   │       │   ├── ActionReceipt.cs
│   │   │       │   ├── ServiceNode.cs
│   │   │       │   └── RemediationAction.cs
│   │   │       └── Infrastructure/
│   │   │           ├── RedisStreamConsumer.cs
│   │   │           ├── ConsulServiceRegistry.cs
│   │   │           └── KubernetesClientFactory.cs
│   │   └── tests/
│   │       └── DecisionEngine.Tests/
│   │           ├── DecisionEngine.Tests.csproj
│   │           ├── Engine/
│   │           │   ├── PolicyEvaluatorTests.cs
│   │           │   ├── DependencyGraphTests.cs
│   │           │   └── ActionDispatcherTests.cs
│   │           └── Executors/
│   │               └── YarpTrafficShifterTests.cs
│   │
│   ├── yarp-gateway/                  # YARP Reverse Proxy (.NET 8)
│   │   ├── Dockerfile
│   │   ├── YarpGateway.sln
│   │   ├── src/
│   │   │   └── YarpGateway/
│   │   │       ├── YarpGateway.csproj
│   │   │       ├── Program.cs
│   │   │       ├── appsettings.json   # YARP routes + clusters (initial config)
│   │   │       ├── Configuration/
│   │   │       │   └── DynamicRouteProvider.cs    # IReverseProxyBuilder extension
│   │   │       └── Controllers/
│   │   │           └── AdminController.cs         # Internal API for weight patches
│   │   └── tests/
│   │       └── YarpGateway.Tests/
│   │           └── AdminControllerTests.cs
│   │
│   ├── llm-copilot/                   # LangChain RCA + Copilot Service (Python)
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── rag/
│   │   │   │   ├── indexer.py         # Indexes telemetry events into FAISS
│   │   │   │   ├── retriever.py       # Semantic search over telemetry vectors
│   │   │   │   └── prompts.py         # RCA, post-mortem, NL query prompt templates
│   │   │   ├── chains/
│   │   │   │   ├── rca_chain.py       # Root cause analysis chain
│   │   │   │   ├── postmortem_chain.py
│   │   │   │   └── copilot_chain.py   # Conversational copilot
│   │   │   └── api/
│   │   │       ├── chat.py            # POST /chat — streaming NL responses
│   │   │       └── postmortem.py      # GET /postmortem/{incident_id}
│   │   └── tests/
│   │       └── test_rag_retriever.py
│   │
│   └── target-services/               # Sample microservices for demo/testing
│       ├── service-a-auth/            # Node.js Express (target for chaos injection)
│       │   ├── Dockerfile
│       │   ├── package.json
│       │   └── src/index.js
│       ├── service-b-orders/          # Python FastAPI (intentionally leaky memory)
│       │   ├── Dockerfile
│       │   └── app/main.py
│       └── service-c-inventory/       # Go HTTP server
│           ├── Dockerfile
│           └── main.go
│
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf                     # Production static file serving
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── public/
│   │   └── favicon.svg
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── index.css
│       ├── components/
│       │   ├── layout/
│       │   │   ├── Sidebar.tsx
│       │   │   ├── Header.tsx
│       │   │   └── Layout.tsx
│       │   ├── dashboard/
│       │   │   ├── ServiceHealthGrid.tsx      # Status tiles per service
│       │   │   ├── AnomalyScoreChart.tsx      # Recharts real-time line chart
│       │   │   ├── IncidentFeed.tsx           # Live action log
│       │   │   ├── DependencyGraph.tsx        # D3.js force-directed graph
│       │   │   └── DriftAlertBanner.tsx       # ADWIN drift notifications
│       │   ├── copilot/
│       │   │   ├── CopilotChatPanel.tsx
│       │   │   ├── ChatMessage.tsx
│       │   │   └── PostMortemCard.tsx
│       │   └── shared/
│       │       ├── Badge.tsx
│       │       ├── ScoreGauge.tsx
│       │       ├── Sparkline.tsx
│       │       └── LoadingSpinner.tsx
│       ├── hooks/
│       │   ├── useWebSocket.ts        # Native WebSocket with auto-reconnect
│       │   ├── useAnomalyStream.ts    # Transforms WS messages → typed events
│       │   └── useServiceGraph.ts     # Manages D3 graph state
│       ├── stores/
│       │   ├── servicesStore.ts       # Zustand store for service states
│       │   ├── incidentsStore.ts
│       │   └── metricsStore.ts
│       ├── api/
│       │   ├── mlBackend.ts           # Axios client for FastAPI REST endpoints
│       │   └── copilot.ts             # Fetch-based streaming for LLM responses
│       ├── types/
│       │   ├── anomaly.ts
│       │   ├── service.ts
│       │   └── incident.ts
│       └── pages/
│           ├── Dashboard.tsx
│           ├── Incidents.tsx
│           ├── Models.tsx             # MLflow model versions view
│           └── Copilot.tsx
│
├── ml-pipeline/
│   ├── README.md
│   ├── notebooks/
│   │   ├── 01_smd_exploration.ipynb       # SMD data analysis + HST warm-up
│   │   ├── 02_nab_benchmarking.ipynb      # NAB scorer vs HST predictions
│   │   ├── 03_feature_engineering.ipynb   # Feature selection experiments
│   │   └── 04_drift_simulation.ipynb      # ADWIN sensitivity analysis
│   ├── scripts/
│   │   ├── download_datasets.sh
│   │   ├── warm_up_hst.py             # Pre-trains HST on SMD; saves to MLflow
│   │   ├── run_nab_benchmark.py       # Computes NAB score for trained model
│   │   ├── simulate_drift.py          # Injects distribution shift to test ADWIN
│   │   └── export_model.py            # Exports production model from MLflow
│   └── configs/
│       ├── hst_hyperparams.yaml       # n_trees, height, window_size per service
│       └── adwin_config.yaml
│
├── infrastructure/
│   ├── README.md
│   │
│   ├── helm/
│   │   └── self-healing-framework/
│   │       ├── Chart.yaml
│   │       ├── values.yaml            # Default values
│   │       ├── values.staging.yaml
│   │       ├── values.production.yaml
│   │       └── templates/
│   │           ├── ml-backend/
│   │           │   ├── deployment.yaml
│   │           │   ├── service.yaml
│   │           │   ├── configmap.yaml
│   │           │   └── hpa.yaml
│   │           ├── decision-engine/
│   │           │   ├── deployment.yaml
│   │           │   ├── service.yaml
│   │           │   └── rbac.yaml      # ServiceAccount + ClusterRole
│   │           ├── yarp-gateway/
│   │           │   ├── deployment.yaml
│   │           │   ├── service.yaml   # LoadBalancer type
│   │           │   └── ingress.yaml
│   │           ├── redis/
│   │           │   ├── statefulset.yaml
│   │           │   ├── service.yaml
│   │           │   └── pvc.yaml
│   │           ├── mlflow/
│   │           │   ├── deployment.yaml
│   │           │   ├── service.yaml
│   │           │   └── minio-statefulset.yaml
│   │           ├── monitoring/
│   │           │   ├── prometheus-values.yaml   # kube-prometheus-stack overrides
│   │           │   └── grafana-dashboards/
│   │           │       ├── selfheal-overview.json
│   │           │       └── hst-model-metrics.json
│   │           └── chaos-mesh/
│   │               ├── network-delay.yaml       # Example chaos experiments
│   │               ├── pod-kill.yaml
│   │               └── memory-stress.yaml
│   │
│   ├── kubernetes/
│   │   ├── namespaces.yaml
│   │   ├── rbac/
│   │   │   ├── decision-engine-sa.yaml
│   │   │   └── cluster-role-binding.yaml
│   │   └── network-policies/
│   │       ├── deny-all-default.yaml
│   │       └── allow-selfheal-system.yaml
│   │
│   └── terraform/                     # Optional: provision EKS/GKE cluster
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
│
├── scripts/
│   ├── dev-setup.sh                   # One-shot local dev bootstrap
│   ├── start-minikube.sh              # Minikube with required addons
│   ├── port-forward-all.sh            # Forward all services for local dev
│   ├── seed-demo-data.py              # Push sample anomaly events to Redis
│   └── run-chaos-experiment.sh        # Triggers Chaos Mesh fault + observes
│
├── docker-compose.yml                 # Full local stack (all services + Redis + MLflow)
├── docker-compose.override.yml        # Dev overrides (hot-reload volumes)
├── .env.example
├── .gitignore
├── .editorconfig
├── .pre-commit-config.yaml            # ruff, black, eslint, dotnet-format
├── Makefile                           # make dev, make test, make deploy-staging
└── README.md
```

---

## Key File Annotations

### `services/ml-backend/app/ml/hst_model.py`
Central class: `HSTModelRegistry` — a dictionary of `{service_id: HalfSpaceTrees}` instances, each with its own ADWIN detector and MLflow run. Thread-safe via `asyncio.Lock`.

### `services/decision-engine/src/Engine/DependencyGraph.cs`
Populated at startup from Consul; refreshed every 60s. Exposed as `IReadOnlyDependencyGraph` for testability. Uses `Microsoft.Extensions.Caching.Memory` for O(1) neighbour lookup.

### `services/yarp-gateway/src/Configuration/DynamicRouteProvider.cs`
Implements `IProxyConfigProvider`. Exposes an `InMemoryConfigProvider` that the Decision Engine patches via the internal `AdminController`. No file I/O — all in-memory, zero-downtime config updates.

### `frontend/src/hooks/useWebSocket.ts`
Exponential backoff reconnect (1s → 2s → 4s → max 30s). Parses `MessageEvent.data` as JSON, dispatches typed events to Zustand stores. Handles connection-state-driven UI (connecting/connected/disconnected badges).

### `infrastructure/helm/self-healing-framework/values.yaml`
Single source of truth for image tags, resource limits, replica counts, and environment variable injection. CI/CD pipeline substitutes `image.tag` via `helm upgrade --set image.tag=$GIT_SHA`.

### `Makefile` — Key targets
```makefile
make dev          # docker-compose up --build
make test-ml      # pytest services/ml-backend/tests
make test-dotnet  # dotnet test services/decision-engine
make test-fe      # pnpm test (Jest + Playwright)
make deploy-stg   # helm upgrade self-healing-framework ./infrastructure/helm/...
make chaos-run    # runs 3-minute chaos experiment and logs recovery timeline
```
