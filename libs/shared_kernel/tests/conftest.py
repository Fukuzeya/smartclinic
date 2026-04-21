"""Test fixtures shared across the shared_kernel test suite."""

from __future__ import annotations

import pytest

from shared_kernel.types import FrozenClock


@pytest.fixture
def frozen_clock() -> FrozenClock:
    """A clock stuck at 2026-01-01 UTC — a sensible default for all tests."""
    return FrozenClock()
