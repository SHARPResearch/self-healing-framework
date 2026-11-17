"""Users + password_resets CRUD on the shared Neon DB."""

import uuid
from datetime import datetime, timedelta, timezone

import asyncpg

from .config import get_auth_settings
from .security import hash_password


async def get_pool() -> asyncpg.Pool:
    """One pool per process. For simplicity we create it lazily."""
    # In production you'd cache this on app.state. For the research demo,
    # creating once at startup and reusing via a module global is fine.
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=get_auth_settings().auth_db_url,
            min_size=1,
            max_size=5,
            ssl="require",
        )
    return _pool


_pool: asyncpg.Pool | None = None


async def create_user(name: str, email: str, password: str) -> dict:
    pool = await get_pool()
    user_id = uuid.uuid4()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (id, name, email, password_hash)
            VALUES ($1, $2, lower($3), $4)
            """,
            user_id, name, email, hash_password(password),
        )
    return {"id": str(user_id), "name": name, "email": email.lower()}


async def get_user_by_email(email: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, email, password_hash FROM users WHERE email = lower($1)",
            email,
        )
    return dict(row) if row else None


async def get_user_by_id(user_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, email FROM users WHERE id = $1::uuid", user_id
        )
    return dict(row) if row else None


async def create_reset_token(user_id: str) -> str:
    pool = await get_pool()
    token = uuid.uuid4().hex
    ttl = get_auth_settings().reset_token_ttl_minutes
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO password_resets (token, user_id, expires_at)
            VALUES ($1, $2::uuid, $3)
            """,
            token, user_id, expires_at,
        )
    return token


async def consume_reset_token(token: str) -> str | None:
    """Returns user_id if the token is valid and unused; marks it used."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT user_id FROM password_resets
                WHERE token = $1 AND used = FALSE AND expires_at > now()
                FOR UPDATE
                """,
                token,
            )
            if not row:
                return None
            await conn.execute(
                "UPDATE password_resets SET used = TRUE WHERE token = $1", token
            )
            return str(row["user_id"])


async def update_password(user_id: str, new_password: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET password_hash = $1 WHERE id = $2::uuid",
            hash_password(new_password), user_id,
        )