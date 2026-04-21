"""``Clock`` — a tiny abstraction over "the current time".

Domain logic that branches on *now* (appointment conflict detection,
prescription expiry, stale-event pruning) must not call ``datetime.now()``
directly — that makes tests flaky and non-deterministic. Instead, handlers
depend on a ``Clock`` protocol and the composition root wires in the real
clock in production and a :class:`FrozenClock` in tests.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Abstract source of current time (always timezone-aware UTC)."""

    def now(self) -> datetime: ...


class SystemClock:
    """Real clock — the only production implementation."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """A clock stuck at a configurable instant (for tests).

    Supports :meth:`advance` so tests can simulate time progression
    deterministically.
    """

    def __init__(self, at: datetime | None = None) -> None:
        if at is None:
            at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        if at.tzinfo is None:
            raise ValueError("FrozenClock requires a timezone-aware datetime")
        self._now = at

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now = self._now + delta
