from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared_kernel.domain.exceptions import ConcurrencyConflict, NotFound
from shared_kernel.types.identifiers import BillId
from shared_kernel.types.money import Currency

from billing.domain.invoice import Invoice
from billing.domain.value_objects import (
    ChargeLine,
    InvoiceStatus,
    PaymentMethod,
    PaymentRecord,
)
from billing.infrastructure.orm import InvoiceRow


class SqlAlchemyInvoiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, invoice_id: BillId) -> Invoice:
        row = (await self._session.execute(
            select(InvoiceRow).where(
                InvoiceRow.invoice_id == uuid.UUID(str(invoice_id))
            )
        )).scalar_one_or_none()
        if row is None:
            raise NotFound(f"Invoice {invoice_id} not found")
        return _row_to_aggregate(row)

    async def get_by_encounter(self, encounter_id: str) -> Invoice | None:
        row = (await self._session.execute(
            select(InvoiceRow).where(InvoiceRow.encounter_id == encounter_id)
        )).scalar_one_or_none()
        if row is None:
            return None
        return _row_to_aggregate(row)

    async def add(self, invoice: Invoice) -> None:
        row = InvoiceRow(
            invoice_id=uuid.UUID(str(invoice.id)),
            patient_id=invoice.patient_id,
            encounter_id=invoice.encounter_id,
            currency=invoice.currency.value,
            status=invoice.status.value,
            lines=[ln.model_dump(mode="json") for ln in invoice.lines],
            payments=[],
            version=0,
        )
        self._session.add(row)
        await self._session.flush()

    async def save(self, invoice: Invoice) -> None:
        row = (await self._session.execute(
            select(InvoiceRow).where(
                InvoiceRow.invoice_id == uuid.UUID(str(invoice.id))
            )
        )).scalar_one_or_none()
        if row is None:
            raise NotFound(f"Invoice {invoice.id} not found for save")
        if row.version != invoice.version:
            raise ConcurrencyConflict(f"Invoice {invoice.id}: version conflict")

        row.status = invoice.status.value
        row.lines = [ln.model_dump(mode="json") for ln in invoice.lines]
        row.payments = [p.model_dump(mode="json") for p in invoice.payments]
        row.version = invoice.version + len(invoice.peek_domain_events())

        now = datetime.now(UTC)
        if invoice.status == InvoiceStatus.ISSUED and row.issued_at is None:
            row.issued_at = now
        if invoice.status == InvoiceStatus.PAID and row.paid_at is None:
            row.paid_at = now

        await self._session.flush()


def _row_to_aggregate(row: InvoiceRow) -> Invoice:
    lines = [ChargeLine.model_validate(ln) for ln in (row.lines or [])]
    payments = [_payment_from_dict(p) for p in (row.payments or [])]
    return Invoice.rehydrate(
        invoice_id=BillId.parse(str(row.invoice_id)),
        version=row.version,
        patient_id=row.patient_id,
        encounter_id=row.encounter_id,
        currency=Currency(row.currency),
        status=InvoiceStatus(row.status),
        lines=lines,
        payments=payments,
    )


def _payment_from_dict(d: dict) -> PaymentRecord:
    from shared_kernel.types.money import Money
    from decimal import Decimal
    amount = Money(
        amount=Decimal(str(d["amount"]["amount"])),
        currency=Currency(d["amount"]["currency"]),
    )
    return PaymentRecord(
        amount=amount,
        method=PaymentMethod(d["method"]),
        reference=d["reference"],
        recorded_by=d["recorded_by"],
    )
