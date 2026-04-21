"""Async SQLAlchemy engine + session plumbing shared by all contexts.

Each service creates its own engine pointing at its own database. The only
thing shared is the ``Base`` declarative class and the consistent naming
convention — so migrations generated from one context's metadata don't
collide in name with another's.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# Consistent constraint naming — critical for alembic to generate
# deterministic migration names across contexts.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Common declarative base for every context's ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def create_engine(
    url: str,
    *,
    echo: bool = False,
    pool_size: int = 10,
    max_overflow: int = 20,
    **kwargs: Any,
) -> AsyncEngine:
    """Thin wrapper around ``create_async_engine`` with sensible defaults.

    ``asyncpg`` is assumed as the driver.
    """
    return create_async_engine(
        url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        future=True,
        **kwargs,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an ``async_sessionmaker`` with expire-on-commit disabled.

    Expire-on-commit is problematic with async code because accessing a
    stale attribute triggers an implicit refresh which requires an open
    session in the current task.
    """
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Async-generator dependency for FastAPI routes."""
    async with factory() as session:
        yield session
