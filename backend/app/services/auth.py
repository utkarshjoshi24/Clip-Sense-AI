"""
backend/app/services/auth.py — JWT creation/verification, password hashing,
token utilities.

Uses passlib with bcrypt for password hashing.
JWT uses HS256 with configurable secret key and expiry.
Refresh tokens are stored as SHA-256 hashes in the DB (never the raw token).
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models.user import User, RefreshToken, PasswordResetToken

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password ────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ─────────────────────────────────────────────────────────────────────

def create_access_token(user_id: uuid.UUID, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token. Raises JWTError if invalid."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ── Refresh Tokens ──────────────────────────────────────────────────────────

def _hash_token(raw_token: str) -> str:
    """SHA-256 hash of a raw token string for safe DB storage."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def create_refresh_token(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Generate a new refresh token, store its hash in DB, return raw token."""
    raw_token = secrets.token_urlsafe(48)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    db_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(db_token)
    await db.flush()
    return raw_token


async def rotate_refresh_token(
    db: AsyncSession, raw_token: str
) -> tuple[str, uuid.UUID] | None:
    """Validate and rotate a refresh token.

    Returns (new_raw_token, user_id) on success.
    Returns None if token is invalid, expired, or already revoked.
    If a revoked token is presented, revokes the entire user's token family
    to detect token theft.
    """
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    db_token = result.scalar_one_or_none()

    if db_token is None:
        return None

    if db_token.revoked:
        # Token reuse detected — revoke all tokens for this user
        await db.execute(
            select(RefreshToken).where(RefreshToken.user_id == db_token.user_id)
        )
        # Mark all tokens revoked
        all_tokens_result = await db.execute(
            select(RefreshToken).where(RefreshToken.user_id == db_token.user_id)
        )
        for t in all_tokens_result.scalars().all():
            t.revoked = True
        await db.flush()
        return None

    if db_token.expires_at < datetime.now(timezone.utc):
        return None

    # Revoke old token
    db_token.revoked = True
    await db.flush()

    # Issue new token
    new_raw = await create_refresh_token(db, db_token.user_id)
    return new_raw, db_token.user_id


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    """Revoke a specific refresh token (logout)."""
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    db_token = result.scalar_one_or_none()
    if db_token:
        db_token.revoked = True
        await db.flush()


# ── Password Reset ───────────────────────────────────────────────────────────

async def create_password_reset_token(db: AsyncSession, user: User) -> str:
    """Generate a password reset token, store hash in DB, return raw token."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    db_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(db_token)
    await db.flush()
    return raw_token


async def consume_password_reset_token(
    db: AsyncSession, raw_token: str
) -> User | None:
    """Validate a password reset token and mark it used.

    Returns the User if valid, None otherwise.
    """
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used == False,  # noqa: E712
        ).options()
    )
    db_token = result.scalar_one_or_none()

    if db_token is None:
        return None
    if db_token.expires_at < datetime.now(timezone.utc):
        return None

    # Load user
    user_result = await db.execute(
        select(User).where(User.id == db_token.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user:
        db_token.used = True
        await db.flush()
    return user


# ── Email Verification ───────────────────────────────────────────────────────

def create_email_verification_token(user_id: uuid.UUID) -> str:
    """Create a short-lived JWT for email verification (not stored in DB)."""
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "email_verify",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_email_verification_token(token: str) -> str | None:
    """Returns user_id string if token is valid, None otherwise."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "email_verify":
            return None
        return payload.get("sub")
    except JWTError:
        return None
