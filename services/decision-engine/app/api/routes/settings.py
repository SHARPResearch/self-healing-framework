"""
Runtime engine settings REST API.

    GET    /api/settings            effective values + metadata
    PATCH  /api/settings            partial update (body = {key: value})
    POST   /api/settings/reload     re-read from DB
    GET    /api/settings/audit      change history
    GET    /api/settings/notifications  recent notification log

Premium gating: the actor is resolved from the `X-Actor` header (default
`unknown`). The single hardcoded owner (`PREMIUM_EMAIL`) counts as premium;
everyone else is standard and is blocked from premium-only keys.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, status

from app.core.runtime_settings import runtime_settings
from app.persistence.postgres import postgres_store

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])

# Hardcoded premium owner until real auth lands.
PREMIUM_EMAIL = "dinildulneth123@gmail.com"


def _actor(x_actor: str | None) -> str:
    return (x_actor or "unknown").strip() or "unknown"


def _is_premium(actor: str) -> bool:
    return actor.lower() == PREMIUM_EMAIL.lower()


@router.get("")
async def get_settings():
    """All tunable settings with effective value, source and metadata."""
    items = runtime_settings.get_all()
    groups = sorted({i["group"] for i in items})
    return {"count": len(items), "groups": groups, "settings": items}


@router.patch("")
async def update_settings(
    patch: dict[str, Any],
    x_actor: str | None = Header(None, alias="X-Actor"),
):
    """
    Partially update settings. Body is a flat `{key: value}` map. All values
    are validated up-front (all-or-nothing). Premium-only keys reject with
    403 for non-premium actors.
    """
    actor = _actor(x_actor)
    is_premium = _is_premium(actor)

    # Reject premium keys for standard users with a clear 403 (per-key).
    for key in patch:
        spec = runtime_settings.get_all()
        by_key = {i["key"]: i for i in spec}
        info = by_key.get(key)
        if info is None:
            raise HTTPException(422, f"unknown setting '{key}'")
        if info["premium"] and not is_premium:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"'{key}' is a premium-only setting. "
                f"Upgrade required (current actor: {actor}).",
            )

    try:
        result = await runtime_settings.update(patch, actor=actor, is_premium=is_premium)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return result


@router.post("/reload")
async def reload_settings(x_actor: str | None = Header(None, alias="X-Actor")):
    """Re-read persisted overrides from the DB and re-apply them."""
    loaded = await runtime_settings.reload()
    return {"ok": True, "loaded": loaded, "settings": runtime_settings.get_all()}


@router.get("/audit")
async def settings_audit(limit: int = Query(100, ge=1, le=500)):
    """Change history for all settings, newest first."""
    entries = await postgres_store.list_settings_audit(limit=limit)
    return {"count": len(entries), "entries": entries}


@router.get("/notifications")
async def list_notifications(limit: int = Query(100, ge=1, le=500)):
    """Recent notification (email) log, newest first."""
    entries = await postgres_store.list_notifications(limit=limit)
    return {"count": len(entries), "entries": entries}
