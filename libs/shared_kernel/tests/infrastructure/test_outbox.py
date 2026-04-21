"""Integration test: aggregate save + outbox write are one transaction.

This is the headline reliability guarantee of the whole system and is worth
a live integration test rather than a mock. We spin up Postgres via
``testcontainers``, create the outbox table, save one aggregate with two
pending events, and verify:

1. Both events appear in the ``outbox`` table on commit.
2. A rolled-back transaction leaves the outbox untouched.
3. A simulated RabbitMQ failure during the relay's publish leaves events
   in place (not deleted) with incremented ``attempts``.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.postgres import PostgresContainer

from shared_kernel.domain import AggregateRoot, DomainEvent
from shared_kernel.infrastructure.database import Base, create_session_factory
from shared_kernel.infrastructure.outbox import (
    EventPublisher,
    OutboxRecord,
    OutboxRelay,
    RelayConfig,
)
from shared_kernel.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration


class _OrderPlaced(DomainEvent):
    event_type: str = "test.order.placed.v1"


class _Order(AggregateRoot[uuid.UUID]):
    def place(self) -> None:
        self._record(
            _OrderPlaced(
                aggregate_id=str(self.id),
                aggregate_type="Order",
                aggregate_version=self.version + 1,
                occurred_at=datetime.now(UTC),
            )
        )


@pytest.fixture(scope="module")
def pg() -> Any:
    with PostgresContainer("postgres:16-alpine") as c:
        yield c


@pytest.fixture
async def engine(pg: Any) -> Any:
    url = pg.get_connection_url().replace("postgresql://", "postgresql+asyncpg://")
    eng = create_async_engine(url, future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest.fixture
def session_factory(engine: Any) -> Any:
    return create_session_factory(engine)


async def test_events_land_in_outbox_on_commit(session_factory: Any) -> None:
    order = _Order(id=uuid.uuid4())
    order.place()
    order.place()

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        uow.register(order)
        await uow.commit()

    async with session_factory() as session:
        rows = (
            await session.execute(select(OutboxRecord).order_by(OutboxRecord.created_at))
        ).scalars().all()
    assert len(rows) == 2
    assert all(r.event_type == "test.order.placed.v1" for r in rows)
    assert all(r.published_at is None for r in rows)


async def test_rollback_discards_events(session_factory: Any) -> None:
    order = _Order(id=uuid.uuid4())
    order.place()
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        uow.register(order)
        # Exit without commit — the UoW must rollback.
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(OutboxRecord).where(OutboxRecord.aggregate_id == str(order.id))
            )
        ).scalars().all()
    assert rows == []
    assert not order.has_pending_events()


class _FlakyPublisher(EventPublisher):
    """Fails the first N publish attempts, then succeeds."""

    def __init__(self, fail_first: int = 2) -> None:
        self.calls = 0
        self._fail_first = fail_first

    async def publish(self, *, exchange: str, routing_key: str, body: bytes, headers: dict[str, Any]) -> None:
        self.calls += 1
        if self.calls <= self._fail_first:
            raise ConnectionError("simulated broker outage")


async def test_relay_retries_on_publisher_failure(session_factory: Any) -> None:
    order = _Order(id=uuid.uuid4())
    order.place()
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        uow.register(order)
        await uow.commit()

    publisher = _FlakyPublisher(fail_first=2)
    relay = OutboxRelay(
        session_factory=session_factory,
        publisher=publisher,
        exchange="test.exchange",
        config=RelayConfig(
            service_name="test",
            poll_interval_seconds=0.05,
            batch_size=10,
            max_attempts=5,
        ),
    )

    task = asyncio.create_task(relay.run_forever())
    # Let the relay run for a bit.
    for _ in range(30):
        await asyncio.sleep(0.1)
        async with session_factory() as session:
            row = (
                await session.execute(
                    select(OutboxRecord).where(
                        OutboxRecord.aggregate_id == str(order.id)
                    )
                )
            ).scalars().first()
            if row is not None and row.published_at is not None:
                break
    relay.stop()
    await task

    assert row is not None
    assert row.published_at is not None
    assert row.attempts >= 2  # at least two failed tries before success
