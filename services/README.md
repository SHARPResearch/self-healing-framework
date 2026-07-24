# services

Backend services for the self-healing framework, one per Doc1 §2 component:

| Folder | Component | Tech |
|---|---|---|
| `ml-backend/` | Telemetry Ingestion + Streaming ML Engine + Model Registry client (also where the Component 1/2/4 "anomaly detection", "dynamic model updating", and "adaptive learning" research pieces live, under `app/ml/`) | FastAPI, river, MLflow |
| `decision-engine/` | Rule-based Decision Engine | .NET 8 Worker Service |
| `yarp-gateway/` | Execution layer (traffic control) | YARP |
| `llm-copilot/` | LLM Copilot / RCA Engine | LangChain, RAG |
| `shared/` | Cross-service shared code | — |
| `target-services/` | Sample microservices for chaos-injection demos | Node/Python/Go |

See each folder's `CLAUDE.md` for specifics, and `docs/Doc3_Execution_Guide.md` for build order.
