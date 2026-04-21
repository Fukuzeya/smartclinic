"""Unit tests for the Invoice aggregate.

Covers:
* Happy-path lifecycle: DRAFT → ISSUED → PARTIALLY_PAID → PAID
* Automatic PAID transition when single payment clears the balance
* All invariant violations (terminal state guard, ordering constraints)
* Void at every valid state; cannot void PAID
* Currency mismatch guards
* Balance calculation across multiple charges and payments
* Event version sequencing
* Rehydration from persisted state
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from shared_kernel.domain.exceptions import InvariantViolation, PreconditionFailed
from shared_kernel.types.identifiers import BillId
from shared_kernel.types.money import Currency, Money

from billing.domain.events import (
    ChargeAddedV1,
    InvoiceCreatedV1,
    InvoiceIssuedV1,
    InvoiceVoidedV1,
    PaymentRecordedV1,
)
from billing.domain.invoice import Invoice
from billing.domain.value_objects import (
    ChargeCategory,
    ChargeLine,
    InvoiceStatus,
    PaymentMethod,
)

# ──────────────────────────────────────── helpers ────────────────────────────

INVOICE_ID = BillId.new()
PATIENT_ID = "patient-001"
ENCOUNTER_ID = "encounter-001"
CLERK = "accounts-clerk-sub"
DOCTOR = "doctor-sub-001"


def _make_invoice(**kwargs) -> Invoice:
    return Invoice.create(
        invoice_id=kwargs.get("invoice_id", INVOICE_ID),
        patient_id=kwargs.get("patient_id", PATIENT_ID),
        encounter_id=kwargs.get("encounter_id", ENCOUNTER_ID),
        currency=kwargs.get("currency", Currency.USD),
    )


def _usd(amount: str) -> Money:
    return Money.of(Decimal(amount), Currency.USD)


def _zwl(amount: str) -> Money:
    return Money.of(Decimal(amount), Currency.ZWL)


def _consult_line(price: str = "20.00") -> ChargeLine:
    return ChargeLine(
        category=ChargeCategory.CONSULTATION,
        description="Outpatient consultation",
        unit_price=_usd(price),
        quantity=1,
    )


def _lab_line(price: str = "15.00", qty: int = 1) -> ChargeLine:
    return ChargeLine(
        category=ChargeCategory.LAB_TEST,
        description="Lab panel",
        unit_price=_usd(price),
        quantity=qty,
    )


def _pay(invoice: Invoice, amount: str = "20.00") -> None:
    invoice.record_payment(
        amount=_usd(amount),
        method=PaymentMethod.CASH,
        reference=f"RCPT-{amount}",
        recorded_by=CLERK,
    )


# ──────────────────────────────────────── construction ───────────────────────

class TestCreate:
    def test_creates_draft_invoice(self):
        inv = _make_invoice()
        assert inv.status == InvoiceStatus.DRAFT

    def test_records_created_event(self):
        inv = _make_invoice()
        events = inv.peek_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], InvoiceCreatedV1)

    def test_created_event_carries_patient_id(self):
        inv = _make_invoice()
        assert inv.peek_domain_events()[0].payload["patient_id"] == PATIENT_ID

    def test_initial_balance_is_zero(self):
        inv = _make_invoice()
        assert inv.balance == Money.zero(Currency.USD)

    def test_created_with_usd_currency_by_default(self):
        inv = _make_invoice()
        assert inv.currency == Currency.USD

    def test_created_with_zwl_currency(self):
        inv = _make_invoice(currency=Currency.ZWL)
        assert inv.currency == Currency.ZWL


# ──────────────────────────────────────── charge addition ────────────────────

class TestAddCharge:
    def test_adds_charge_in_draft(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line())
        assert len(inv.lines) == 1

    def test_records_charge_added_event(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line())
        event_types = [type(e) for e in inv.peek_domain_events()]
        assert ChargeAddedV1 in event_types

    def test_multiple_charges_accumulate(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line())
        inv.add_charge(_lab_line())
        assert len(inv.lines) == 2

    def test_total_due_sums_all_lines(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line("20.00"))
        inv.add_charge(_lab_line("15.00", qty=2))
        assert inv.total_due == _usd("50.00")

    def test_charge_with_quantity_multiplies_subtotal(self):
        inv = _make_invoice()
        inv.add_charge(_lab_line("10.00", qty=3))
        assert inv.total_due == _usd("30.00")

    def test_cannot_add_charge_after_issue(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line())
        inv.issue(issued_by=CLERK)
        with pytest.raises(PreconditionFailed):
            inv.add_charge(_lab_line())

    def test_cannot_add_charge_to_voided_invoice(self):
        inv = _make_invoice()
        inv.void(reason="Test", voided_by=CLERK)
        with pytest.raises(PreconditionFailed):
            inv.add_charge(_consult_line())

    def test_currency_mismatch_raises_invariant_violation(self):
        inv = _make_invoice(currency=Currency.USD)
        zwl_line = ChargeLine(
            category=ChargeCategory.CONSULTATION,
            description="ZWL charge",
            unit_price=_zwl("5000.00"),
        )
        with pytest.raises(InvariantViolation, match="currency"):
            inv.add_charge(zwl_line)


# ──────────────────────────────────────── issuing ────────────────────────────

class TestIssue:
    def test_transitions_to_issued(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line())
        inv.issue(issued_by=CLERK)
        assert inv.status == InvoiceStatus.ISSUED

    def test_records_issued_event(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line())
        inv.issue(issued_by=CLERK)
        event_types = [type(e) for e in inv.peek_domain_events()]
        assert InvoiceIssuedV1 in event_types

    def test_issued_event_carries_total_due(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line("20.00"))
        inv.issue(issued_by=CLERK)
        ev = next(e for e in inv.peek_domain_events() if isinstance(e, InvoiceIssuedV1))
        assert ev.payload["total_due_minor_units"] == 2000  # $20.00 = 2000 cents

    def test_cannot_issue_empty_invoice(self):
        inv = _make_invoice()
        with pytest.raises(InvariantViolation, match="no charge lines"):
            inv.issue(issued_by=CLERK)

    def test_cannot_issue_twice(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line())
        inv.issue(issued_by=CLERK)
        with pytest.raises(PreconditionFailed):
            inv.issue(issued_by=CLERK)

    def test_cannot_issue_voided_invoice(self):
        inv = _make_invoice()
        inv.void(reason="Test", voided_by=CLERK)
        with pytest.raises(PreconditionFailed):
            inv.issue(issued_by=CLERK)


# ──────────────────────────────────────── payments ───────────────────────────

class TestRecordPayment:
    def test_partial_payment_transitions_to_partially_paid(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line("20.00"))
        inv.issue(issued_by=CLERK)
        _pay(inv, "10.00")
        assert inv.status == InvoiceStatus.PARTIALLY_PAID

    def test_full_payment_transitions_to_paid(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line("20.00"))
        inv.issue(issued_by=CLERK)
        _pay(inv, "20.00")
        assert inv.status == InvoiceStatus.PAID

    def test_two_payments_that_together_settle_balance(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line("20.00"))
        inv.issue(issued_by=CLERK)
        _pay(inv, "12.00")
        _pay(inv, "8.00")
        assert inv.status == InvoiceStatus.PAID

    def test_records_payment_recorded_event(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line())
        inv.issue(issued_by=CLERK)
        _pay(inv)
        event_types = [type(e) for e in inv.peek_domain_events()]
        assert PaymentRecordedV1 in event_types

    def test_balance_decreases_after_payment(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line("20.00"))
        inv.issue(issued_by=CLERK)
        _pay(inv, "8.00")
        assert inv.balance == _usd("12.00")

    def test_total_paid_accumulates(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line("30.00"))
        inv.issue(issued_by=CLERK)
        _pay(inv, "10.00")
        _pay(inv, "10.00")
        assert inv.total_paid == _usd("20.00")

    def test_cannot_pay_more_than_balance(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line("20.00"))
        inv.issue(issued_by=CLERK)
        with pytest.raises(InvariantViolation, match="balance"):
            _pay(inv, "25.00")

    def test_cannot_pay_zero(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line())
        inv.issue(issued_by=CLERK)
        with pytest.raises((InvariantViolation, ValueError)):
            inv.record_payment(
                amount=_usd("0.00"),
                method=PaymentMethod.CASH,
                reference="REF",
                recorded_by=CLERK,
            )

    def test_cannot_pay_draft_invoice(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line())
        with pytest.raises(PreconditionFailed):
            _pay(inv)

    def test_cannot_pay_paid_invoice(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line("20.00"))
        inv.issue(issued_by=CLERK)
        _pay(inv, "20.00")
        with pytest.raises(PreconditionFailed):
            _pay(inv, "5.00")

    def test_currency_mismatch_in_payment_raises(self):
        inv = _make_invoice(currency=Currency.USD)
        inv.add_charge(_consult_line())
        inv.issue(issued_by=CLERK)
        with pytest.raises(InvariantViolation, match="currency"):
            inv.record_payment(
                amount=_zwl("5000.00"),
                method=PaymentMethod.CASH,
                reference="REF",
                recorded_by=CLERK,
            )

    def test_ecocash_payment_method_accepted(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line("20.00"))
        inv.issue(issued_by=CLERK)
        inv.record_payment(
            amount=_usd("20.00"),
            method=PaymentMethod.ECOCASH,
            reference="ECO-12345",
            recorded_by=CLERK,
        )
        assert inv.status == InvoiceStatus.PAID


# ──────────────────────────────────────── voiding ────────────────────────────

class TestVoid:
    def test_voids_draft_invoice(self):
        inv = _make_invoice()
        inv.void(reason="Duplicate", voided_by=CLERK)
        assert inv.status == InvoiceStatus.VOID

    def test_voids_issued_invoice(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line())
        inv.issue(issued_by=CLERK)
        inv.void(reason="Patient deceased", voided_by=CLERK)
        assert inv.status == InvoiceStatus.VOID

    def test_voids_partially_paid_invoice(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line("20.00"))
        inv.issue(issued_by=CLERK)
        _pay(inv, "5.00")
        inv.void(reason="Write-off approved", voided_by=CLERK)
        assert inv.status == InvoiceStatus.VOID

    def test_records_voided_event(self):
        inv = _make_invoice()
        inv.void(reason="Test", voided_by=CLERK)
        event_types = [type(e) for e in inv.peek_domain_events()]
        assert InvoiceVoidedV1 in event_types

    def test_voided_event_carries_reason(self):
        reason = "Patient transferred"
        inv = _make_invoice()
        inv.void(reason=reason, voided_by=CLERK)
        ev = next(e for e in inv.peek_domain_events() if isinstance(e, InvoiceVoidedV1))
        assert ev.payload["reason"] == reason

    def test_cannot_void_paid_invoice(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line("20.00"))
        inv.issue(issued_by=CLERK)
        _pay(inv, "20.00")
        with pytest.raises(PreconditionFailed, match="paid"):
            inv.void(reason="Too late", voided_by=CLERK)

    def test_cannot_void_twice(self):
        inv = _make_invoice()
        inv.void(reason="First", voided_by=CLERK)
        with pytest.raises(PreconditionFailed):
            inv.void(reason="Second", voided_by=CLERK)


# ──────────────────────────────────────── version sequencing ─────────────────

class TestVersionSequencing:
    def test_first_event_version_is_one(self):
        inv = _make_invoice()
        ev = inv.peek_domain_events()[0]
        assert ev.aggregate_version == 1

    def test_each_command_increments_version(self):
        inv = _make_invoice()
        inv.add_charge(_consult_line())
        inv.issue(issued_by=CLERK)
        _pay(inv)
        versions = [e.aggregate_version for e in inv.peek_domain_events()]
        assert versions == sorted(versions)
        assert len(set(versions)) == len(versions)


# ──────────────────────────────────────── rehydration ────────────────────────

class TestRehydrate:
    def test_rehydrate_restores_status(self):
        inv = Invoice.rehydrate(
            invoice_id=INVOICE_ID,
            version=3,
            patient_id=PATIENT_ID,
            encounter_id=ENCOUNTER_ID,
            currency=Currency.USD,
            status=InvoiceStatus.ISSUED,
            lines=[_consult_line()],
            payments=[],
        )
        assert inv.status == InvoiceStatus.ISSUED

    def test_rehydrate_does_not_record_events(self):
        inv = Invoice.rehydrate(
            invoice_id=INVOICE_ID,
            version=5,
            patient_id=PATIENT_ID,
            encounter_id=ENCOUNTER_ID,
            currency=Currency.USD,
            status=InvoiceStatus.PAID,
            lines=[_consult_line()],
            payments=[],
        )
        assert len(inv.peek_domain_events()) == 0

    def test_rehydrated_version_matches(self):
        inv = Invoice.rehydrate(
            invoice_id=INVOICE_ID,
            version=7,
            patient_id=PATIENT_ID,
            encounter_id=ENCOUNTER_ID,
            currency=Currency.USD,
            status=InvoiceStatus.PAID,
            lines=[_consult_line()],
            payments=[],
        )
        assert inv.version == 7

    def test_rehydrated_paid_invoice_cannot_be_voided(self):
        inv = Invoice.rehydrate(
            invoice_id=INVOICE_ID,
            version=5,
            patient_id=PATIENT_ID,
            encounter_id=ENCOUNTER_ID,
            currency=Currency.USD,
            status=InvoiceStatus.PAID,
            lines=[_consult_line()],
            payments=[],
        )
        with pytest.raises(PreconditionFailed):
            inv.void(reason="Too late", voided_by=CLERK)
