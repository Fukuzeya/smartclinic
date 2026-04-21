"""Event-sourced aggregate root.

In this pattern the aggregate has **no** separate state table in the database.
The full state of the aggregate is derived solely by replaying its event stream
from the beginning (or from a snapshot, once added). This makes the audit trail
tamper-evident by design: you cannot change the past without breaking the replay.

Terminology used throughout the Clinical bounded context (and in ADR 0003):

* **Command** — an intent to change state (``CloseEncounter``).
* **Event** — an immutable fact that a command produced (``EncounterClosed``).
* **Apply** — the pure function that advances aggregate state given an event.
* **Rehydrate** — rebuilding an aggregate from scratch by replaying its event stream.

Design notes
------------
``_record_and_apply`` is the *only* method that command-handling methods should
call to emit new state changes. It both appends the event to the pending list
(for the Unit-of-Work to forward to the outbox) *and* immediately applies the
event to in-memory state. This keeps command methods and apply methods as the
single source of truth for both the "what happened" and "what changed".

During rehydration, events are dispatched only through ``_dispatch_apply`` so
that no new events are recorded — the aggregate is reconstructed without side
effects.

The ``_dispatch_apply`` dispatcher follows the naming convention::

    def _apply_encounter_started(self, event: EncounterStarted) -> None: ...

where the method name is ``_apply_`` + the snake_case of the event class name.
Missing handlers are silently skipped (forward-compatibility: old aggregates
survive events introduced in newer software versions during a rolling deploy).
"""

from __future__ import annotations

import re
from typing import Generic, Sequence, TypeVar

from shared_kernel.domain.aggregate_root import AggregateRoot
from shared_kernel.domain.domain_event import DomainEvent

TId = TypeVar("TId")


def _camel_to_snake(name: str) -> str:
    """``EncounterStarted`` → ``encounter_started``."""
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


class EventSourcedAggregateRoot(AggregateRoot[TId], Generic[TId]):
    """Base class for aggregates whose durable state is their event stream.

    Concrete subclasses must:

    1. Provide a ``rehydrate(...)`` class method that creates a blank instance
       and then calls :meth:`_replay` to apply all historical events.
    2. Implement ``_apply_<snake_case_event_class>(event)`` methods for each
       event type the aggregate can produce.
    3. Call ``self._record_and_apply(event)`` instead of ``self._record(event)``
       in every command-handling method, so the in-memory state is kept
       consistent with the pending-events list.
    """

    def _record_and_apply(self, event: DomainEvent) -> None:
        """Append *event* to the pending list **and** apply it to in-memory state.

        Use this in command methods.  Never mutate aggregate fields directly.
        """
        self._record(event)
        self._dispatch_apply(event)

    def _dispatch_apply(self, event: DomainEvent) -> None:
        """Route *event* to the matching ``_apply_*`` handler, if present."""
        method_name = "_apply_" + _camel_to_snake(type(event).__name__)
        handler = getattr(self, method_name, None)
        if handler is not None:
            handler(event)

    def _replay(self, events: Sequence[DomainEvent]) -> None:
        """Apply a sequence of *historical* events without recording new ones.

        Called by the concrete ``rehydrate`` class method after the blank
        instance is created.  Sets ``_version`` to the last event's
        ``aggregate_version`` so the optimistic-concurrency check in the
        repository is accurate.
        """
        for event in events:
            self._dispatch_apply(event)
            self._version = event.aggregate_version
