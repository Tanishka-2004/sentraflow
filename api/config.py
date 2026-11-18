"""Configuration settings for SentraFlow API."""

from __future__ import annotations

import os
from pathlib import Path
from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "SentraFlow API"
    environment: str = os.getenv("ENVIRONMENT", "development")
    secret_key: str = os.getenv("JWT_SECRET_KEY", "sentraflow-super-secret-jwt-key-32-chars-long!")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    database_url: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{Path(__file__).parent.parent / 'sentraflow_meta.db'}",
    )
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]


settings = Settings()

