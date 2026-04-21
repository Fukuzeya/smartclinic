"""Unit tests for the ``ValueObject`` base."""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from shared_kernel.domain import ValueObject


class _Colour(ValueObject):
    red: int
    green: int
    blue: int


def test_value_object_is_immutable() -> None:
    c = _Colour(red=255, green=0, blue=0)
    with pytest.raises(ValidationError):
        c.red = 0  # type: ignore[misc]


def test_equal_by_value() -> None:
    assert _Colour(red=1, green=2, blue=3) == _Colour(red=1, green=2, blue=3)


def test_hash_is_stable_and_consistent_with_equality() -> None:
    a = _Colour(red=1, green=2, blue=3)
    b = _Colour(red=1, green=2, blue=3)
    assert hash(a) == hash(b)


def test_with_returns_copy_and_revalidates() -> None:
    c = _Colour(red=1, green=2, blue=3)
    d = c.with_(red=200)
    assert c.red == 1  # original unchanged
    assert d.red == 200


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        _Colour(red=1, green=2, blue=3, alpha=255)  # type: ignore[call-arg]
