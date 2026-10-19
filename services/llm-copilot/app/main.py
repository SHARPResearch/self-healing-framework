"""
LLM-Driven Observability Copilot & Automated Post-Mortem Engine
Main FastAPI Application Entry Point.

Component 5 of the Self-Healing AI-Driven Failure Prediction Framework.
Owner: Rukshan E A Y (IT23263512)
"""

from app.api.routes import chat

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys

from app.core.config import settings
from app.api.routes import health, security, postmortem, webhooks

# Configure logging
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")

# FastAPI App 
app = FastAPI(
    title="LLM-Driven Observability Copilot & Post-Mortem Engine",
    description="""
    ## Component 5 — Multi-Agent LLM System
    
    This component provides:
    - **Security Agent**: Systemic masking guardrails (PII scrubbing)
    - **Reporting Agent**: Automated Markdown post-mortem generation
    - **RCA Agent**: Root Cause Analysis
    - **Conversational Agent**: RAG-based natural language querying (coming in PP2)
    
    ### PP1 Functions
    1. **Function 1**: `/api/security/mask` — Zero-leakage PII scrubbing
    2. **Function 2**: `/api/postmortem/generate` — Automated post-mortem reports
    """,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers 
app.include_router(health.router)
app.include_router(security.router)
app.include_router(postmortem.router)
app.include_router(webhooks.router)
app.include_router(chat.router)


# Lifecycle Events 
@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting LLM Copilot on {settings.api_host}:{settings.api_port}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Component 2 URL: {settings.component2_base_url}")
    logger.info(f"Masking Enabled: {settings.masking_enabled}")


@app.on_event("shutdown")
async def shutdown_event():
    from app.services.decision_engine_client import decision_engine_client
    await decision_engine_client.close()
    logger.info("LLM Copilot shutdown complete")


# Root Endpoint 
@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "LLM-Driven Observability Copilot",
        "component": "Component 5",
        "owner": "Rukshan E A Y (IT23263512)",
        "version": "0.1.0",
        "docs": "/docs",
        "pp1_functions": [
            "POST /api/security/mask — Function 1: Systemic Masking Guardrail",
            "POST /api/postmortem/generate — Function 2: Automated Post-Mortem Generator",
        ],
    }

# Agent registry 
@app.get("/api/agents", tags=[" Agent Registry"])
async def list_agents():
    """List all registered agents."""
    from app.agents.orchestrator.agent_registry import agent_registry
    return {
        "agents": agent_registry.list_agents(),
        "total": len(agent_registry.list_agents())
    }