"""
Rule REST API — Hybrid Rule Management.

Three levels of user control:

    Level 1  POST /api/rules/{id}/toggle        enable / disable
    Level 2  PATCH /api/rules/{id}              customize (thresholds, priority,
                                                applies_to, guardrails, enabled)
    Level 3  POST /api/rules/custom             create a rule from scratch

Endpoints:

    GET    /api/rules                       list (filters: type, status, enabled)
    GET    /api/rules/templates             list read-only template rules
    GET    /api/rules/meta/stats            registry metadata
    GET    /api/rules/{rule_id}             one rule
    GET    /api/rules/{rule_id}/audit       audit history
    POST   /api/rules                       full upsert (admin-only)
    POST   /api/rules/custom                create custom rule (Level 3)
    POST   /api/rules/{rule_id}/toggle      enable/disable (Level 1)
    POST   /api/rules/{rule_id}/validate    dry-run validation
    PATCH  /api/rules/{rule_id}             partial update (Level 2)
    DELETE /api/rules/{rule_id}             delete custom rule only
    POST   /api/rules/reload                hot-reload from DB

Ownership guards (see docs — "Never allow breaking the system through UI"):
    * default rules cannot be deleted
    * default rules' `then` (action) and `id` are frozen
    * templates can be neither edited nor deleted
    * a PATCH that changes `then` must exist, so the API can 400 rather than
      silently ignore it
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, status

from app.rules.models import (
    CreateCustomRulePayload,
    Rule,
    RuleCustomizationPayload,
    RuleStatus,
)
from app.rules.registry import rule_registry
from app.rules.repository import rule_repository
from app.rules.validation import validate_rule_payload

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rules", tags=["rules"])


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
def _actor(x_actor: str | None) -> str:
    """Actor for the audit trail. Single-admin system for now."""
    return (x_actor or "unknown").strip() or "unknown"


async def _reload_registry() -> int:
    """Reload the in-memory registry. Failure is logged, never fatal —
    the old rules stay in memory so the engine keeps working."""
    try:
        return await rule_registry.reload()
    except Exception:
        log.exception("Rule registry reload failed — keeping previous rules")
        return rule_registry.count()


async def _build_contexts(limit: int = 50) -> list[Any]:
    """
    Build AnomalyContext objects for the most recent anomalies. Used by the
    validate endpoint's "would match N of M" dry-run. Returns [] when the
    DB has nothing yet (the caller degrades gracefully).
    """
    from app.api.routes.mock_data import SERVICES, _app, _infra
    from app.rules.classifier import classify
    from app.rules.context import ContextBuilder
    from app.persistence.postgres import postgres_store

    try:
        anomalies = await postgres_store.list_recent_anomalies(limit=limit)
    except Exception:
        log.exception("validate: could not read recent anomalies")
        return []

    builder = ContextBuilder()
    builder.set_services_catalog(SERVICES)
    contexts = []
    for a in anomalies:
        sid = a.get("service_id")
        try:
            ctx = builder.build(a, infra=_infra(sid), app=_app(sid), recent_anomalies=anomalies)
            classify(ctx)
            contexts.append(ctx)
        except Exception:
            log.exception("validate: context build failed for anomaly %s", a.get("id"))
    return contexts


# ─────────────────────────────────────────────────────────────────────
# LIST / READ  (static paths declared before /{rule_id} so they win)
# ─────────────────────────────────────────────────────────────────────
@router.get("")
async def list_rules(
    type: str | None = Query(
        None,
        description="Filter by rule type: all | default | custom | templates | archived",
    ),
    status_filter: str | None = Query(
        None, alias="status", description="ACTIVE | DRAFT | ARCHIVED",
    ),
    enabled: bool | None = Query(None, description="Only enabled / disabled"),
):
    """Return every rule (templates excluded unless type=templates)."""
    rules = await rule_repository.list_all(enabled_only=False, include_templates=True)

    if type == "templates":
        rules = [r for r in rules if r.is_template]
    elif type == "default":
        rules = [r for r in rules if r.is_default and not r.is_template]
    elif type == "custom":
        rules = [r for r in rules if not r.is_default and not r.is_template]
    elif type == "archived":
        rules = [r for r in rules if r.status == RuleStatus.ARCHIVED]
    # "all" (or None) → everything

    if status_filter:
        target = status_filter.upper()
        rules = [r for r in rules if r.status.value == target]
    if enabled is not None:
        rules = [r for r in rules if r.enabled == enabled]

    return {
        "count": len(rules),
        "rules": [r.model_dump(mode="json") for r in rules],
    }


@router.get("/templates")
async def list_templates():
    """Read-only starting points offered by SHARP."""
    rules = await rule_repository.list_all(include_templates=True)
    templates = [r for r in rules if r.is_template]
    return {
        "count": len(templates),
        "rules": [r.model_dump(mode="json") for r in templates],
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


@router.get("/{rule_id}/audit")
async def get_rule_audit(rule_id: str, limit: int = Query(100, ge=1, le=500)):
    rule = await rule_repository.get(rule_id)
    if not rule:
        raise HTTPException(404, f"rule {rule_id} not found")
    entries = await rule_repository.get_audit_history(rule_id, limit=limit)
    return {"rule_id": rule_id, "count": len(entries), "entries": entries}


# ─────────────────────────────────────────────────────────────────────
# Level 2 — partial update (customize thresholds/priority/etc)
# ─────────────────────────────────────────────────────────────────────
@router.patch("/{rule_id}")
async def patch_rule(
    rule_id: str,
    payload: RuleCustomizationPayload,
    x_actor: str | None = Header(None, alias="X-Actor"),
):
    """
    Partially update a rule.

    Default rules: safe fields are editable; `then` (action) and `id` are
    frozen. Templates: read-only. Custom rules: everything except ownership.
    """
    actor = _actor(x_actor)
    current = await rule_repository.get(rule_id)
    if not current:
        raise HTTPException(404, f"rule {rule_id} not found")

    if current.is_template:
        raise HTTPException(
            403,
            f"Cannot edit template rule {rule_id} — templates are read-only. "
            "Clone it as a custom rule instead.",
        )

    updates = payload.model_dump(exclude_unset=True, mode="json")

    # Guards
    if "id" in updates and updates["id"] != rule_id:
        raise HTTPException(
            403,
            "Cannot change a rule's id — clone it as a custom rule instead",
        )
    updates.pop("id", None)

    if "then" in updates and updates["then"] != current.then.model_dump(mode="json"):
        if current.is_default:
            raise HTTPException(
                400,
                "Cannot change action of default rule",
            )
        if current.created_by in ("system",) and not current.is_default:
            raise HTTPException(
                403,
                "Cannot change the action of a system-owned rule",
            )

    if not updates:
        return {"ok": True, "rule": current.model_dump(mode="json"), "changed": []}

    updated = await rule_repository.patch_rule(rule_id, updates, actor=actor)
    if not updated:
        raise HTTPException(404, f"rule {rule_id} not found")

    await _reload_registry()
    return {
        "ok": True,
        "changed": sorted(updates.keys()),
        "rule": updated.model_dump(mode="json"),
    }


# ─────────────────────────────────────────────────────────────────────
# Level 3 — create a custom rule
# ─────────────────────────────────────────────────────────────────────
@router.post("/custom", status_code=status.HTTP_201_CREATED)
async def create_custom_rule(
    payload: CreateCustomRulePayload,
    x_actor: str | None = Header(None, alias="X-Actor"),
):
    """
    Create a user-owned rule from scratch. `is_default` is forced FALSE and
    `created_by` is forced to the actor. The payload must validate.
    """
    actor = _actor(x_actor)
    existing = await rule_repository.list_ids()

    raw = payload.model_dump(mode="json")
    # Force user ownership — the caller cannot claim SHARP's namespace
    raw["is_default"] = False
    raw["is_template"] = False
    raw["created_by"] = actor if actor != "unknown" else "user"

    result = validate_rule_payload(raw, existing_ids=existing, is_update=False)
    if not result["valid"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Rule validation failed", "errors": result["errors"]},
        )

    rule = Rule.model_validate(raw)
    created = await rule_repository.create_custom_rule(rule, actor=raw["created_by"])
    await _reload_registry()
    return {
        "ok": True,
        "rule": created.model_dump(mode="json"),
        "warnings": result.get("warnings", []),
    }


# ─────────────────────────────────────────────────────────────────────
# Level 1 — enable / disable
# ─────────────────────────────────────────────────────────────────────
@router.post("/{rule_id}/toggle")
async def toggle_rule(
    rule_id: str,
    enabled: bool | None = Query(None, description="Force a value instead of flipping"),
    x_actor: str | None = Header(None, alias="X-Actor"),
):
    """Flip a rule's enabled flag. Works on any rule (including templates)."""
    actor = _actor(x_actor)
    updated = await rule_repository.toggle_rule(rule_id, actor=actor, enabled=enabled)
    if not updated:
        raise HTTPException(404, f"rule {rule_id} not found")

    await _reload_registry()
    return {
        "ok": True,
        "id": rule_id,
        "enabled": updated.enabled,
        "rule": updated.model_dump(mode="json"),
    }


