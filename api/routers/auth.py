"""Authentication router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
import jwt
from sqlalchemy.orm import Session

from api.config import settings
from api.database import get_db
from api.dependencies import get_current_user
from api.models import User
from api.schemas import LoginRequest, RefreshRequest, Token, UserResponse
from api.security import create_access_token, create_refresh_token, decode_token, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/token", response_model=Token)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> Token:
    """Authenticate with email and password, issuing access and refresh tokens."""
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    claims = {"sub": user.email, "role": user.role}
    access_token = create_access_token(claims)
    refresh_token = create_refresh_token(claims)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=Token)
def refresh_token(request: RefreshRequest, db: Session = Depends(get_db)) -> Token:
    """Exchange a valid refresh token for a fresh access token."""
    try:
        payload = decode_token(request.refresh_token)
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        if not email or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expired or invalid refresh token",
        )

    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled",
        )

    claims = {"sub": user.email, "role": user.role}
    new_access = create_access_token(claims)
    new_refresh = create_refresh_token(claims)

    return Token(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Retrieve profile of currently authenticated user."""
    return current_user

