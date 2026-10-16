# Fetches data from Component 2

"""
Component 2 Client — Fetches extended telemetry and decision context
from the Decision Engine's API.
"""
import httpx
from typing import Dict, Any, Optional
from loguru import logger

from app.core.config import settings


class DecisionEngineClient:
    """HTTP client for Component 2 (Decision Engine) API."""

    def __init__(self):
        self.base_url = settings.component2_base_url
        self._client = httpx.AsyncClient(timeout=30.0)

    async def get_telemetry_history(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Fetch extended telemetry snapshot for a given decision."""
        try:
            response = await self._client.get(
                f"{self.base_url}/api/telemetry-history",
                params={"decision_id": decision_id},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch telemetry for {decision_id}: {e}")
            return None

    async def get_dependency_graph_context(self, service: str) -> Optional[Dict[str, Any]]:
        """Fetch dependency graph context for a service."""
        try:
            response = await self._client.get(
                f"{self.base_url}/api/graph/context",
                params={"service": service},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch graph context for {service}: {e}")
            return None

    async def health_check(self) -> bool:
        """Check if Component 2 is reachable."""
        try:
            response = await self._client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self._client.aclose()


# Singleton
decision_engine_client = DecisionEngineClient()