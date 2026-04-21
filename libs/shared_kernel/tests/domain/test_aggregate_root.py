"""Unit tests for ``AggregateRoot``."""

from __future__ import annotations

import uuid

from shared_kernel.domain import AggregateRoot, DomainEvent


class _OrderPlaced(DomainEvent):
    event_type: str = "test.order.placed.v1"


class _Order(AggregateRoot[uuid.UUID]):
    def place(self) -> None:
        self._record(
            _OrderPlaced(
                aggregate_id=str(self.id),
                aggregate_type="Order",
                aggregate_version=self.version + 1,
            )
        )


def test_new_aggregate_has_no_pending_events() -> None:
    order = _Order(id=uuid.uuid4())
    assert not order.has_pending_events()
    assert order.pull_domain_events() == []


def test_record_and_drain() -> None:
    order = _Order(id=uuid.uuid4())
    order.place()
    order.place()
    assert order.has_pending_events()
    events = order.pull_domain_events()
    assert len(events) == 2
    assert not order.has_pending_events(), "drain must be idempotent"


def test_version_starts_at_zero_and_can_be_bumped() -> None:
    order = _Order(id=uuid.uuid4())
    assert order.version == 0
    order._bump_version()  # noqa: SLF001
    assert order.version == 1


def test_peek_is_nondestructive() -> None:
    order = _Order(id=uuid.uuid4())
    order.place()
    assert len(order.peek_domain_events()) == 1
    assert order.has_pending_events()  # still there
