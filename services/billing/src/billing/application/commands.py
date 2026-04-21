"""Billing application-layer commands."""

from __future__ import annotations

from shared_kernel.application.command import Command
from shared_kernel.types.identifiers import BillId


class AddChargeCommand(Command):
    invoice_id: BillId
    category: str           # ChargeCategory enum value
    description: str
    unit_price_amount: str  # Decimal as string
    unit_price_currency: str = "USD"
    quantity: int = 1
    reference_id: str | None = None


class IssueInvoiceCommand(Command):
    invoice_id: BillId
    issued_by: str          # Keycloak subject


class RecordPaymentCommand(Command):
    invoice_id: BillId
    amount: str             # Decimal as string
    currency: str = "USD"
    method: str             # PaymentMethod enum value
    reference: str          # Receipt / transaction reference
    recorded_by: str        # Keycloak subject


class VoidInvoiceCommand(Command):
    invoice_id: BillId
    reason: str
    voided_by: str          # Keycloak subject
