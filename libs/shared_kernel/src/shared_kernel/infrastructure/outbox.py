"""Transactional Outbox.

The cardinal reliability pattern for event-driven microservices. On write
we persist domain events to an ``outbox`` table in the **same transaction**
as the aggregate state change — so either both succeed or both fail, and
there is no possibility of "state saved but event lost" or vice versa.

A background :class:`OutboxRelay` task polls the table with
``FOR UPDATE SKIP LOCKED`` so multiple replicas can claim disjoint batches,
publishes each event to RabbitMQ, and marks it published. Retries use
exponential backoff; records that exceed ``max_attempts`` are left in place
with their error for operator attention (see ``outbox_relay_lag_seconds``
alert).

See ADR 0009 for the full rationale and trade-offs.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Integer,
    String,
    Text,
    and_,
    func,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.domain.domain_event import DomainEvent
from shared_kernel.infrastructure.database import Base
from shared_kernel.infrastructure.logging import get_logger
from shared_kernel.infrastructure.metrics import (
    EVENT_PUBLISHED,
    OUTBOX_LAG,
    OUTBOX_PENDING,
)

log = get_logger(__name__)


# ---------------------------------------------------------------- ORM model

class OutboxRecord(Base):
    """Row in the per-context outbox table.

    All timestamps are timezone-aware UTC. ``payload`` stores the
    serialised event body; ``headers`` carry the trace / correlation /
    causation tuple plus optional tamper-evidence chain data.
    """

    __tablename__ = "outbox"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    aggregate_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    routing_key: Mapped[str] = mapped_column(String(256), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    headers: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_event_dict(self) -> dict[str, Any]:
        return {
            "event_id": str(self.id),
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "occurred_at": self.occurred_at.isoformat(),
            "payload": self.payload,
            **self.headers,
        }


# ---------------------------------------------------------------- encoder

def _routing_key_for(event: DomainEvent) -> str:
    """Default routing key policy: use the event's type verbatim.

    Event types are already dotted (``clinical.encounter.diagnosed.v1``) so
    they map directly to topic-exchange routing keys — no transformation
    needed.
    """
    return event.event_type


def record_event(session: AsyncSession, event: DomainEvent) -> OutboxRecord:
    """Append one event to the outbox within the caller's transaction.

    Caller is responsible for commit. This is the **only** supported way for
    an aggregate's events to reach the bus: direct ``event_bus.publish`` is
    forbidden from application code.
    """
    row = OutboxRecord(
        id=event.event_id,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        event_type=event.event_type,
        routing_key=_routing_key_for(event),
        payload=event.payload,
        headers={
            "trace_id": event.trace_id,
            "correlation_id": event.correlation_id,
            "causation_id": str(event.causation_id) if event.causation_id else None,
            "aggregate_version": event.aggregate_version,
        },
        occurred_at=event.occurred_at,
    )
    session.add(row)
    return row


# ---------------------------------------------------------------- relay

@dataclass(slots=True)
class RelayConfig:
    service_name: str
    poll_interval_seconds: float = 2.0
    batch_size: int = 100
    max_attempts: int = 12
    base_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 60.0


class EventPublisher:
    """Narrow interface used by the relay; concrete impl is the RabbitMQ bus."""

    async def publish(
        self,
        *,
        exchange: str,
        routing_key: str,
        body: bytes,
        headers: dict[str, Any],
    ) -> None:
        raise NotImplementedError


class OutboxRelay:
    """Background task that drains the outbox into RabbitMQ.

    Safe to run N replicas concurrently thanks to
    ``SELECT ... FOR UPDATE SKIP LOCKED``.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        publisher: EventPublisher,
        exchange: str,
        config: RelayConfig,
    ) -> None:
        self._session_factory = session_factory
        self._publisher = publisher
        self._exchange = exchange
        self._config = config
        self._stopping = asyncio.Event()

    async def run_forever(self) -> None:
        log.info("outbox.relay.start", service=self._config.service_name)
        while not self._stopping.is_set():
            try:
                published = await self._drain_once()
            except Exception as exc:  # defensive — a bug here must not kill the loop
                log.exception("outbox.relay.iteration_failed", error=str(exc))
                published = 0
            await self._sleep_or_stop(
                0.05 if published >= self._config.batch_size else self._config.poll_interval_seconds
            )
        log.info("outbox.relay.stopped", service=self._config.service_name)

    def stop(self) -> None:
        self._stopping.set()

    async def _drain_once(self) -> int:
        async with self._session_factory() as session:
            async with session.begin():
                claim_stmt = (
                    select(OutboxRecord)
                    .where(OutboxRecord.published_at.is_(None))
                    .where(OutboxRecord.attempts < self._config.max_attempts)
                    .order_by(OutboxRecord.created_at)
                    .limit(self._config.batch_size)
                    .with_for_update(skip_locked=True)
                )
                batch = (await session.execute(claim_stmt)).scalars().all()
                for row in batch:
                    await self._attempt_publish(session, row)
            await self._update_lag_metric(session)
            return len(batch)

    async def _attempt_publish(
        self, session: AsyncSession, row: OutboxRecord
    ) -> None:
        body = json.dumps(row.to_event_dict(), default=str).encode("utf-8")
        try:
            await self._publisher.publish(
                exchange=self._exchange,
                routing_key=row.routing_key,
                body=body,
                headers={
                    "event-id": str(row.id),
                    "event-type": row.event_type,
                    "aggregate-type": row.aggregate_type,
                    "aggregate-id": row.aggregate_id,
                    **{k: v for k, v in row.headers.items() if v is not None},
                },
            )
        except Exception as exc:
            row.attempts += 1
            row.last_error = f"{type(exc).__name__}: {exc}"[:2000]
            log.warning(
                "outbox.publish_failed",
                event_id=str(row.id),
                event_type=row.event_type,
                attempts=row.attempts,
                error=row.last_error,
            )
            # Don't re-raise — keep the rest of the batch flowing.
            return
        row.published_at = datetime.now(UTC)
        row.last_error = None
        EVENT_PUBLISHED.labels(self._config.service_name, row.event_type).inc()

    async def _update_lag_metric(self, session: AsyncSession) -> None:
        oldest_stmt = select(
            func.min(OutboxRecord.created_at).filter(
                OutboxRecord.published_at.is_(None)
            )
        )
        pending_stmt = select(func.count()).select_from(OutboxRecord).where(
            OutboxRecord.published_at.is_(None)
        )
        oldest = (await session.execute(oldest_stmt)).scalar()
        pending = (await session.execute(pending_stmt)).scalar_one()
        OUTBOX_PENDING.labels(self._config.service_name).set(float(pending))
        if oldest is not None:
            lag = (datetime.now(UTC) - oldest).total_seconds()
        else:
            lag = 0.0
        OUTBOX_LAG.labels(self._config.service_name).set(lag)

    async def _sleep_or_stop(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=seconds)
        except TimeoutError:
            pass


__all__ = [
    "EventPublisher",
    "OutboxRecord",
    "OutboxRelay",
    "RelayConfig",
    "record_event",
]
