"""``Money`` — a value object for monetary amounts.

Billing in Zimbabwe uses multiple currencies simultaneously (USD + ZWL in
everyday practice, ZAR at border clinics), so we **never** reduce money to a
bare ``Decimal``. Two ``Money`` objects in different currencies can be
compared for equality (they are not equal) but may not be added — that
requires an explicit conversion via a ``DomainService``.

All arithmetic is performed with ``Decimal`` to avoid float imprecision that
would be unacceptable for billing.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from shared_kernel.domain.value_object import ValueObject


class Currency(StrEnum):
    """Supported currencies.

    Kept deliberately small. Extending this list is a domain decision that
    ripples through Billing — pair the addition with an ADR.
    """

    USD = "USD"
    ZWL = "ZWL"
    ZAR = "ZAR"

    @property
    def minor_units(self) -> int:
        """Decimal places used for the minor unit (e.g. cents)."""
        return 2


class Money(ValueObject):
    """An amount of a specific currency.

    Invariants:

    * ``amount`` is rounded to the currency's minor-unit precision on
      construction.
    * Negative amounts are allowed (used for refunds and adjustments) but
      NaN/Infinity are not.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=False,  # we coerce Decimal-compatible inputs
        populate_by_name=True,
    )

    amount: Decimal
    currency: Currency = Field(default=Currency.USD)

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_amount(cls, v: Any) -> Decimal:
        if isinstance(v, Decimal):
            return v
        try:
            return Decimal(str(v))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"cannot coerce {v!r} to Decimal") from exc

    @model_validator(mode="after")
    def _quantize(self) -> Self:
        if not self.amount.is_finite():
            raise ValueError("Money amount must be finite")
        quantum = Decimal(10) ** -self.currency.minor_units
        # use object.__setattr__ because the model is frozen
        object.__setattr__(self, "amount", self.amount.quantize(quantum))
        return self

    # ----------------------------------------------------------- factories

    @classmethod
    def zero(cls, currency: Currency = Currency.USD) -> Self:
        return cls(amount=Decimal(0), currency=currency)

    @classmethod
    def of(cls, amount: Decimal | int | float | str, currency: Currency) -> Self:
        return cls(amount=Decimal(str(amount)), currency=currency)

    # ----------------------------------------------------------- arithmetic

    def _require_same_currency(self, other: Money) -> None:
        if self.currency is not other.currency:
            raise ValueError(
                f"currency mismatch: {self.currency.value} vs {other.currency.value} "
                "(use a DomainService to convert explicitly)"
            )

    def __add__(self, other: Money) -> Money:
        self._require_same_currency(other)
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: Money) -> Money:
        self._require_same_currency(other)
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def __mul__(self, factor: Decimal | int) -> Money:
        if isinstance(factor, float):
            raise TypeError("refusing to multiply Money by float (use Decimal)")
        return Money(amount=self.amount * Decimal(factor), currency=self.currency)

    __rmul__ = __mul__

    def __neg__(self) -> Money:
        return Money(amount=-self.amount, currency=self.currency)

    def __lt__(self, other: Money) -> bool:
        self._require_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        self._require_same_currency(other)
        return self.amount <= other.amount

    # Equality is inherited (value-based) and already handles currency because
    # `currency` is a field. The custom comparators above are only for <, <=.

    # ---------------------------------------------------- serialisation aides

    @property
    def minor_units_amount(self) -> int:
        """Return the amount in minor units (e.g. 1999 for $19.99)."""
        return int(self.amount * (Decimal(10) ** self.currency.minor_units))

    def format(self) -> str:
        """Human-readable representation. Not a substitute for i18n formatting."""
        return f"{self.amount:.{self.currency.minor_units}f} {self.currency.value}"

    def __str__(self) -> str:  # pragma: no cover
        return self.format()
