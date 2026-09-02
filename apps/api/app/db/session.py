"""SQLAlchemy engine/session helpers for the local Postgres backend.

Only used when DB_BACKEND=local. The Supabase path goes through PostgREST and
never touches this module.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def normalise_database_url(url: str) -> str:
    """Pin psycopg3; a bare postgresql:// URL would otherwise select psycopg2."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def make_engine(database_url: Optional[str] = None) -> Engine:
    """Build an engine for `database_url`, defaulting to settings.DATABASE_URL."""
    url = database_url or settings.database_url
    if not url:
        raise ValueError(
            "DATABASE_URL is not set. Required when DB_BACKEND=local "
            "(e.g. postgresql+psycopg://postgres:postgres@localhost:5432/spotify)"
        )
    return create_engine(normalise_database_url(url), pool_pre_ping=True, future=True)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Process-wide engine for the configured DATABASE_URL."""
    return make_engine()


def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)
