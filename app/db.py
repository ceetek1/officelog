"""Database engines and request sessions."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def app_engine() -> Engine:
    """Engine for the app's restricted role."""
    return create_engine(get_settings().resolved_app_database_url, pool_pre_ping=True, pool_size=5)


@lru_cache
def owner_engine() -> Engine:
    """Engine for the database owner: migrations and role setup only."""
    return create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=1)


@lru_cache
def _factory() -> sessionmaker[Session]:
    return sessionmaker(bind=app_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """A session per request. Endpoints that write call ``db.commit()`` themselves, before they
    answer, so a reply never claims something was saved when it wasn't. Anything not committed is
    rolled back."""
    db = _factory()()
    try:
        yield db
    finally:
        db.close()
