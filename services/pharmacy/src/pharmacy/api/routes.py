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
from pharmacy.infrastructure.orm import PrescriptionRow

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])


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
    principal = get_current_principal(request)
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
    principal = get_current_principal(request)
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
    principal = get_current_principal(request)
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
