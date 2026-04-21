"""Inbox dedup — exactly-once *effect* for event consumers.

RabbitMQ gives us at-least-once delivery. That means a subscriber can see
the same event twice: network partition, consumer crash after processing
but before ack, etc. We solve this with an ``inbox`` table keyed by
``(event_id, consumer_name)``: the consumer's effect (DB write, HTTP call,
emitted command) runs only if the key is absent, and we write the key in
the **same transaction** as the effect. Re-delivery finds the key present
and skips.

See ADR 0009 for the paired rationale.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, PrimaryKeyConstraint, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.infrastructure.database import Base


class InboxRecord(Base):
    __tablename__ = "inbox"
    __table_args__ = (PrimaryKeyConstraint("event_id", "consumer_name", name="pk_inbox"),)

    event_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    consumer_name: Mapped[str] = mapped_column(String(256), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


async def was_processed(
    session: AsyncSession,
    *,
    event_id: uuid.UUID,
    consumer_name: str,
) -> bool:
    """True if ``(event_id, consumer_name)`` is already in the inbox."""
    stmt = select(InboxRecord.event_id).where(
        InboxRecord.event_id == event_id,
        InboxRecord.consumer_name == consumer_name,
    )
    return (await session.execute(stmt)).first() is not None


async def mark_processed(
    session: AsyncSession,
    *,
    event_id: uuid.UUID,
    consumer_name: str,
) -> None:
    """Insert an inbox row. Caller controls the surrounding transaction."""
    session.add(
        InboxRecord(
            event_id=event_id,
            consumer_name=consumer_name,
            processed_at=datetime.now(UTC),
        )
    )


class idempotent_consumer:  # noqa: N801 — intentional lowercase
    """Async context manager: short-circuits if the event is already processed.

    Usage::

        async with idempotent_consumer(session, event_id=..., consumer_name=...) as was_new:
            if not was_new:
                return              # already processed — skip
            ... do side effect ...
        # entering __aexit__ without error commits the inbox row.
    """

    __slots__ = ("_session", "_event_id", "_consumer_name", "_was_new")

    def __init__(
        self,
        session: AsyncSession,
        *,
        event_id: uuid.UUID,
        consumer_name: str,
    ) -> None:
        self._session = session
        self._event_id = event_id
        self._consumer_name = consumer_name
        self._was_new = False

    async def __aenter__(self) -> bool:
        already = await was_processed(
            self._session,
            event_id=self._event_id,
            consumer_name=self._consumer_name,
        )
        self._was_new = not already
        return self._was_new

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if exc is None and self._was_new:
            await mark_processed(
                self._session,
                event_id=self._event_id,
                consumer_name=self._consumer_name,
            )


__all__ = [
    "InboxRecord",
    "idempotent_consumer",
    "mark_processed",
    "was_processed",
]