# ─────────────────────────────────────────────────────────────────────
# Dry-run validation
# ─────────────────────────────────────────────────────────────────────
@router.post("/{rule_id}/validate")
async def validate_rule(
    rule_id: str,
    payload: dict[str, Any],
    test: bool = Query(False, description="Also dry-run against recent anomalies"),
):
    """
    Validate a rule payload without saving it. Answers `{"valid": bool,
    "errors": [...]}`. The rule_id in the path is only used to decide
    whether an id collision is an error (editing vs creating).
    """
    existing = await rule_repository.list_ids()
    is_update = rule_id in existing
    if not is_update and rule_id != payload.get("id"):
        # allow validating an arbitrary body against a prospective id
        pass

    result = validate_rule_payload(payload, existing_ids=existing, is_update=is_update)

    if test and result["valid"]:
        contexts = await _build_contexts()
        try:
            from app.rules.validation import count_matches
            result["match_preview"] = count_matches(
                Rule.model_validate(result["rule"]), contexts
            )
        except Exception:
            log.exception("validate: match preview failed")
            result["match_preview"] = {
                "total_anomalies": len(contexts),
                "matched_count": 0,
                "message": "Match preview unavailable",
            }

    return result


# ─────────────────────────────────────────────────────────────────────
# Full upsert (admin-only)
# ─────────────────────────────────────────────────────────────────────
@router.post("", status_code=status.HTTP_201_CREATED)
async def upsert_rule(
    rule: Rule,
    x_actor: str | None = Header(None, alias="X-Actor"),
):
    """
    Create or replace a rule by id, then refresh the in-memory registry.
    Admin path — bypasses the ownership guards by design (used by scripts
    and by SHARP itself when installing default rules).
    """
    actor = _actor(x_actor or "admin")
    await rule_repository.upsert(rule, actor=actor)
    await _reload_registry()
    return {"ok": True, "id": rule.id, "version": rule.version}


# ─────────────────────────────────────────────────────────────────────
# Delete — custom rules only
# ─────────────────────────────────────────────────────────────────────
@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: str,
    x_actor: str | None = Header(None, alias="X-Actor"),
):
    actor = _actor(x_actor)
    current = await rule_repository.get(rule_id)
    if not current:
        raise HTTPException(404, f"rule {rule_id} not found")

    if current.is_default:
        raise HTTPException(403, "Cannot delete default rule")
    if current.is_template:
        raise HTTPException(403, "Cannot delete template rule")

    deleted = await rule_repository.delete_custom_rule(rule_id, actor=actor)
    if not deleted:
        raise HTTPException(404, f"rule {rule_id} not found")

    await _reload_registry()
    return {"ok": True, "deleted": rule_id}


# ─────────────────────────────────────────────────────────────────────
# Hot reload
# ─────────────────────────────────────────────────────────────────────
@router.post("/reload")
async def reload_rules(x_actor: str | None = Header(None, alias="X-Actor")):
    """Re-read rules from Postgres into the in-memory registry."""
    actor = _actor(x_actor)
    count = await rule_registry.reload()
    await rule_repository.log_reload(actor=actor, count=count)
    return {"ok": True, "loaded": count}
