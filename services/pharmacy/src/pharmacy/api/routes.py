"""Pharmacy HTTP API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from shared_kernel.fastapi.dependencies import require_any_role, require_role, get_current_principal
from shared_kernel.types.identifiers import PrescriptionId

from pharmacy.application.commands import (
    DispensePartialCommand,
    DispensePrescriptionCommand,
    RejectPrescriptionCommand,
)
from pharmacy.infrastructure.orm import PrescriptionRow, DrugStockRow

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])
stock_router = APIRouter(prefix="/drug-stock", tags=["drug-stock"])


class DispenseRequest(BaseModel):
    pass  # dispensed_by comes from JWT principal


class DispensePartialRequest(BaseModel):
    drug_names: list[str]


class RejectRequest(BaseModel):
    reasons: list[str]


@router.post("/{prescription_id}/dispense",
             dependencies=[Depends(require_role("pharmacist"))])
async def dispense(prescription_id: str, request: Request) -> dict:
    """Run specification chain and dispense if satisfied."""
    principal = await get_current_principal(request, request.headers.get("authorization"))
    handler = request.app.state.dispense_handler
    result = await handler.handle(DispensePrescriptionCommand(
        prescription_id=PrescriptionId.parse(prescription_id),
        dispensed_by=principal.subject,
    ))
    if result["outcome"] == "rejected":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Dispensing rejected by specification", "reasons": result["reasons"]},
        )
    return result


@router.post("/{prescription_id}/dispense-partial",
             status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_role("pharmacist"))])
async def dispense_partial(
    prescription_id: str, body: DispensePartialRequest, request: Request
) -> None:
    principal = await get_current_principal(request, request.headers.get("authorization"))
    from pharmacy.application.handlers import DispensePartialHandler
    handler = DispensePartialHandler(request.app.state.uow_factory)
    await handler.handle(DispensePartialCommand(
        prescription_id=PrescriptionId.parse(prescription_id),
        dispensed_line_names=body.drug_names,
        dispensed_by=principal.subject,
    ))


@router.post("/{prescription_id}/reject",
             status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_role("pharmacist"))])
async def reject(prescription_id: str, body: RejectRequest, request: Request) -> None:
    principal = await get_current_principal(request, request.headers.get("authorization"))
    from pharmacy.application.handlers import RejectPrescriptionHandler
    handler = RejectPrescriptionHandler(request.app.state.uow_factory)
    await handler.handle(RejectPrescriptionCommand(
        prescription_id=PrescriptionId.parse(prescription_id),
        reasons=body.reasons,
        rejected_by=principal.subject,
    ))


@router.get("", dependencies=[Depends(require_any_role("pharmacist", "doctor"))])
async def list_prescriptions(
    request: Request,
    patient_id: str | None = None,
    status_filter: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        q = select(PrescriptionRow)
        if patient_id:
            q = q.where(PrescriptionRow.patient_id == patient_id)
        if status_filter:
            q = q.where(PrescriptionRow.status == status_filter)
        from sqlalchemy import func
        total = (await session.execute(
            select(func.count()).select_from(q.subquery())
        )).scalar_one()
        rows = (await session.execute(
            q.order_by(PrescriptionRow.received_at.desc()).limit(limit).offset(offset)
        )).scalars().all()
    return {
        "items": [_row_to_dict(r) for r in rows],
        "total": total, "limit": limit, "offset": offset,
    }


@router.get("/{prescription_id}",
            dependencies=[Depends(require_any_role("pharmacist", "doctor"))])
async def get_prescription(prescription_id: str, request: Request) -> dict:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        row = (await session.execute(
            select(PrescriptionRow).where(
                PrescriptionRow.prescription_id == uuid.UUID(prescription_id)
            )
        )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return _row_to_dict(row)


def _row_to_dict(row: PrescriptionRow) -> dict:
    return {
        "prescription_id": str(row.prescription_id),
        "encounter_id": row.encounter_id,
        "patient_id": row.patient_id,
        "issued_by": row.issued_by,
        "status": row.status,
        "lines": row.lines,
        "received_at": row.received_at.isoformat(),
        "dispensed_at": row.dispensed_at.isoformat() if row.dispensed_at else None,
    }


# ── Drug stock management endpoints ─────────────────────────────────────────


class ReceiveStockRequest(BaseModel):
    quantity: float
    reason: str = "Received from supplier"


class AdjustStockRequest(BaseModel):
    new_quantity: float
    reason: str


class AddDrugRequest(BaseModel):
    drug_name: str
    quantity_on_hand: float = 0.0
    unit: str = "tablets"
    reorder_threshold: float = 50.0


@stock_router.get("", dependencies=[Depends(require_any_role("pharmacist", "doctor"))])
async def list_drug_stock(
    request: Request,
    low_stock_only: bool = False,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """List all drugs with current stock levels."""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        q = select(DrugStockRow)
        if search:
            q = q.where(DrugStockRow.drug_name.ilike(f"%{search}%"))
        if low_stock_only:
            q = q.where(DrugStockRow.quantity_on_hand <= DrugStockRow.reorder_threshold)
        from sqlalchemy import func
        total = (await session.execute(
            select(func.count()).select_from(q.subquery())
        )).scalar_one()
        rows = (await session.execute(
            q.order_by(DrugStockRow.drug_name).limit(limit).offset(offset)
        )).scalars().all()
    return {
        "items": [_stock_to_dict(r) for r in rows],
        "total": total, "limit": limit, "offset": offset,
    }


@stock_router.get("/{drug_name}", dependencies=[Depends(require_any_role("pharmacist", "doctor"))])
async def get_drug_stock(drug_name: str, request: Request) -> dict:
    """Get stock details for a specific drug."""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        row = (await session.execute(
            select(DrugStockRow).where(DrugStockRow.drug_name == drug_name)
        )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Drug not found in inventory")
    return _stock_to_dict(row)


@stock_router.post("/{drug_name}/receive",
                   dependencies=[Depends(require_role("pharmacist"))])
async def receive_stock(drug_name: str, body: ReceiveStockRequest, request: Request) -> dict:
    """Record incoming stock from supplier."""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        row = (await session.execute(
            select(DrugStockRow).where(DrugStockRow.drug_name == drug_name)
        )).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Drug not found in inventory")
        row.quantity_on_hand += body.quantity
        from datetime import datetime, timezone
        row.last_updated_at = datetime.now(timezone.utc)
        await session.commit()
    return _stock_to_dict(row)


@stock_router.post("/{drug_name}/adjust",
                   dependencies=[Depends(require_role("pharmacist"))])
async def adjust_stock(drug_name: str, body: AdjustStockRequest, request: Request) -> dict:
    """Manual inventory adjustment with reason."""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        row = (await session.execute(
            select(DrugStockRow).where(DrugStockRow.drug_name == drug_name)
        )).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Drug not found in inventory")
        row.quantity_on_hand = body.new_quantity
        from datetime import datetime, timezone
        row.last_updated_at = datetime.now(timezone.utc)
        await session.commit()
    return _stock_to_dict(row)


@stock_router.post("", status_code=status.HTTP_201_CREATED,
                   dependencies=[Depends(require_role("pharmacist"))])
async def add_drug(body: AddDrugRequest, request: Request) -> dict:
    """Add a new drug to inventory."""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        existing = (await session.execute(
            select(DrugStockRow).where(DrugStockRow.drug_name == body.drug_name)
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Drug already exists in inventory")
        row = DrugStockRow(
            drug_name=body.drug_name,
            quantity_on_hand=body.quantity_on_hand,
            unit=body.unit,
            reorder_threshold=body.reorder_threshold,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return _stock_to_dict(row)


def _stock_to_dict(row: DrugStockRow) -> dict:
    return {
        "id": str(row.id),
        "drug_name": row.drug_name,
        "quantity_on_hand": row.quantity_on_hand,
        "unit": row.unit,
        "reorder_threshold": row.reorder_threshold,
        "is_low_stock": row.quantity_on_hand <= row.reorder_threshold,
        "last_updated_at": row.last_updated_at.isoformat(),
    }
