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
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )

Note: `when` is a reserved word in SQL — the column is named `when_condition`.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.persistence.postgres import postgres_store
from app.rules.models import Rule

log = logging.getLogger(__name__)


def _row_to_rule(row: Any) -> Rule:
    """Convert an asyncpg Record to a Rule model."""
    return Rule.model_validate({
        "id":           row["id"],
        "version":      row["version"],
        "priority":     row["priority"],
        "description":  row["description"] or "",
        "enabled":      row["enabled"],
        "applies_to":   _jsonb(row["applies_to"]),
        "when":         _jsonb(row["when_condition"]),
        "then":         _jsonb(row["then_action"]),
        "guardrails":   _jsonb(row["guardrails"]),
        "tags":         _jsonb(row["tags"]) or [],
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


class RuleRepository:
    """All DB access for rules. Caller must ensure postgres_store is connected."""

    async def count(self) -> int:
        async with postgres_store.pool.acquire() as conn:
            return int(await conn.fetchval("SELECT COUNT(*) FROM rules"))

    async def list_all(self, enabled_only: bool = False) -> list[Rule]:
        sql = "SELECT * FROM rules"
        if enabled_only:
            sql += " WHERE enabled = TRUE"
        sql += " ORDER BY priority DESC, id ASC"
        async with postgres_store.pool.acquire() as conn:
            rows = await conn.fetch(sql)
        return [_row_to_rule(r) for r in rows]

    async def get(self, rule_id: str) -> Rule | None:
        async with postgres_store.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM rules WHERE id=$1", rule_id)
        return _row_to_rule(row) if row else None

    async def upsert(self, rule: Rule) -> None:
        """Insert or replace a rule by id."""
        payload = rule.model_dump(mode="json")
        async with postgres_store.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO rules
                    (id, version, priority, description, enabled,
                     applies_to, when_condition, then_action,
                     guardrails, tags, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10, NOW())
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
            )

    async def delete(self, rule_id: str) -> bool:
        async with postgres_store.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM rules WHERE id=$1", rule_id)
        return result.endswith(" 1")


# Singleton
rule_repository = RuleRepository()