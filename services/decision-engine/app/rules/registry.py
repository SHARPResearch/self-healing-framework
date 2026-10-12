"""
In-memory rule registry.

Lifecycle:
    - On startup, load_from_db() reads all enabled rules into memory
    - POST /api/rules/reload re-reads from DB
    - Rule CRUD endpoints call registry.reload() after writes

Access patterns:
    registry.all()              → list[Rule] sorted by priority DESC
    registry.get(rule_id)       → Rule | None
    registry.count()            → int
    registry.last_loaded_at     → datetime | None

Thread safety: single async event loop + GIL means a simple attribute
swap is atomic. We build a new dict then assign it.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.rules.models import Rule
from app.rules.repository import rule_repository
from app.rules.seeds import SEED_RULES

log = logging.getLogger(__name__)


class RuleRegistry:
    _instance: "RuleRegistry | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._rules: dict[str, Rule] = {}
            cls._instance._last_loaded_at: datetime | None = None
        return cls._instance

    # ── reads ─────────────────────────────────────────────────────
    def all(self) -> list[Rule]:
        """All enabled rules, sorted by priority DESC."""
        return sorted(
            (r for r in self._rules.values() if r.enabled),
            key=lambda r: (-r.priority, r.id),
        )

    def get(self, rule_id: str) -> Rule | None:
        return self._rules.get(rule_id)

    def count(self) -> int:
        return len(self._rules)

    @property
    def last_loaded_at(self) -> datetime | None:
        return self._last_loaded_at

    # ── lifecycle ─────────────────────────────────────────────────
    async def load_from_db(self) -> int:
        """Read all rules from Postgres into memory. Returns count."""
        rules = await rule_repository.list_all(enabled_only=False)
        self._rules = {r.id: r for r in rules}
        self._last_loaded_at = datetime.now(timezone.utc)
        log.info("RuleRegistry loaded %d rules from DB", len(self._rules))
        return len(self._rules)

    async def reload(self) -> int:
        """Alias for load_from_db — used by hot-reload endpoint."""
        return await self.load_from_db()

    async def seed_if_empty(self) -> int:
        """Insert SEED_RULES if the table is empty. Returns number inserted."""
        existing = await rule_repository.count()
        if existing > 0:
            log.info("Rules table already has %d rows; skipping seed", existing)
            return 0

        log.info("Seeding %d starter rules into Postgres", len(SEED_RULES))
        for raw in SEED_RULES:
            rule = Rule.model_validate(raw)
            await rule_repository.upsert(rule)
        return len(SEED_RULES)


# Singleton
rule_registry = RuleRegistry()