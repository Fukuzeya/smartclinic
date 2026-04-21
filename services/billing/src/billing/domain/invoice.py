"""Billing Invoice aggregate.

Lifecycle::

    DRAFT → ISSUED → PARTIALLY_PAID → PAID
                                     ↑
                   ISSUED ───────────┘ (if first payment settles in full)
    DRAFT | ISSUED | PARTIALLY_PAID → VOID

Invariants:
* Charges may only be added while status is DRAFT.
* An invoice may only be issued if it has at least one charge line.
* Payments may only be recorded against ISSUED or PARTIALLY_PAID invoices.
* Payment amount must not exceed the outstanding balance.
* PAID and VOID are terminal states.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from shared_kernel.domain.aggregate_root import AggregateRoot
from shared_kernel.domain.exceptions import InvariantViolation, PreconditionFailed
from shared_kernel.domain.entity import Entity
from shared_kernel.types.identifiers import BillId
from shared_kernel.types.money import Currency, Money

from billing.domain.events import (
    ChargeAddedV1,
    InvoiceCreatedV1,
    InvoiceIssuedV1,
    InvoiceVoidedV1,
    PaymentRecordedV1,
)
from billing.domain.value_objects import (
    ChargeLine,
    InvoiceStatus,
    PaymentMethod,
    PaymentRecord,
)

_TERMINAL = {InvoiceStatus.PAID, InvoiceStatus.VOID}


class Invoice(AggregateRoot[BillId]):
    """Billing consistency boundary for a single patient encounter."""

    # ───────────────────────────────────────────── factory / rehydration ──────

    @classmethod
    def create(
        cls,
        *,
        invoice_id: BillId,
        patient_id: str,
        encounter_id: str,
        currency: Currency = Currency.USD,
    ) -> Invoice:
        instance = cls.__new__(cls)
        Entity.__init__(instance, id=invoice_id)
        instance._version = 0
        instance._pending_events = []
        instance._patient_id = patient_id
        instance._encounter_id = encounter_id
        instance._currency = currency
        instance._status = InvoiceStatus.DRAFT
        instance._lines: list[ChargeLine] = []
        instance._payments: list[PaymentRecord] = []
        instance._record(InvoiceCreatedV1.build(
            invoice_id=uuid.UUID(str(invoice_id)),
            aggregate_version=instance._next_version(),
            patient_id=patient_id,
            encounter_id=encounter_id,
            currency=currency.value,
        ))
        return instance

    @classmethod
    def rehydrate(
        cls,
        *,
        invoice_id: BillId,
        version: int,
        patient_id: str,
        encounter_id: str,
        currency: Currency,
        status: InvoiceStatus,
        lines: list[ChargeLine],
        payments: list[PaymentRecord],
    ) -> Invoice:
        instance = cls.__new__(cls)
        Entity.__init__(instance, id=invoice_id)
        instance._version = version
        instance._pending_events = []
        instance._patient_id = patient_id
        instance._encounter_id = encounter_id
        instance._currency = currency
        instance._status = status
        instance._lines = lines
        instance._payments = payments
        return instance

    # ─────────────────────────────────────────────────── commands ─────────────

    def add_charge(self, line: ChargeLine) -> None:
        """Add a billable line.  Only allowed in DRAFT status."""
        self._assert_modifiable()
        if self._status != InvoiceStatus.DRAFT:
            raise PreconditionFailed(
                f"Cannot add charges to an invoice in '{self._status}' status. "
                "Only DRAFT invoices accept new charges."
            )
        if line.unit_price.currency != self._currency:
            raise InvariantViolation(
                f"Charge currency '{line.unit_price.currency}' does not match "
                f"invoice currency '{self._currency}'."
            )
        self._lines.append(line)
        self._record(ChargeAddedV1.build(
            invoice_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            line=line.model_dump(mode="json"),
        ))

    def issue(self, *, issued_by: str) -> None:
        """Finalise the invoice and make it payable."""
        self._assert_modifiable()
        if self._status != InvoiceStatus.DRAFT:
            raise PreconditionFailed(
                f"Cannot issue invoice in '{self._status}' status."
            )
        if not self._lines:
            raise InvariantViolation(
                "Cannot issue an invoice with no charge lines."
            )
        self._status = InvoiceStatus.ISSUED
        self._record(InvoiceIssuedV1.build(
            invoice_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            total_due_minor_units=self.total_due.minor_units_amount,
            currency=self._currency.value,
            issued_by=issued_by,
        ))

    def record_payment(
        self,
        *,
        amount: Money,
        method: PaymentMethod,
        reference: str,
        recorded_by: str,
    ) -> None:
        """Apply a payment.  Automatically transitions to PAID when balance reaches zero."""
        self._assert_modifiable()
        if self._status not in (InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID):
            raise PreconditionFailed(
                f"Cannot record payment against invoice in '{self._status}' status. "
                "Invoice must be ISSUED or PARTIALLY_PAID."
            )
        if amount.currency != self._currency:
            raise InvariantViolation(
                f"Payment currency '{amount.currency}' does not match "
                f"invoice currency '{self._currency}'."
            )
        if amount.amount <= Decimal(0):
            raise InvariantViolation("Payment amount must be positive.")
        if amount > self.balance:
            raise InvariantViolation(
                f"Payment {amount.format()} exceeds outstanding balance "
                f"{self.balance.format()}."
            )

        payment = PaymentRecord(
            amount=amount,
            method=method,
            reference=reference,
            recorded_by=recorded_by,
        )
        self._payments.append(payment)

        new_balance = self.balance  # recalculated after appending
        if new_balance.amount <= Decimal(0):
            self._status = InvoiceStatus.PAID
        else:
            self._status = InvoiceStatus.PARTIALLY_PAID

        self._record(PaymentRecordedV1.build(
            invoice_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            amount_minor_units=amount.minor_units_amount,
            currency=self._currency.value,
            method=method.value,
            reference=reference,
            recorded_by=recorded_by,
            new_status=self._status.value,
            balance_minor_units=max(0, new_balance.minor_units_amount),
        ))

    def void(self, *, reason: str, voided_by: str) -> None:
        """Write off / cancel the invoice.  Cannot void a fully-paid invoice."""
        self._assert_modifiable()
        if self._status == InvoiceStatus.PAID:
            raise PreconditionFailed(
                "Cannot void a fully paid invoice. Raise a refund instead."
            )
        self._status = InvoiceStatus.VOID
        self._record(InvoiceVoidedV1.build(
            invoice_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            reason=reason,
            voided_by=voided_by,
        ))

    # ───────────────────────────────────────────────── read properties ────────

    @property
    def status(self) -> InvoiceStatus:
        return self._status

    @property
    def patient_id(self) -> str:
        return self._patient_id

    @property
    def encounter_id(self) -> str:
        return self._encounter_id

    @property
    def currency(self) -> Currency:
        return self._currency

    @property
    def lines(self) -> tuple[ChargeLine, ...]:
        return tuple(self._lines)

    @property
    def payments(self) -> tuple[PaymentRecord, ...]:
        return tuple(self._payments)

    @property
    def total_due(self) -> Money:
        total = Money.zero(self._currency)
        for line in self._lines:
            total = total + line.subtotal
        return total

    @property
    def total_paid(self) -> Money:
        total = Money.zero(self._currency)
        for payment in self._payments:
            total = total + payment.amount
        return total

    @property
    def balance(self) -> Money:
        return self.total_due - self.total_paid

    # ─────────────────────────────────────────────────── helpers ──────────────

    def _next_version(self) -> int:
        return self._version + len(self._pending_events) + 1

    def _assert_modifiable(self) -> None:
        if self._status in _TERMINAL:
            raise PreconditionFailed(
                f"Invoice is {self._status} and cannot be modified."
            )
