"""Run auth DDL against the Neon DB. Call once on service startup."""

import asyncpg

from .config import get_auth_settings
from .schemas import AUTH_DDL


async def run_auth_migrations() -> None:
    pool = await asyncpg.create_pool(
        dsn=get_auth_settings().auth_db_url, min_size=1, max_size=2, ssl="require"
    )
    async with pool.acquire() as conn:
        for ddl in AUTH_DDL:
            await conn.execute(ddl)
    await pool.close()
    print("[AUTH] Migrations complete")