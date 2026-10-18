"""
websocket.py — GET /ws/events: the live event stream for the dashboard (Doc1 §3.3).

On connect the client receives one `snapshot` message (current services and open operator
queries), then every bus message: anomaly_score, quarantine_opened, change_observed,
lifecycle_decision, operator_query, query_answered, query_expired, model_transition,
demo_injection. Envelope: {type, service_id, ts, data}.
"""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api import views
from app.bus import envelope
from app.runtime import runtime

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/events")
async def events(ws: WebSocket) -> None:
    await ws.accept()
    await ws.send_json(envelope("snapshot", None, {
        "services": [views.service_health(runtime.fleet, rt) for rt in runtime.fleet.services.values()],
        "queries": views.queries(runtime.fleet, "open"),
    }))
    stream = runtime.bus.subscribe()
    try:
        async for message in stream:
            await ws.send_json(message)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as exc:  # noqa: BLE001
        logger.info("ws: client dropped (%s)", exc)
    finally:
        await stream.aclose()
