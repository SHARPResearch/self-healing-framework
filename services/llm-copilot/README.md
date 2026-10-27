# LLM-Driven Observability Copilot & Automated Post-Mortem Engine

## Overview
This component is part of the **Self-Healing AI-Driven Failure Prediction and Automated Recovery Framework for Microservices**. It acts as the semantic translation gateway, bridging the technical complexity of microservice telemetry with cross-functional organizational stakeholders. 

It utilizes a **Multi-Agent System** to:
1. Translate natural language queries into complex telemetry insights (Conversational RAG Agent).
2. Automatically generate structured Root Cause Analysis (RCA) and Post-Mortem reports upon recovery (Reporting Agent).
3. Enforce strict, real-time data privacy by scrubbing PII, internal IPs, and tokens before any data reaches the LLM (Security Agent).

## Progress Presentation 1 (PP1) Scope
To demonstrate 50% completion of this component, this module currently implements and exposes **2 core functions** with strict input/output contracts:

### Function 1: Systemic Masking Guardrail (Security Agent)
- **Purpose**: Ensures zero data leakage by sanitizing raw telemetry before LLM processing.
- **Mandatory Input**: `raw_telemetry_data` (String or JSON containing raw logs, metrics, or chat input).
- **Mandatory Output**: `sanitized_telemetry_data` (String/JSON with PII, internal IPs, and bearer tokens replaced by `[REDACTED]`).

### Function 2: Automated Post-Mortem Generator (Reporting + RCA Agents)
- **Purpose**: Consumes recovery events from Component 2 and generates a professional Markdown incident report.
- **Mandatory Input**: `recovery_event_payload` (JSON/Dict from Component 2 containing: `service_name`, `anomaly_score`, `root_cause`, `actions_taken`, `start_time`, `end_time`).
- **Mandatory Output**: `markdown_report` (A structured, formatted Markdown string containing the Root Cause Analysis, timeline, and resolution steps).

## Multi-Agent Architecture
- **Orchestrator Agent**: Routes incoming requests (user queries vs. system events) to the appropriate specialized agent.
- **Conversational Agent (RAG)**: Translates natural language to PromQL/SQL and retrieves context from the vector store.
- **Reporting Agent**: Listens asynchronously for recovery triggers and orchestrates post-mortem generation.
- **RCA Agent**: Analyzes dependency graphs and telemetry to pinpoint the root cause before report generation.
- **Security Agent**: Applies Named Entity Recognition (NER) and Regex-based masking guardrails.

## Integration with Component 2 (Decision Engine)
This component does not operate in isolation. It integrates with **Component 2 (Context-Aware & Dependency-Driven Rule-Based Decision Engine)** via:
1. **Webhook/API Trigger**: Component 2 sends a `recovery_event_payload` to our `/api/webhooks/recovery` endpoint upon executing or simulating (Shadow Mode) a recovery action.
2. **Data Fetching**: Our backend uses a dedicated client to fetch extended telemetry history from Component 2's database if needed.
3. **Dashboard Sync**: Generated post-mortems and chat insights are pushed to the shared React frontend via REST/WebSocket.

## Tech Stack (100% Free & Open Source)
- **Backend**: Python, FastAPI
- **Agent Orchestration**: LangChain / LlamaIndex
- **Vector Database**: ChromaDB or FAISS (Local)
- **LLM Runtime**: Ollama (Local Llama 3 / Mistral) or Google Gemini API (Free Tier)
- **Security**: Python `re` (Regex), `spaCy` (NER)
- **Database**: PostgreSQL (for storing generated reports and chat history)
- **Frontend**: React, Vite, Tailwind CSS (Shared monorepo)

## Windows
- python -m venv venv
- venv\Scripts\activate

## Download Ollama  for generate postmortem report
- Upgrade ollama 3.2
- Open Command Prompt and type this (ollama pull llama3.2)

## Server Runnig
- uvicorn app.main:app --reload --port 8004
- http://localhost:8004/docs

## POST /api/security/mask

{
  "raw_data": {
    "user": "admin@company.com",
    "server_ip": "192.168.1.100",
    "auth_token": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
  }
}

## POST /api/webhooks/recovery?wait=true

