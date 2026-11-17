"""Auth endpoints. Mount at /api/auth in any FastAPI app."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from .security import create_access_token, verify_password
from .store import (
    consume_reset_token,
    create_reset_token,
    create_user,
    get_user_by_email,
    update_password,
)

router = APIRouter()


class SignupBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class ForgotBody(BaseModel):
    email: EmailStr


class ResetBody(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(body: SignupBody):
    existing = await get_user_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = await create_user(body.name, body.email, body.password)
    token = create_access_token(subject=user["id"])
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/login")
async def login(body: LoginBody):
    user = await get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(subject=str(user["id"]))
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": str(user["id"]), "name": user["name"], "email": user["email"]},
    }


@router.post("/forgot-password")
async def forgot_password(body: ForgotBody):
    """Always returns 200 to prevent email enumeration."""
    user = await get_user_by_email(body.email)
    if user:
        token = await create_reset_token(str(user["id"]))
        # TODO: send email via SMTP. For now we log it.
        # The response body does NOT include the token (safer).
        print(f"[AUTH] Password reset token for {body.email}: {token}")
    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(body: ResetBody):
    user_id = await consume_reset_token(body.token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    await update_password(user_id, body.new_password)
    return {"message": "Password updated. You can now sign in."}