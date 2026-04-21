"""Saga Orchestrator HTTP API — read-only observation endpoints.

The Saga is driven entirely by integration events; there are no write
endpoints.  These endpoints provide operational visibility so staff (or the
Angular dashboard) can see exactly where a patient visit stands across all
bounded contexts.

GET /sagas/{saga_id}                   — full saga state + context
GET /sagas/by-encounter/{encounter_id} — look up by encounter (natural key)
GET /sagas                             — list with filters (active/completed/cancelled)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from shared_kernel.fastapi.dependencies import require_any_role

from saga_orchestrator.infrastructure.orm import SagaRow

router = APIRouter(prefix="/sagas", tags=["sagas"])

_READABLE_ROLES = Depends(require_any_role("doctor", "receptionist", "accounts", "lab_technician"))


@router.get("", dependencies=[_READABLE_ROLES])
async def list_sagas(
    request: Request,
    patient_id: str | None = None,
    status_filter: str | None = None,
    step_filter: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    from sqlalchemy import func

    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        q = select(SagaRow)
        if patient_id:
            q = q.where(SagaRow.patient_id == patient_id)
        if status_filter:
            q = q.where(SagaRow.status == status_filter)
        if step_filter:
            q = q.where(SagaRow.step == step_filter)
        total = (await session.execute(
            select(func.count()).select_from(q.subquery())
        )).scalar_one()
        rows = (await session.execute(
            q.order_by(SagaRow.started_at.desc()).limit(limit).offset(offset)
        )).scalars().all()
    return {
        "items": [_row_to_dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/by-encounter/{encounter_id}", dependencies=[_READABLE_ROLES])
async def get_saga_by_encounter(encounter_id: str, request: Request) -> dict:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        row = (await session.execute(
            select(SagaRow).where(SagaRow.encounter_id == encounter_id)
        )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Saga not found for this encounter")
    return _row_to_dict(row)


@router.get("/{saga_id}", dependencies=[_READABLE_ROLES])
async def get_saga(saga_id: str, request: Request) -> dict:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        row = (await session.execute(
            select(SagaRow).where(SagaRow.saga_id == uuid.UUID(saga_id))
        )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Saga not found")
    return _row_to_dict(row)


def _row_to_dict(row: SagaRow) -> dict:
    return {
        "saga_id": str(row.saga_id),
        "patient_id": row.patient_id,
        "encounter_id": row.encounter_id,
        "step": row.step,
        "status": row.status,
        "context": row.context,
        "started_at": row.started_at.isoformat(),
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }
