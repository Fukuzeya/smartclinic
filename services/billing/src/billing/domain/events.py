"""Billing domain events."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import Field

from shared_kernel.domain.domain_event import DomainEvent


class BillingEvent(DomainEvent):
    aggregate_type: str = Field(default="Invoice")


class InvoiceCreatedV1(BillingEvent):
    event_type: str = Field(default="billing.invoice.created.v1")

    @classmethod
    def build(
        cls, *, invoice_id: uuid.UUID, aggregate_version: int,
        patient_id: str, encounter_id: str, currency: str, **kw,
    ) -> InvoiceCreatedV1:
        return cls(
            aggregate_id=str(invoice_id),
            aggregate_version=aggregate_version,
            payload={
                "patient_id": patient_id,
                "encounter_id": encounter_id,
                "currency": currency,
            },
            **kw,
        )


class ChargeAddedV1(BillingEvent):
    event_type: str = Field(default="billing.invoice.charge_added.v1")

    @classmethod
    def build(
        cls, *, invoice_id: uuid.UUID, aggregate_version: int,
        line: dict[str, Any], **kw,
    ) -> ChargeAddedV1:
        return cls(
            aggregate_id=str(invoice_id),
            aggregate_version=aggregate_version,
            payload={"line": line},
            **kw,
        )


class InvoiceIssuedV1(BillingEvent):
    """Invoice has been finalised and sent to the patient for payment."""
    event_type: str = Field(default="billing.invoice.issued.v1")

    @classmethod
    def build(
        cls, *, invoice_id: uuid.UUID, aggregate_version: int,
        total_due_minor_units: int, currency: str, issued_by: str, **kw,
    ) -> InvoiceIssuedV1:
        return cls(
            aggregate_id=str(invoice_id),
            aggregate_version=aggregate_version,
            payload={
                "total_due_minor_units": total_due_minor_units,
                "currency": currency,
                "issued_by": issued_by,
            },
            **kw,
        )


class PaymentRecordedV1(BillingEvent):
    event_type: str = Field(default="billing.invoice.payment_recorded.v1")

    @classmethod
    def build(
        cls, *, invoice_id: uuid.UUID, aggregate_version: int,
        amount_minor_units: int, currency: str,
        method: str, reference: str, recorded_by: str,
        new_status: str, balance_minor_units: int, **kw,
    ) -> PaymentRecordedV1:
        return cls(
            aggregate_id=str(invoice_id),
            aggregate_version=aggregate_version,
            payload={
                "amount_minor_units": amount_minor_units,
                "currency": currency,
                "method": method,
                "reference": reference,
                "recorded_by": recorded_by,
                "new_status": new_status,
                "balance_minor_units": balance_minor_units,
            },
            **kw,
        )


class InvoiceVoidedV1(BillingEvent):
    event_type: str = Field(default="billing.invoice.voided.v1")

    @classmethod
    def build(
        cls, *, invoice_id: uuid.UUID, aggregate_version: int,
        reason: str, voided_by: str, **kw,
    ) -> InvoiceVoidedV1:
        return cls(
            aggregate_id=str(invoice_id),
            aggregate_version=aggregate_version,
            payload={"reason": reason, "voided_by": voided_by},
            **kw,
        )
