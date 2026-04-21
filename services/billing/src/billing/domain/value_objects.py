"""Billing bounded context — value objects."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import Field, model_validator

from shared_kernel.domain.value_object import ValueObject
from shared_kernel.types.money import Currency, Money


class InvoiceStatus(StrEnum):
    DRAFT = "draft"                # Charges can still be added
    ISSUED = "issued"              # Sent to patient; no more charge additions
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"                  # Terminal — fully settled
    VOID = "void"                  # Terminal — cancelled/written off


class ChargeCategory(StrEnum):
    CONSULTATION = "consultation"
    LAB_TEST = "lab_test"
    MEDICATION = "medication"
    PROCEDURE = "procedure"
    ACCOMMODATION = "accommodation"
    OTHER = "other"


class PaymentMethod(StrEnum):
    CASH = "cash"
    ECOCASH = "ecocash"           # Zimbabwean mobile money
    ZIPIT = "zipit"               # ZIPIT bank transfer (Zimbabwe)
    INSURANCE = "insurance"
    BANK_TRANSFER = "bank_transfer"
    OTHER = "other"


class ChargeLine(ValueObject):
    """One billable item on an invoice."""
    category: ChargeCategory
    description: str = Field(min_length=1, max_length=255)
    unit_price: Money
    quantity: int = Field(ge=1, default=1)
    # Optional reference back to the source document (lab order id, etc.)
    reference_id: str | None = None

    @property
    def subtotal(self) -> Money:
        return self.unit_price * self.quantity


class PaymentRecord(ValueObject):
    """One payment applied against an invoice."""
    amount: Money
    method: PaymentMethod
    reference: str = Field(min_length=1, max_length=100)  # receipt / txn ref
    recorded_by: str   # Keycloak subject of the accounts clerk

    @model_validator(mode="after")
    def _positive_amount(self) -> PaymentRecord:
        if self.amount.amount <= Decimal(0):
            raise ValueError("Payment amount must be positive")
        return self


class InvoiceCurrency(StrEnum):
    """Convenience alias so the service does not import Currency directly."""
    USD = Currency.USD.value
    ZWL = Currency.ZWL.value
    ZAR = Currency.ZAR.value
