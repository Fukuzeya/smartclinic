"""Unit of Work protocol.

The Unit of Work is the **atomic commit unit**. It is the *only* component
that knows how to persist aggregate state and outbox events in a single
database transaction — handlers depend on the interface and the composition
root wires in the concrete implementation (see
``shared_kernel.infrastructure.sqlalchemy_uow.SqlAlchemyUnitOfWork``).

Contract:

* Entering the UoW context begins a transaction.
* ``register(aggregate)`` signals "this aggregate has been touched; its
  pending events must be flushed on commit".
* On ``commit()`` the UoW drains pending events from every registered
  aggregate, writes them to the outbox table, then commits the DB
  transaction. Both operations happen inside the same transaction so there
  is no possibility of "state saved but events lost" or vice-versa.
* On exception or ``rollback()``, nothing is persisted and pending events
  are discarded.
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, runtime_checkable

from shared_kernel.domain.aggregate_root import AggregateRoot


@runtime_checkable
class UnitOfWork(Protocol):
    """Async context manager providing transactional commit semantics."""

    async def __aenter__(self) -> UnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    def register(self, aggregate: AggregateRoot[object]) -> None:
        """Track ``aggregate`` so its pending events are flushed on commit."""

    async def commit(self) -> None:
        """Flush pending events to the outbox and commit the DB transaction.

        Implementations must raise if any registered aggregate's stored
        version conflicts with its in-memory version (optimistic concurrency).
        """

    async def rollback(self) -> None:
        """Abandon all changes since the UoW was entered."""