- Add Header: x-webhook-secret = test_secret_123
{
  "decision_id": "dec-2026-10-20-0042",
  "timestamp": "2026-10-20T14:35:00Z",
  "service": "order-svc",
  "triggering_anomaly": {
    "anomaly_score": 0.94,
    "metric": "error_rate",
    "deviation_magnitude": 7.5,
    "detected_at": "2026-10-20T14:23:45Z"
  },
  "dependency_context": {
    "root_cause_service": "database-svc",
    "blast_radius": 3,
    "risk_level": "HIGH",
    "propagation_type": "upstream"
  },
  "rule_matched": "UPSTREAM_DATABASE_FAILOVER",
  "validation_outcome": "AUTO_EXECUTE",
  "confidence_score": 0.91,
  "action_taken": {
    "type": "restart_pod",
    "target": "database-svc",
    "parameters": {"graceful": true}
  },
  "execution_status": "SUCCESS",
  "recovery_time_sec": 18.5,
  "telemetry_snapshot_url": "/api/telemetry-history?decision_id=dec-2026-10-20-0042"
}

## POST /api/chat/ingest

{
  "service": "inventory-svc",
  "metrics": {
    "cpu_usage": {"value": 45, "avg": 30, "max": 55},
    "memory_usage": {"value": 92, "avg": 60, "max": 95},
    "error_rate": {"value": 12.5, "avg": 1.0},
    "latency": {"p50": 150, "p95": 1200, "p99": 3500},
    "db_pool_active": {"value": 98, "max": 100}
  },
  "logs": [
    "2026-10-21 09:10:00 INFO inventory-svc started on 10.0.0.15:8080",
    "2026-10-21 09:15:30 WARNING Memory usage exceeded 85% threshold, GC overhead increasing",
    "2026-10-21 09:18:45 ERROR Failed to acquire database connection from pool for user admin@enterprise.com",
    "2026-10-21 09:19:12 ERROR java.lang.OutOfMemoryError: Java heap space at com.inventory.cache.MemoryStore.put()",
    "2026-10-21 09:20:00 CRITICAL Service inventory-svc unresponsive, health check failed from 192.168.10.5"
  ],
  "time_range": {
    "start": "2026-10-21T09:00:00Z",
    "end": "2026-10-21T09:30:00Z"
  }
}

## For Frontend

- Why did the order service experience high error rates?

## Project Structure
```text
services/llm-copilot/
┣ app/
┃ ┣ api/routes/          # Endpoints: chat, postmortem, rca, webhooks, health
┃ ┣ agents/              # Multi-agent logic (orchestrator, conversational, reporting, rca, security)
┃ ┣ core/                # Config, Pydantic models (events.py for Comp 2 payloads)
┃ ┣ db/                  # PostgreSQL and Vector store connections
┃ ┣ services/            # decision_engine_client.py, llm_client.py
┃ ┗ main.py              # FastAPI entry point
┣ tests/                 # Unit tests for agents (e.g., test_masking.py)
┣ requirements.txt
┣ Dockerfile
┗ README.md


Backend & API (Python)
FastAPI: The main web framework. Used because it is highly performant, supports asynchronous operations (crucial for AI agents), and auto-generates the Swagger UI documentation.
Uvicorn: The ASGI server used to run FastAPI.
Pydantic & Pydantic-Settings: Used for strict data validation (ensuring Component 2 payloads are perfectly formatted) and managing .env configuration.
HTTPX: An async HTTP client used to communicate with Component 2 (Decision Engine) and fetch telemetry data.
SQLAlchemy: The ORM used to connect to the SQLite/PostgreSQL database to persist post-mortem reports.
Loguru: Used for clean, readable, and structured logging during agent execution.
Tenacity: Used to add automatic retry logic when calling the LLM API in case of timeouts.
AI, LLM & RAG (Artificial Intelligence)
Ollama: The local runtime engine used to host and run the LLMs without needing expensive cloud APIs.
Llama 3.2 (via Ollama): The Large Language Model used for generating post-mortem reports and answering chat queries.
Nomic Embed Text (via Ollama): The embedding model used to convert text into vectors for the RAG pipeline.
ChromaDB: The vector database used to store and retrieve telemetry chunks and past post-mortems based on semantic similarity.
Sentence-Transformers: The underlying library used by ChromaDB to compute the vector embeddings locally.

Frontend (React / TypeScript)
React & TypeScript: The core UI library and language for type-safe frontend development.
Vite: The lightning-fast build tool and development server.
React Router DOM: Used for navigating between pages (Dashboard, Copilot, Post-Mortems).
Tailwind CSS: Used for rapid, utility-first styling.
Framer Motion: Used for smooth, professional animations (like the typing dots and chat bubbles).
Lucide React: Used for the clean, modern icons in the UI.
Shadcn/UI: The component library used for buttons, cards, and inputs.

Databases & Storage
ChromaDB (Vector DB): Stores the semantic embeddings of logs and metrics for the RAG retrieval.
SQLite (Relational DB): Stores the final generated Markdown post-mortem reports and evaluation metrics locally.
