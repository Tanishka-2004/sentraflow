"""Security utilities: password hashing and JWT issuance."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import bcrypt
import jwt

from api.config import settings


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt with tuned work factor for sub-second auth."""
    salt = bcrypt.gensalt(rounds=4)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def create_access_token(
    data: dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Generate a short-lived JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "iat": now, "type": "access"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(
    data: dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Generate a long-lived JWT refresh token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        or timedelta(days=settings.refresh_token_expire_days)
    )
    to_encode.update({"exp": expire, "iat": now, "type": "refresh"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
