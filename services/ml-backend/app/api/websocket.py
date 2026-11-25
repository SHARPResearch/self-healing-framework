"""
websocket.py — GET /ws/events: the live event stream for the dashboard (Doc1 §3.3).

With AUTH_MODE=jwt the client's first message must be {"type": "auth", "token": <JWT>} (browsers
cannot set an Authorization header on a WebSocket, and a token in the URL would end up in access
logs). Nothing is sent before it verifies; a bad or missing token closes the socket with 4401.
The stream is the caller's tenant only (docs/adr/0015).

Then the client receives one `snapshot` message (current services and open operator queries),
then every bus message: anomaly_score, quarantine_opened, change_observed, lifecycle_decision,
operator_query, query_answered, query_expired, model_transition, demo_injection.
Envelope: {type, service_id, ts, data}.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.api import views
from app.auth import ANONYMOUS_OWNER, Principal, TokenError, verify_token
from app.bus import envelope
from app.config import settings
from app.tenancy import tenants

logger = logging.getLogger(__name__)
router = APIRouter()

AUTH_TIMEOUT_S = 10
UNAUTHORIZED = 4401        # WebSocket close codes 4000-4999 are the application's
NO_FLEET = 4404


async def _authenticate(ws: WebSocket) -> Principal:
    if settings.auth_mode != "jwt":
        return ANONYMOUS_OWNER
    raw = await asyncio.wait_for(ws.receive_text(), timeout=AUTH_TIMEOUT_S)
    msg = json.loads(raw)
    if msg.get("type") != "auth" or not msg.get("token"):
        raise TokenError("first message must be {type: auth, token}")
    return verify_token(msg["token"])


@router.websocket("/ws/events")
async def events(ws: WebSocket) -> None:
    await ws.accept()
    try:
        p = await _authenticate(ws)
        runtime = await tenants.get(p.tenant)
    except (TokenError, asyncio.TimeoutError, json.JSONDecodeError, KeyError) as exc:
        await ws.close(code=UNAUTHORIZED, reason=str(exc)[:120])
        return
    except HTTPException as exc:
        await ws.close(code=NO_FLEET, reason=str(exc.detail)[:120])
        return
    except WebSocketDisconnect:
        return
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
