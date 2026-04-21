"""Unit tests for ``Money``."""

from __future__ import annotations

from decimal import Decimal

import pytest

from shared_kernel.types import Currency, Money


def test_money_quantises_to_currency_precision() -> None:
    assert Money.of("1.239", Currency.USD).amount == Decimal("1.24")


def test_addition_requires_same_currency() -> None:
    a = Money.of(10, Currency.USD)
    b = Money.of(10, Currency.ZWL)
    with pytest.raises(ValueError):
        _ = a + b


def test_addition_is_correct_for_same_currency() -> None:
    a = Money.of("1.10", Currency.USD)
    b = Money.of("2.20", Currency.USD)
    assert (a + b).amount == Decimal("3.30")


def test_equality_cares_about_currency() -> None:
    assert Money.of(10, Currency.USD) != Money.of(10, Currency.ZWL)


def test_refuses_float_multiplication() -> None:
    with pytest.raises(TypeError):
        _ = Money.of(1, Currency.USD) * 1.5  # type: ignore[operator]


def test_minor_units_amount() -> None:
    assert Money.of("19.99", Currency.USD).minor_units_amount == 1999


def test_comparisons_require_same_currency() -> None:
    with pytest.raises(ValueError):
        _ = Money.of(1, Currency.USD) < Money.of(1, Currency.ZWL)


def test_immutable() -> None:
    from pydantic import ValidationError

    m = Money.of(1, Currency.USD)
    with pytest.raises(ValidationError):
        m.amount = Decimal("2")  # type: ignore[misc]
