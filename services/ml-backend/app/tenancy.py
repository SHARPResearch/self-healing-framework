"""
tenancy.py — one runtime per organization (docs/adr/0015).

Every request and WebSocket is resolved to its tenant's Runtime: the fleet it may see and act on,
the store scoped to its tenant_id, and its own event channel. Nothing a runtime holds is reachable
from another tenant.

  AUTH_MODE=off       one runtime, tenant "default" (the laptop demo, the tests)
  live mode           the cluster has one owner: PRIMARY_TENANT's runtime scores it; any other
                      organization has no fleet (404 with an explanation)
  replay, no primary  every organization gets its own replay demo fleet, built the first time one
                      of its members calls; at most MAX_TENANTS of them, since each fleet holds its
                      models and SMD windows in memory (Render's free plan has 512 MB)

All tenants share one database pool (PgStore.for_tenant).
"""

import asyncio
import logging
from typing import Callable

from fastapi import HTTPException

from app.auth import DEFAULT_TENANT
from app.config import settings
from app.fleet import ServiceFleet
from app.runtime import Runtime, runtime as platform_runtime

logger = logging.getLogger(__name__)


class Tenants:
    def __init__(self, primary: Runtime):
        self.primary = primary
        self.runtimes: dict[str, Runtime] = {}
        self._lock = asyncio.Lock()
        self.fleet_factory: Callable[[], ServiceFleet] = ServiceFleet   # tests use a smaller fleet
        self._backing = self._replay = True

    @property
    def multi(self) -> bool:
        """Replay demo fleets per organization (JWT auth, no single owner)."""
        return settings.auth_mode == "jwt" and not settings.primary_tenant and not self.primary.live

    async def start(self, backing_services: bool, replay: bool) -> None:
        self._backing, self._replay = backing_services, replay
        if settings.auth_mode != "jwt":
            if self.primary.tenant != DEFAULT_TENANT:
                self.primary.set_tenant(DEFAULT_TENANT)
            await self._start(self.primary, DEFAULT_TENANT)
        elif settings.primary_tenant or self.primary.live:
            if not settings.primary_tenant:
                logger.warning("tenancy: live mode with JWT auth but no PRIMARY_TENANT; nobody can see "
                               "the cluster until it names the owning organization")
            tenant = settings.primary_tenant or DEFAULT_TENANT
            if self.primary.tenant != tenant:
                self.primary.set_tenant(tenant)
            await self._start(self.primary, tenant)
        else:
            # per-organization demo fleets, built on demand; the platform runtime stays idle, so it
            # must not buffer the backend's logs that nothing would ever flush
            self.primary.hub.uninstall()
            logger.info("tenancy: a replay fleet per organization, up to %d", settings.max_tenants)

    async def _start(self, rt: Runtime, tenant: str, store=None) -> None:
        await rt.start(backing_services=self._backing, replay=self._replay, store=store)
        self.runtimes[tenant] = rt

    async def get(self, tenant: str) -> Runtime:
        rt = self.runtimes.get(tenant)
        if rt is not None:
            return rt
        if not self.multi:
            raise HTTPException(404, "your organization has no monitored fleet on this SHARP instance "
                                     "(it monitors one cluster, owned by another organization)")
        async with self._lock:
            if tenant in self.runtimes:
                return self.runtimes[tenant]
            if len(self.runtimes) >= settings.max_tenants:
                raise HTTPException(503, f"this SHARP instance already runs {settings.max_tenants} "
                                         "organizations' demo fleets; raise MAX_TENANTS or try later")
            rt = Runtime(fleet=self.fleet_factory(), tenant=tenant, platform=False)
            logger.info("tenancy: building a replay fleet for organization %s", tenant)
            await self._start(rt, tenant, store=self._shared_store(tenant))
            return rt

    def _shared_store(self, tenant: str):
        """A store for `tenant` on an existing pool, or None to open one."""
        for rt in [self.primary, *self.runtimes.values()]:
            if getattr(rt.store, "pool", None) is not None:
                return rt.store.for_tenant(tenant)
        return None

    async def stop(self) -> None:
        for rt in reversed(list(self.runtimes.values())):
            await rt.stop()
        if self.primary not in self.runtimes.values():
            self.primary.hub.stop()
        self.runtimes.clear()

    def ready(self) -> bool:
        if self.multi:
            return True                    # fleets are built on demand; the API itself is up
        return self.primary.ready


tenants = Tenants(platform_runtime)
