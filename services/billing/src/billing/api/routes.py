"""Billing HTTP API.

Write endpoints (accounts clerk role):
  POST /invoices/{id}/add-charge
  POST /invoices/{id}/issue
  POST /invoices/{id}/record-payment
  POST /invoices/{id}/void

Read endpoints (accounts, doctor, receptionist):
  GET  /invoices                 — list with filters
  GET  /invoices/{id}            — single invoice with full line/payment detail
  GET  /invoices/{id}/summary    — balance summary only
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from shared_kernel.fastapi.dependencies import (
    get_current_principal,
    require_any_role,
    require_role,
)
from shared_kernel.types.identifiers import BillId

from billing.application.commands import (
    AddChargeCommand,
    IssueInvoiceCommand,
    RecordPaymentCommand,
    VoidInvoiceCommand,
)
from billing.application.handlers import (
    AddChargeHandler,
    IssueInvoiceHandler,
    RecordPaymentHandler,
    VoidInvoiceHandler,
)
from billing.infrastructure.orm import InvoiceRow

router = APIRouter(prefix="/invoices", tags=["invoices"])


# ──────────────────────────────────────────── request models ─────────────────

class AddChargeRequest(BaseModel):
    category: str
    description: str
    unit_price_amount: str
    unit_price_currency: str = "USD"
    quantity: int = 1
    reference_id: str | None = None


class RecordPaymentRequest(BaseModel):
    amount: str
    currency: str = "USD"
    method: str
    reference: str


class VoidRequest(BaseModel):
    reason: str


# ──────────────────────────────────────────── write endpoints ─────────────────

@router.post(
    "/{invoice_id}/add-charge",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("accounts"))],
)
async def add_charge(
    invoice_id: str, body: AddChargeRequest, request: Request
) -> None:
    await AddChargeHandler(request.app.state.uow_factory).handle(
        AddChargeCommand(
            invoice_id=BillId.parse(invoice_id),
            category=body.category,
            description=body.description,
            unit_price_amount=body.unit_price_amount,
            unit_price_currency=body.unit_price_currency,
            quantity=body.quantity,
            reference_id=body.reference_id,
        )
    )


@router.post(
    "/{invoice_id}/issue",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("accounts"))],
)
async def issue_invoice(invoice_id: str, request: Request) -> None:
    principal = get_current_principal(request)
    await IssueInvoiceHandler(request.app.state.uow_factory).handle(
        IssueInvoiceCommand(
            invoice_id=BillId.parse(invoice_id),
            issued_by=principal.subject,
        )
    )


@router.post(
    "/{invoice_id}/record-payment",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("accounts"))],
)
async def record_payment(
    invoice_id: str, body: RecordPaymentRequest, request: Request
) -> None:
    principal = get_current_principal(request)
    await RecordPaymentHandler(request.app.state.uow_factory).handle(
        RecordPaymentCommand(
            invoice_id=BillId.parse(invoice_id),
            amount=body.amount,
            currency=body.currency,
            method=body.method,
            reference=body.reference,
            recorded_by=principal.subject,
        )
    )


@router.post(
    "/{invoice_id}/void",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("accounts"))],
)
async def void_invoice(
    invoice_id: str, body: VoidRequest, request: Request
) -> None:
    principal = get_current_principal(request)
    await VoidInvoiceHandler(request.app.state.uow_factory).handle(
        VoidInvoiceCommand(
            invoice_id=BillId.parse(invoice_id),
            reason=body.reason,
            voided_by=principal.subject,
        )
    )


# ──────────────────────────────────────────── read endpoints ──────────────────

@router.get(
    "",
    dependencies=[Depends(require_any_role("accounts", "doctor", "receptionist"))],
)
async def list_invoices(
    request: Request,
    patient_id: str | None = None,
    encounter_id: str | None = None,
    status_filter: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    from sqlalchemy import func

    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        q = select(InvoiceRow)
        if patient_id:
            q = q.where(InvoiceRow.patient_id == patient_id)
        if encounter_id:
            q = q.where(InvoiceRow.encounter_id == encounter_id)
        if status_filter:
            q = q.where(InvoiceRow.status == status_filter)
        total = (await session.execute(
            select(func.count()).select_from(q.subquery())
        )).scalar_one()
        rows = (await session.execute(
            q.order_by(InvoiceRow.created_at.desc()).limit(limit).offset(offset)
        )).scalars().all()
    return {
        "items": [_row_to_dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/{invoice_id}",
    dependencies=[Depends(require_any_role("accounts", "doctor", "receptionist"))],
)
async def get_invoice(invoice_id: str, request: Request) -> dict:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        row = (await session.execute(
            select(InvoiceRow).where(
                InvoiceRow.invoice_id == uuid.UUID(invoice_id)
            )
        )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _row_to_dict(row)


@router.get(
    "/{invoice_id}/summary",
    dependencies=[Depends(require_any_role("accounts", "doctor", "receptionist"))],
)
async def get_invoice_summary(invoice_id: str, request: Request) -> dict:
    from decimal import Decimal
    from shared_kernel.types.money import Currency, Money

    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        row = (await session.execute(
            select(InvoiceRow).where(
                InvoiceRow.invoice_id == uuid.UUID(invoice_id)
            )
        )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    currency = Currency(row.currency)

    def _sum_lines() -> Decimal:
        total = Decimal(0)
        for ln in (row.lines or []):
            price = Decimal(str(ln["unit_price"]["amount"]))
            qty = int(ln.get("quantity", 1))
            total += price * qty
        return total

    def _sum_payments() -> Decimal:
        total = Decimal(0)
        for p in (row.payments or []):
            total += Decimal(str(p["amount"]["amount"]))
        return total

    total_due = _sum_lines()
    total_paid = _sum_payments()
    balance = total_due - total_paid

    return {
        "invoice_id": str(row.invoice_id),
        "patient_id": row.patient_id,
        "encounter_id": row.encounter_id,
        "currency": row.currency,
        "status": row.status,
        "total_due": str(total_due),
        "total_paid": str(total_paid),
        "balance": str(max(Decimal(0), balance)),
    }


# ─────────────────────────────────────────── helper ──────────────────────────

def _row_to_dict(row: InvoiceRow) -> dict:
    return {
        "invoice_id": str(row.invoice_id),
        "patient_id": row.patient_id,
        "encounter_id": row.encounter_id,
        "currency": row.currency,
        "status": row.status,
        "lines": row.lines or [],
        "payments": row.payments or [],
        "created_at": row.created_at.isoformat(),
        "issued_at": row.issued_at.isoformat() if row.issued_at else None,
        "paid_at": row.paid_at.isoformat() if row.paid_at else None,
    }
