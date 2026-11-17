"""Dev-only standalone app — `python -m services.shared.auth` from repo root.

In production the auth router is mounted inside decision-engine (or a thin
gateway). This dev app exists only so you can test the three endpoints
without starting the whole stack.
"""

from fastapi import FastAPI
from .routes import router
from .migrate import run_auth_migrations


def create_app() -> FastAPI:
    app = FastAPI(title="Shared Auth (dev)")

    @app.on_event("startup")
    async def _startup():
        await run_auth_migrations()

    app.include_router(router, prefix="/api/auth", tags=["auth"])
    return app


app = create_app()