"""
main.py — FastAPI app for the ml-backend (Doc1 §2: Telemetry Ingestion API, Streaming ML Engine,
Model Registry client).

Run:  uv run uvicorn app.main:app --port 8002
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app import metrics
from app.api import routes, websocket
from app.config import settings
from app.tenancy import tenants

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await tenants.start(backing_services=settings.use_backing_services, replay=settings.start_replay)
    yield
    await tenants.stop()


app = FastAPI(title="self-healing ml-backend", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(routes.router)
app.include_router(websocket.router)


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> Response:
    """Prometheus exposition of app/metrics.py, scraped by the ServiceMonitor in the Helm chart."""
    return Response(metrics.render(), media_type=metrics.CONTENT_TYPE_LATEST)
