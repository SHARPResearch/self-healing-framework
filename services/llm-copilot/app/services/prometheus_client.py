# Queries Prometheus API

"""
Prometheus Client - Queries Prometheus API for telemetry context.
"""
import httpx
from typing import Dict, Any, Optional
from loguru import logger

from app.core.config import settings

class PrometheusClient:
    """HTTP client for fetching metrics from Prometheus."""

    def __init__(self):
        # In a real setup, this would be the Prometheus URL. 
        # For PP1 testing, we can point it to a mock or leave it as a placeholder.
        self.base_url = getattr(settings, "prometheus_url", "http://localhost:9090")
        self._client = httpx.AsyncClient(timeout=10.0)

    async def query_range(self, query: str, start: str, end: str, step: str = "1m") -> Optional[Dict[str, Any]]:
        """Query Prometheus range data."""
        try:
            response = await self._client.get(
                f"{self.base_url}/api/v1/query_range",
                params={"query": query, "start": start, "end": end, "step": step}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.warning(f"Prometheus query failed (expected in mock env): {e}")
            return None

    async def close(self):
        await self._client.aclose()

# Singleton instance
prometheus_client = PrometheusClient()