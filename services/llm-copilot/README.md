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