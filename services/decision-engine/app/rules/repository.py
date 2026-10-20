"""
Rule repository — Postgres CRUD for the `rules` table.

Schema (see app/persistence/schemas.py):
    rules(
        id TEXT PRIMARY KEY,
        version INT NOT NULL DEFAULT 1,
        priority INT NOT NULL DEFAULT 100,
        description TEXT NOT NULL DEFAULT '',
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        applies_to JSONB NOT NULL,
        when_condition JSONB NOT NULL,
        then_action JSONB NOT NULL,
        guardrails JSONB NOT NULL,
        tags JSONB NOT NULL DEFAULT '[]',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        -- hybrid rule management (Batch 2)
        is_default BOOLEAN NOT NULL DEFAULT FALSE,
        is_template BOOLEAN NOT NULL DEFAULT FALSE,
        created_by TEXT NOT NULL DEFAULT 'system',
        owner_org_id TEXT,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        parent_rule_id TEXT REFERENCES rules(id) ON DELETE SET NULL
    )

Note: `when` is a reserved word in SQL — the column is named `when_condition`.

Every write method takes an `actor` and appends to `rule_audit` on success.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.persistence.postgres import postgres_store
from app.rules.models import Rule, RuleStatus

log = logging.getLogger(__name__)


def _row_to_rule(row: Any) -> Rule:
    """Convert an asyncpg Record to a Rule model."""
    return Rule.model_validate({
        "id":            row["id"],
        "version":       row["version"],
        "priority":      row["priority"],
        "description":   row["description"] or "",
        "enabled":       row["enabled"],
        "applies_to":    _jsonb(row["applies_to"]),
        "when":          _jsonb(row["when_condition"]),
        "then":          _jsonb(row["then_action"]),
        "guardrails":    _jsonb(row["guardrails"]),
        "tags":          _jsonb(row["tags"]) or [],
        "is_default":    _get(row, "is_default", False),
        "is_template":   _get(row, "is_template", False),
        "created_by":    _get(row, "created_by", "system"),
        "owner_org_id":  _get(row, "owner_org_id", None),
        "status":        _get(row, "status", "ACTIVE"),
        "parent_rule_id": _get(row, "parent_rule_id", None),
        "created_at":    _iso(_get(row, "created_at", None)),
        "updated_at":    _iso(_get(row, "updated_at", None)),
    })


def _jsonb(v: Any) -> Any:
    """asyncpg returns JSONB as str on some versions, dict on others."""
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return v
    if isinstance(v, str):
        return json.loads(v)
    return v


def _get(row: Any, key: str, default: Any = None) -> Any:
    """Safe column read — tolerates a pre-migration DB missing the column."""
    try:
        return row[key]
    except (KeyError, IndexError):
        return default


def _iso(v: Any) -> str | None:
    return v.isoformat() if hasattr(v, "isoformat") else v


def _diff(before: dict | None, after: dict | None) -> dict:
    """
    Minimal before/after diff. Only includes keys whose value changed, so
    the audit log stays readable instead of storing two full rule blobs.
    """
    before = before or {}
    after = after or {}
    changed_from: dict[str, Any] = {}
    changed_to: dict[str, Any] = {}
    for key in set(before) | set(after):
        b = before.get(key)
        a = after.get(key)
        if b != a:
            changed_from[key] = b
            changed_to[key] = a
    return {"before": changed_from, "after": changed_to}


class RuleRepository:
    """All DB access for rules. Caller must ensure postgres_store is connected."""

    async def count(self) -> int:
        async with postgres_store.pool.acquire() as conn:
            return int(await conn.fetchval("SELECT COUNT(*) FROM rules"))

    async def list_all(
        self,
        enabled_only: bool = False,
        include_templates: bool = False,
    ) -> list[Rule]:
        sql = "SELECT * FROM rules"
        clauses = []
        if enabled_only:
            clauses.append("enabled = TRUE")
        if not include_templates:
            clauses.append("is_template = FALSE")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY priority DESC, id ASC"
        async with postgres_store.pool.acquire() as conn:
            rows = await conn.fetch(sql)
        return [_row_to_rule(r) for r in rows]

    async def get(self, rule_id: str) -> Rule | None:
        async with postgres_store.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM rules WHERE id=$1", rule_id)
        return _row_to_rule(row) if row else None

    async def list_ids(self) -> set[str]:
        async with postgres_store.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id FROM rules")
        return {r["id"] for r in rows}

    async def upsert(self, rule: Rule, actor: str = "system") -> None:
        """
        Insert or replace a rule by id. Writes a CREATE or UPDATE audit row.
        Not the endpoint used for user edits — see patch_rule / create_custom_rule.
        """
        before = await self.get(rule.id)
        payload = rule.model_dump(mode="json")
        async with postgres_store.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO rules
                    (id, version, priority, description, enabled,
                     applies_to, when_condition, then_action,
                     guardrails, tags,
                     is_default, is_template, created_by, owner_org_id,
                     status, parent_rule_id, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
                        $11,$12,$13,$14,$15,$16, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    version        = EXCLUDED.version,
                    priority       = EXCLUDED.priority,
                    description    = EXCLUDED.description,
                    enabled        = EXCLUDED.enabled,
                    applies_to     = EXCLUDED.applies_to,
                    when_condition = EXCLUDED.when_condition,
                    then_action    = EXCLUDED.then_action,
                    guardrails     = EXCLUDED.guardrails,
                    tags           = EXCLUDED.tags,
                    is_default     = EXCLUDED.is_default,
                    is_template    = EXCLUDED.is_template,
                    created_by     = EXCLUDED.created_by,
                    owner_org_id   = EXCLUDED.owner_org_id,
                    status         = EXCLUDED.status,
                    parent_rule_id = EXCLUDED.parent_rule_id,
                    updated_at     = NOW()
                """,
                payload["id"],
                payload["version"],
                payload["priority"],
                payload["description"],
                payload["enabled"],
                json.dumps(payload["applies_to"]),
                json.dumps(payload["when"]),
                json.dumps(payload["then"]),
                json.dumps(payload["guardrails"]),
                json.dumps(payload["tags"]),
                payload["is_default"],
                payload["is_template"],
                payload["created_by"],
                payload["owner_org_id"],
                payload["status"],
                payload["parent_rule_id"],
            )
        await postgres_store.save_rule_audit(
            rule.id,
            "UPDATE" if before else "CREATE",
            actor,
            _diff(
                before.model_dump(mode="json") if before else None,
                payload,
            ),
        )

    async def save_rule(self, rule: Rule) -> None:
        """
        Overwrite an existing rule's editable columns WITHOUT an audit row.
        Used internally after a guarded patch/toggle already logged its own
        entry (so the history isn't doubled up).
        """
        payload = rule.model_dump(mode="json")
        async with postgres_store.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE rules SET
                    version        = $2,
                    priority       = $3,
                    description    = $4,
                    enabled        = $5,
                    applies_to     = $6,
                    when_condition = $7,
                    then_action    = $8,
                    guardrails     = $9,
                    tags           = $10,
                    status         = $11,
                    updated_at     = NOW()
                WHERE id = $1
                """,
                payload["id"],
                payload["version"],
                payload["priority"],
                payload["description"],
                payload["enabled"],
                json.dumps(payload["applies_to"]),
                json.dumps(payload["when"]),
                json.dumps(payload["then"]),
                json.dumps(payload["guardrails"]),
                json.dumps(payload["tags"]),
                payload["status"],
            )

    # ── Level 2 — partial customization (guarded at the route layer) ──
    async def patch_rule(
        self,
        rule_id: str,
        updates: dict[str, Any],
        actor: str = "unknown",
    ) -> Rule | None:
        """
        Apply `updates` (a subset of Rule fields, already validated) to an
        existing rule. Returns the updated rule, or None if it doesn't exist.

        The route layer is responsible for the ownership guard — this method
        trusts its caller and deliberately does NOT allow id/ownership changes.
        """
        current = await self.get(rule_id)
        if not current:
            return None

        before = current.model_dump(mode="json")
        forbidden_overwrite = {"id", "version", "is_default", "is_template"}
        patchable = {
            k: v for k, v in updates.items()
            if k in Rule.model_fields and k not in forbidden_overwrite
        }
        merged = current.model_dump(mode="json")
        merged.update(patchable)
        updated = Rule.model_validate(merged)

        await self.save_rule(updated)
        await postgres_store.save_rule_audit(
            rule_id,
            "UPDATE",
            actor,
            _diff(before, updated.model_dump(mode="json")),
        )
        return updated

    # ── Level 1 — enable/disable ─────────────────────────────────
    async def toggle_rule(
        self,
        rule_id: str,
        actor: str = "unknown",
        enabled: bool | None = None,
    ) -> Rule | None:
        """
        Flip `enabled` (or force it when `enabled` is given). Returns the
        updated rule, or None if it doesn't exist.
        """
        current = await self.get(rule_id)
        if not current:
            return None

        new_enabled = (not current.enabled) if enabled is None else enabled
        if new_enabled == current.enabled:
            return current

        merged = current.model_dump(mode="json")
        merged["enabled"] = new_enabled
        updated = Rule.model_validate(merged)

        await self.save_rule(updated)
        await postgres_store.save_rule_audit(
            rule_id,
            "TOGGLE",
            actor,
            {"before": {"enabled": current.enabled},
             "after":  {"enabled": new_enabled}},
        )
        return updated

    # ── Level 3 — custom rule creation ───────────────────────────
    async def create_custom_rule(
        self,
        rule: Rule,
        actor: str = "user",
    ) -> Rule:
        """
        Insert a brand-new user-owned rule. `is_default` is forced FALSE and
        `created_by` is forced to the actor — the caller cannot opt out.
        """
        payload = rule.model_dump(mode="json")
        payload["is_default"] = False
        payload["is_template"] = False
        payload["created_by"] = actor or "user"
        payload.setdefault("status", RuleStatus.ACTIVE.value)
        final = Rule.model_validate(payload)

        await self.upsert(final, actor=actor)
        # upsert already wrote CREATE/UPDATE; tag the id as user-owned
        return final

    # ── Delete (default rules are protected at the route layer) ──
    async def delete_custom_rule(
        self,
        rule_id: str,
        actor: str = "unknown",
    ) -> bool:
        """Delete a rule and log it. Returns False when the id was absent."""
        current = await self.get(rule_id)
        if not current:
            return False

        async with postgres_store.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM rules WHERE id=$1", rule_id)
        if not result.endswith(" 1"):
            return False

        await postgres_store.save_rule_audit(
            rule_id,
            "DELETE",
            actor,
            {"before": current.model_dump(mode="json"), "after": None},
        )
        return True

    # Back-compat: the old endpoint called repository.delete()
    async def delete(self, rule_id: str) -> bool:
        return await self.delete_custom_rule(rule_id, actor="admin")

    # ── Audit history ────────────────────────────────────────────
    async def get_audit_history(
        self,
        rule_id: str,
        limit: int = 100,
    ) -> list[dict]:
        return await postgres_store.list_rule_audit(rule_id, limit=limit)

    async def log_reload(self, actor: str = "unknown", count: int = 0) -> None:
        """Record a registry hot-reload in the audit trail."""
        await postgres_store.save_rule_audit(
            "__registry__",
            "RELOAD",
            actor,
            {"loaded": count},
        )


# Singleton
rule_repository = RuleRepository()
