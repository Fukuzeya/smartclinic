"""Laboratory HTTP API.

Write endpoints (mutate aggregate via command handlers):
  POST /lab-orders/{id}/collect-sample   — lab technician
  POST /lab-orders/{id}/record-result    — lab technician
  POST /lab-orders/{id}/complete         — lab technician
  POST /lab-orders/{id}/cancel           — lab technician or doctor

Read endpoints (query the projection table directly):
  GET  /lab-orders                       — list with filters
  GET  /lab-orders/{id}                  — single order with results
  GET  /lab-orders/{id}/results          — results only
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
from shared_kernel.types.identifiers import LabOrderId

from laboratory.application.commands import (
    CancelOrderCommand,
    CollectSampleCommand,
    CompleteOrderCommand,
    RecordResultCommand,
)
from laboratory.application.handlers import (
    CancelOrderHandler,
    CollectSampleHandler,
    CompleteOrderHandler,
    RecordResultHandler,
)
from laboratory.infrastructure.orm import LabOrderRow

router = APIRouter(prefix="/lab-orders", tags=["lab-orders"])


# ──────────────────────────────────────────── request / response models ──────

class CollectSampleRequest(BaseModel):
    sample_type: str   # blood | urine | stool | sputum | swab | tissue | csf | other


class RecordResultRequest(BaseModel):
    test_code: str
    test_name: str
    value: str
    unit: str | None = None
    reference_range_lower: str | None = None
    reference_range_upper: str | None = None
    reference_range_unit: str | None = None
    interpretation: str   # normal | low | high | critical_low | critical_high | positive | negative | indeterminate
    notes: str | None = None


class CancelRequest(BaseModel):
    reason: str


# ──────────────────────────────────────────── write endpoints ─────────────────

@router.post(
    "/{order_id}/collect-sample",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("lab_technician"))],
)
async def collect_sample(
    order_id: str, body: CollectSampleRequest, request: Request
) -> None:
    principal = get_current_principal(request)
    await CollectSampleHandler(request.app.state.uow_factory).handle(
        CollectSampleCommand(
            order_id=LabOrderId.parse(order_id),
            sample_type=body.sample_type,
            collected_by=principal.subject,
        )
    )


@router.post(
    "/{order_id}/record-result",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("lab_technician"))],
)
async def record_result(
    order_id: str, body: RecordResultRequest, request: Request
) -> None:
    principal = get_current_principal(request)
    await RecordResultHandler(request.app.state.uow_factory).handle(
        RecordResultCommand(
            order_id=LabOrderId.parse(order_id),
            test_code=body.test_code,
            test_name=body.test_name,
            value=body.value,
            unit=body.unit,
            reference_range_lower=body.reference_range_lower,
            reference_range_upper=body.reference_range_upper,
            reference_range_unit=body.reference_range_unit,
            interpretation=body.interpretation,
            notes=body.notes,
            performed_by=principal.subject,
        )
    )


@router.post(
    "/{order_id}/complete",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("lab_technician"))],
)
async def complete_order(order_id: str, request: Request) -> None:
    principal = get_current_principal(request)
    await CompleteOrderHandler(request.app.state.uow_factory).handle(
        CompleteOrderCommand(
            order_id=LabOrderId.parse(order_id),
            reported_by=principal.subject,
        )
    )


@router.post(
    "/{order_id}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_any_role("lab_technician", "doctor"))],
)
async def cancel_order(
    order_id: str, body: CancelRequest, request: Request
) -> None:
    principal = get_current_principal(request)
    await CancelOrderHandler(request.app.state.uow_factory).handle(
        CancelOrderCommand(
            order_id=LabOrderId.parse(order_id),
            reason=body.reason,
            cancelled_by=principal.subject,
        )
    )


# ──────────────────────────────────────────── read endpoints ──────────────────

@router.get(
    "",
    dependencies=[Depends(require_any_role("lab_technician", "doctor", "receptionist"))],
)
async def list_orders(
    request: Request,
    patient_id: str | None = None,
    status_filter: str | None = None,
    encounter_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    from sqlalchemy import func

    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        q = select(LabOrderRow)
        if patient_id:
            q = q.where(LabOrderRow.patient_id == patient_id)
        if status_filter:
            q = q.where(LabOrderRow.status == status_filter)
        if encounter_id:
            q = q.where(LabOrderRow.encounter_id == encounter_id)
        total = (await session.execute(
            select(func.count()).select_from(q.subquery())
        )).scalar_one()
        rows = (await session.execute(
            q.order_by(LabOrderRow.received_at.desc()).limit(limit).offset(offset)
        )).scalars().all()
    return {
        "items": [_row_to_dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/{order_id}",
    dependencies=[Depends(require_any_role("lab_technician", "doctor", "receptionist"))],
)
async def get_order(order_id: str, request: Request) -> dict:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        row = (await session.execute(
            select(LabOrderRow).where(
                LabOrderRow.order_id == uuid.UUID(order_id)
            )
        )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Lab order not found")
    return _row_to_dict(row)


@router.get(
    "/{order_id}/results",
    dependencies=[Depends(require_any_role("lab_technician", "doctor"))],
)
async def get_results(order_id: str, request: Request) -> dict:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        row = (await session.execute(
            select(LabOrderRow).where(
                LabOrderRow.order_id == uuid.UUID(order_id)
            )
        )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Lab order not found")
    return {
        "order_id": str(row.order_id),
        "status": row.status,
        "results": row.results or [],
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


# ──────────────────────────────────────────── helper ─────────────────────────

def _row_to_dict(row: LabOrderRow) -> dict:
    return {
        "order_id": str(row.order_id),
        "patient_id": row.patient_id,
        "encounter_id": row.encounter_id,
        "ordered_by": row.ordered_by,
        "status": row.status,
        "sample_type": row.sample_type,
        "lines": row.lines,
        "results": row.results or [],
        "received_at": row.received_at.isoformat(),
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }
