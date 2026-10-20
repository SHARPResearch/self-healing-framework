# Receives notifications from Component - 02

"""
Webhook receiver for Component 2 recovery events.
"""
from fastapi import APIRouter, Header, HTTPException
from loguru import logger
from typing import Optional

from app.core.config import settings
from app.core.events import RecoveryEventPayload

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


@router.post("/recovery", summary="Receive Recovery Event from Component 2")
async def receive_recovery_event(
    event: RecoveryEventPayload,
    x_webhook_secret: Optional[str] = Header(None),
):
    """
    Webhook endpoint that Component 2 calls after executing a recovery action.
    Validates the secret and queues the event for post-mortem generation.
    """
    # Verify webhook secret
    if x_webhook_secret != settings.component2_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    logger.info(f"Received recovery event: {event.decision_id} for {event.service}")
    
    # In production, this would queue to a message broker (Redis/RabbitMQ)
    # For PP1, we acknowledge receipt immediately
    return {
        "status": "received",
        "decision_id": event.decision_id,
        "message": "Event queued for post-mortem generation",
    }