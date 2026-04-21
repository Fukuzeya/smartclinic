"""The ``AggregateRoot`` base class.

An Aggregate is a **consistency boundary**: all invariants that must hold
together are enforced at the root. External code may only reference the
root, never internal entities. This is the cardinal DDD rule and the reason
we never expose raw internal lists from outside the aggregate.

Every aggregate in SmartClinic tracks *pending domain events* — facts that
will be published once the Unit of Work commits. Handlers call
``_record(event)`` on the aggregate; the UoW later calls
``pull_domain_events()`` to drain and persist them to the outbox in the
same transaction as the aggregate state change (see ADR 0009).

Optimistic concurrency is supported via the ``version`` attribute: every
successful save increments it, and a concurrent writer whose load-version is
stale will be rejected with :class:`ConcurrencyConflict`.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from shared_kernel.domain.domain_event import DomainEvent
from shared_kernel.domain.entity import Entity

TId = TypeVar("TId")


class AggregateRoot(Entity[TId], Generic[TId]):
    """Base class for the consistency-boundary root of an aggregate.

    Concrete aggregates should:

    1. Extend this class.
    2. Call ``super().__init__(id=...)`` in their constructor.
    3. Mutate state **only** inside methods that end with
       ``self._record(SomeEvent(...))`` so the event record is the ultimate
       source of truth. For event-sourced aggregates (Clinical's
       ``Encounter``) this is enforced further by making state-mutating
       methods *apply* events rather than mutate fields directly.
    """

    __slots__ = ("_pending_events", "_version")

    def __init__(self, *, id: TId, version: int = 0) -> None:
        super().__init__(id=id)
        if version < 0:
            raise ValueError("version must be non-negative")
        self._version: int = version
        self._pending_events: list[DomainEvent] = []

    # ------------------------------------------------------------------ version

    @property
    def version(self) -> int:
        """The version at which this aggregate was last persisted.

        ``0`` means "never persisted". After a successful commit, the
        infrastructure layer increments this to reflect the durable state.
        """
        return self._version

    def _bump_version(self) -> None:
        """Increment the persisted version. Called by the repository on save."""
        self._version += 1

    # ------------------------------------------------------------------ events

    def _record(self, event: DomainEvent) -> None:
        """Append a domain event to this aggregate's pending list.

        Events should be recorded **after** any invariant check has passed:
        the rule of thumb is *"validate, then record"*. Never mutate
        aggregate state without also recording the event that explains the
        mutation.
        """
        self._pending_events.append(event)

    def pull_domain_events(self) -> list[DomainEvent]:
        """Drain pending events. Idempotent when called on a clean aggregate.

        Only the Unit of Work should call this; handlers and tests may peek
        via :attr:`peek_domain_events`.
        """
        drained, self._pending_events = self._pending_events, []
        return drained

    def peek_domain_events(self) -> tuple[DomainEvent, ...]:
        """Read-only view of pending events (tests, diagnostics)."""
        return tuple(self._pending_events)

    def has_pending_events(self) -> bool:
        return bool(self._pending_events)
