# Health check endpoint

"""Health check endpoints."""
from fastapi import APIRouter  # pyright: ignore[reportMissingImports]
from app.services.decision_engine_client import decision_engine_client

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health Check")
async def health_check():
    """Basic health check for this component."""
    return {"status": "ok", "component": "llm-copilot", "version": "0.1.0"}


@router.get("/health/component2", summary="Component 2 Connectivity Check")
async def component2_health():
    """Check if Component 2 (Decision Engine) is reachable."""
    is_healthy = await decision_engine_client.health_check()
    return {
        "component2_reachable": is_healthy,
        "component2_url": decision_engine_client.base_url,
    }