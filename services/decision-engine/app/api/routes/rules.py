"""
Rule REST API.

    GET    /api/rules                 list all rules
    GET    /api/rules/{rule_id}       get one rule
    POST   /api/rules                 create or replace a rule
    DELETE /api/rules/{rule_id}       delete a rule
    POST   /api/rules/reload          hot-reload from DB
    GET    /api/rules/meta/stats      registry metadata
"""
from fastapi import APIRouter, HTTPException, status

from app.rules.models import Rule
from app.rules.registry import rule_registry
from app.rules.repository import rule_repository

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("")
async def list_rules():
    """Return every rule (enabled + disabled), sorted by priority."""
    rules = await rule_repository.list_all(enabled_only=False)
    return {
        "count": len(rules),
        "rules": [r.model_dump(mode="json") for r in rules],
    }


@router.get("/meta/stats")
async def registry_stats():
    """Registry metadata — useful for the frontend + demos."""
    return {
        "in_memory_count": rule_registry.count(),
        "last_loaded_at": rule_registry.last_loaded_at.isoformat()
                          if rule_registry.last_loaded_at else None,
    }


@router.get("/{rule_id}")
async def get_rule(rule_id: str):
    rule = await rule_repository.get(rule_id)
    if not rule:
        raise HTTPException(404, f"rule {rule_id} not found")
    return rule.model_dump(mode="json")


@router.post("", status_code=status.HTTP_201_CREATED)
async def upsert_rule(rule: Rule):
    """Create or replace a rule by id, then refresh the in-memory registry."""
    await rule_repository.upsert(rule)
    await rule_registry.reload()
    return {"ok": True, "id": rule.id, "version": rule.version}


@router.delete("/{rule_id}")
async def delete_rule(rule_id: str):
    deleted = await rule_repository.delete(rule_id)
    if not deleted:
        raise HTTPException(404, f"rule {rule_id} not found")
    await rule_registry.reload()
    return {"ok": True, "deleted": rule_id}


@router.post("/reload")
async def reload_rules():
    """Re-read rules from Postgres into the in-memory registry."""
    count = await rule_registry.reload()
    return {"ok": True, "loaded": count}