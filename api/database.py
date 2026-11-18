"""Database configuration and session management for SentraFlow API."""

from __future__ import annotations

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from api.config import settings

# Configure SQLite or PostgreSQL
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a thread-local database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

