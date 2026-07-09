"""
backend/app/routers/auth.py — Authentication endpoints.

POST /auth/signup
POST /auth/login
POST /auth/refresh
POST /auth/logout
GET  /auth/verify-email
POST /auth/forgot-password
POST /auth/reset-password
GET  /auth/me
GET  /auth/google
GET  /auth/google/callback
"""

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db
from ..dependencies import get_current_user
from ..models.user import User, UserRole
from ..models.video import Video
from ..schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from ..services import auth as auth_svc
from ..services.email import send_password_reset_email, send_verification_email

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "clipsense_refresh"
COOKIE_OPTS = dict(
    httponly=True,
    secure=settings.APP_ENV == "production",
    samesite="lax",
    max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
)


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(COOKIE_NAME, raw_token, **COOKIE_OPTS)


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)


@router.post("/signup", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=body.email,
        hashed_password=auth_svc.hash_password(body.password),
        role=UserRole.FREE,
        email_verified=False,
    )
    db.add(user)
    await db.flush()

    token = auth_svc.create_email_verification_token(user.id)
    send_verification_email(body.email, token)

    return {"message": "Account created. Please check your email to verify your address."}


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not auth_svc.verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = auth_svc.create_access_token(user.id, user.role.value)
    raw_refresh = await auth_svc.create_refresh_token(db, user.id)
    _set_refresh_cookie(response, raw_refresh)

    return {"access_token": access_token}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    clipsense_refresh: str | None = Cookie(default=None),
):
    if not clipsense_refresh:
        raise HTTPException(status_code=401, detail="No refresh token")

    result = await auth_svc.rotate_refresh_token(db, clipsense_refresh)
    if result is None:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    new_raw, user_id = result
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()

    access_token = auth_svc.create_access_token(user.id, user.role.value)
    _set_refresh_cookie(response, new_raw)

    return {"access_token": access_token}


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    clipsense_refresh: str | None = Cookie(default=None),
):
    if clipsense_refresh:
        await auth_svc.revoke_refresh_token(db, clipsense_refresh)
    _clear_refresh_cookie(response)
    return {"message": "Logged out successfully"}


@router.get("/verify-email", response_model=MessageResponse)
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    user_id_str = auth_svc.decode_email_verification_token(token)
    if not user_id_str:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    import uuid
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id_str)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.email_verified = True
    return {"message": "Email verified successfully. You can now log in."}


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    # Always return success to prevent user enumeration
    if user and user.hashed_password:
        token = await auth_svc.create_password_reset_token(db, user)
        send_password_reset_email(user.email, token)
    return {"message": "If that email is registered, you'll receive a reset link shortly."}


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_svc.consume_password_reset_token(db, body.token)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user.hashed_password = auth_svc.hash_password(body.new_password)
    return {"message": "Password updated successfully. You can now log in."}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.get("/google")
async def google_login():
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google OAuth not configured")

    params = (
        f"client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid email profile"
        f"&access_type=offline"
    )
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router.get("/google/callback")
async def google_callback(code: str, response: Response, db: AsyncSession = Depends(get_db)):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google OAuth not configured")

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Google OAuth token exchange failed")

        id_token_str = token_resp.json().get("id_token")
        # Fetch user info
        userinfo_resp = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {token_resp.json().get('access_token')}"},
        )
        userinfo = userinfo_resp.json()

    email = userinfo.get("email")
    google_sub = userinfo.get("sub")

    if not email:
        raise HTTPException(status_code=400, detail="Could not retrieve email from Google")

    # Find or create user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            email=email,
            oauth_provider="google",
            oauth_sub=google_sub,
            email_verified=True,
            role=UserRole.FREE,
        )
        db.add(user)
        await db.flush()
    elif not user.oauth_sub:
        user.oauth_provider = "google"
        user.oauth_sub = google_sub

    access_token = auth_svc.create_access_token(user.id, user.role.value)
    raw_refresh = await auth_svc.create_refresh_token(db, user.id)
    _set_refresh_cookie(response, raw_refresh)

    return RedirectResponse(
        f"{settings.FRONTEND_URL}/dashboard?access_token={access_token}"
    )
