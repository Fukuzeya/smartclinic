"""Unit tests for ``FrozenClock``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from shared_kernel.types import Clock, FrozenClock, SystemClock


def test_frozen_clock_is_deterministic() -> None:
    fixed = datetime(2030, 5, 1, 12, 0, 0, tzinfo=UTC)
    c = FrozenClock(at=fixed)
    assert c.now() == fixed
    assert c.now() == fixed  # stable across calls


def test_frozen_clock_advance() -> None:
    c = FrozenClock()
    before = c.now()
    c.advance(timedelta(hours=3))
    assert c.now() - before == timedelta(hours=3)


def test_frozen_clock_requires_tz_aware() -> None:
    with pytest.raises(ValueError):
        FrozenClock(at=datetime(2030, 1, 1))  # naive


def test_system_clock_is_tz_aware() -> None:
    assert SystemClock().now().tzinfo is not None


def test_clock_protocol_runtime_checkable() -> None:
    assert isinstance(SystemClock(), Clock)
    assert isinstance(FrozenClock(), Clock)
