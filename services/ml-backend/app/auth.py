"""
auth.py — who is calling, for which tenant, and what they may do (docs/adr/0014).

With AUTH_MODE=jwt every request carries a short-lived JWT issued by the auth service
(services/auth, Better Auth), verified here against its public JWKS. Claims used:

  sub    the user id
  email  shown as the operator on answered queries and manual transitions (the audit trail)
  org    the active organization: the tenant whose fleet and data the request may touch
  role   the user's role in that organization: viewer < operator < admin, owner

Permissions, the same names the auth service grants (services/auth/src/auth.js):

  read     dashboards, logs, models, decisions                   every role
  operate  answer CADAL queries, validity checks, demo and live actions, pause   operator and up
  manage   promote, roll back, reset the fleet                    admin and owner

With AUTH_MODE=off (the laptop demo, the tests) every caller is the owner of tenant "default".
"""

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TENANT = "default"
PERMISSIONS = {
    "viewer": {"read"},
    "operator": {"read", "operate"},
    "admin": {"read", "operate", "manage"},
    "owner": {"read", "operate", "manage"},
}


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str
    tenant: str
    role: str

    def can(self, permission: str) -> bool:
        return permission in PERMISSIONS.get(self.role, set())


ANONYMOUS_OWNER = Principal("local", "operator", DEFAULT_TENANT, "owner")


class TokenError(Exception):
    pass


_jwks_client = None


def _signing_key(token: str):
    global _jwks_client
    import jwt

    if _jwks_client is None:
        # keys are cached for 5 minutes; an unknown `kid` (a rotated key) triggers one refetch
        _jwks_client = jwt.PyJWKClient(settings.auth_jwks_url, cache_keys=True, lifespan=300)
    return _jwks_client.get_signing_key_from_jwt(token).key


def verify_token(token: str) -> Principal:
    """A Principal from a valid JWT, or TokenError."""
    import jwt

    try:
        claims = jwt.decode(token, _signing_key(token), algorithms=["EdDSA", "ES256", "RS256"],
                            audience=settings.auth_audience, issuer=settings.auth_issuer,
                            options={"require": ["exp", "sub"]})
    except jwt.PyJWKClientError as exc:
        raise TokenError(f"cannot verify tokens: {exc}") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError(str(exc)) from exc
    if not claims.get("org"):
        raise TokenError("no active organization: create or join one first")
    return Principal(user_id=claims["sub"], email=claims.get("email") or claims["sub"],
                     tenant=claims["org"], role=claims.get("role") or "viewer")


def principal_from_header(authorization: Optional[str]) -> Principal:
    if settings.auth_mode != "jwt":
        return ANONYMOUS_OWNER
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "sign in required", headers={"WWW-Authenticate": "Bearer"})
    try:
        return verify_token(authorization[7:].strip())
    except TokenError as exc:
        raise HTTPException(401, str(exc), headers={"WWW-Authenticate": "Bearer"})


async def current_principal(request: Request) -> Principal:
    return principal_from_header(request.headers.get("authorization"))


def require(permission: str):
    """Dependency: the caller, if their role in the tenant grants `permission`, else 403."""
    async def check(p: Principal = Depends(current_principal)) -> Principal:
        if not p.can(permission):
            raise HTTPException(403, f"your role ({p.role}) cannot {permission}")
        return p
    return check
