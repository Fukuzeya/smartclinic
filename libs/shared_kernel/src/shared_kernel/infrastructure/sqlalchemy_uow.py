"""Concrete ``UnitOfWork`` implementation over SQLAlchemy async sessions.

The critical guarantee: aggregate state + domain events land in the
**same** database transaction. Handlers call
``uow.register(aggregate)`` after any successful mutation, and on
``commit()`` we:

1. Drain ``aggregate.pull_domain_events()`` for every registered aggregate.
2. Insert each event into the ``outbox`` table (see ``outbox.py``).
3. Flush + commit the session.

If the commit fails for any reason (constraint violation, concurrency
conflict, DB unavailable), the transaction is rolled back and no events
have been persisted — there is no way for the system to emit "it happened"
to downstream contexts when it in fact did not.
"""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.domain.aggregate_root import AggregateRoot
from shared_kernel.infrastructure.correlation import (
    get_causation_id,
    get_correlation_id,
)
from shared_kernel.infrastructure.logging import get_logger
from shared_kernel.infrastructure.outbox import record_event

log = get_logger(__name__)


class SqlAlchemyUnitOfWork(UnitOfWork):
    """SQLAlchemy-backed Unit of Work with outbox integration."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._tracked: list[AggregateRoot[object]] = []

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("UoW used outside of async context")
        return self._session

    # -------------------------------------------------- context manager

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        self._session = self._session_factory()
        await self._session.begin()
        self._tracked = []
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if exc is not None:
                await self.rollback()
            elif self._session is not None and self._session.in_transaction():
                # Caller forgot to commit explicitly — that's a handler bug.
                # Safer to rollback than to silently commit.
                await self.rollback()
        finally:
            if self._session is not None:
                await self._session.close()
                self._session = None

    # -------------------------------------------------- UoW contract

    def register(self, aggregate: AggregateRoot[object]) -> None:
        if aggregate not in self._tracked:
            self._tracked.append(aggregate)

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("UoW not entered")

        # Drain events and append to outbox *before* flushing: the flush will
        # include the outbox rows so everything is atomic.
        for aggregate in self._tracked:
            events = aggregate.pull_domain_events()
            if not events:
                continue
            cid = get_correlation_id()
            caus = get_causation_id()
            for event in events:
                # Fill in trace/correlation metadata if the aggregate didn't.
                enriched = event.model_copy(
                    update={
                        "correlation_id": event.correlation_id or cid,
                        "trace_id": event.trace_id,
                        "causation_id": event.causation_id
                        or (None if caus is None else _as_uuid(caus)),
                    }
                )
                record_event(self._session, enriched)
                aggregate._bump_version()  # noqa: SLF001 — UoW is an intentional friend
                log.debug(
                    "uow.event_recorded",
                    event_type=enriched.event_type,
                    aggregate_id=enriched.aggregate_id,
                    aggregate_version=enriched.aggregate_version,
                )

        await self._session.commit()
        self._tracked = []

    async def rollback(self) -> None:
        if self._session is None or not self._session.in_transaction():
            return
        await self._session.rollback()
        # Drop any pending events on the floor — they never happened.
        for agg in self._tracked:
            agg.pull_domain_events()
        self._tracked = []


def _as_uuid(value: str) -> object:
    import uuid  # local import — avoids polluting the module namespace

    try:
        return uuid.UUID(value)
    except ValueError:
        return None
