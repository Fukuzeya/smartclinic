"""Generic repository protocol.

The *domain* only sees the interface. The concrete implementation — which
talks to SQLAlchemy, PostgreSQL, or an event store — lives in the
infrastructure layer of each bounded context.

This separation is what lets us swap the Clinical context's repository from
a state-based ORM mapper to an event-sourced one without touching a single
line of domain code.
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from shared_kernel.domain.aggregate_root import AggregateRoot

TAgg = TypeVar("TAgg", bound=AggregateRoot[object])
TId = TypeVar("TId")


@runtime_checkable
class Repository(Protocol[TAgg, TId]):
    """Async repository for a single aggregate root type.

    Implementations are responsible for:

    * Materialising the aggregate from its persistent representation
      (ORM rows, event stream, …).
    * On save, detecting optimistic-concurrency conflicts against
      :attr:`AggregateRoot.version` and raising
      :class:`~shared_kernel.domain.exceptions.ConcurrencyConflict`.
    * Draining ``aggregate.pull_domain_events()`` and handing the events to
      the Unit of Work for outbox persistence.
    """

    async def get(self, aggregate_id: TId) -> TAgg: ...
    async def add(self, aggregate: TAgg) -> None: ...
    async def remove(self, aggregate: TAgg) -> None: ...
