"""Clinical HTTP API — write-side commands + read-side queries.

Write endpoints (POST) invoke command handlers; the response carries the
resource location only — no aggregate state is returned (CQRS).
Read endpoints (GET) query the ``encounter_summaries`` read model table
populated by the projection subscriber.

Role requirements:
* Starting / closing encounters: ``doctor``
* Recording vitals, SOAP notes, diagnoses: ``doctor``
* Issuing prescriptions / lab orders: ``doctor``
* Voiding (admin correction): ``doctor`` or ``receptionist``
* Reading encounters: ``doctor``, ``receptionist``
* Chain audit: ``doctor`` only (sensitive medico-legal endpoint)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from shared_kernel.fastapi.dependencies import require_role, require_any_role, get_current_principal
from shared_kernel.types.identifiers import EncounterId

from clinical.application.commands import (
    AddSOAPNoteCommand,
    CloseEncounterCommand,
    IssuePrescriptionCommand,
    LabOrderLineInput,
    PlaceLabOrderCommand,
    PrescriptionLineInput,
    RecordDiagnosisCommand,
    RecordVitalSignsCommand,
    StartEncounterCommand,
    VoidEncounterCommand,
)
from clinical.application.handlers import (
    AddSOAPNoteHandler,
    CloseEncounterHandler,
    IssuePrescriptionHandler,
    PlaceLabOrderHandler,
    RecordDiagnosisHandler,
    RecordVitalSignsHandler,
    StartEncounterHandler,
    VoidEncounterHandler,
)
from clinical.infrastructure.orm import EncounterSummaryRow
from clinical.infrastructure.repository import SqlAlchemyEncounterRepository

router = APIRouter(prefix="/encounters", tags=["encounters"])


# ---------------------------------------------------------------------------
# Request / response models

class StartEncounterRequest(BaseModel):
    patient_id: str
    doctor_id: str
    appointment_id: str | None = None


class RecordVitalSignsRequest(BaseModel):
    temperature_celsius: float | None = None
    systolic_bp_mmhg: int | None = None
    diastolic_bp_mmhg: int | None = None
    pulse_bpm: int | None = None
    respiratory_rate_rpm: int | None = None
    oxygen_saturation_pct: float | None = None
    weight_kg: float | None = None
    height_cm: float | None = None


class AddSOAPNoteRequest(BaseModel):
    subjective: str
    objective: str
    assessment: str
    plan: str


class RecordDiagnosisRequest(BaseModel):
    icd10_code: str
    description: str
    is_primary: bool = False


class PrescriptionLineRequest(BaseModel):
    drug_name: str
    dose: str
    route: str
    frequency: str
    duration_days: int
    instructions: str | None = None


class IssuePrescriptionRequest(BaseModel):
    lines: list[PrescriptionLineRequest] = Field(min_length=1)


class LabTestRequest(BaseModel):
    test_code: str
    urgency: str = "routine"
    notes: str | None = None


class PlaceLabOrderRequest(BaseModel):
    tests: list[LabTestRequest] = Field(min_length=1)


class VoidRequest(BaseModel):
    reason: str


# ---------------------------------------------------------------------------
# Write endpoints

@router.post("", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_role("doctor"))])
async def start_encounter(body: StartEncounterRequest, request: Request) -> dict:
    principal = get_current_principal(request)
    encounter_id = EncounterId.new()
    handler = StartEncounterHandler(request.app.state.uow_factory)
    await handler.handle(StartEncounterCommand(
        encounter_id=encounter_id,
        patient_id=body.patient_id,
        doctor_id=principal.subject,
        appointment_id=body.appointment_id,
        started_by=principal.subject,
    ))
    return {"encounter_id": str(encounter_id)}


@router.post("/{encounter_id}/vital-signs", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_role("doctor"))])
async def record_vital_signs(
    encounter_id: str, body: RecordVitalSignsRequest, request: Request
) -> None:
    principal = get_current_principal(request)
    handler = RecordVitalSignsHandler(request.app.state.uow_factory)
    await handler.handle(RecordVitalSignsCommand(
        encounter_id=EncounterId.parse(encounter_id),
        recorded_by=principal.subject,
        **body.model_dump(),
    ))


@router.post("/{encounter_id}/soap-notes", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_role("doctor"))])
async def add_soap_note(
    encounter_id: str, body: AddSOAPNoteRequest, request: Request
) -> None:
    principal = get_current_principal(request)
    handler = AddSOAPNoteHandler(request.app.state.uow_factory)
    await handler.handle(AddSOAPNoteCommand(
        encounter_id=EncounterId.parse(encounter_id),
        authored_by=principal.subject,
        **body.model_dump(),
    ))


@router.post("/{encounter_id}/diagnoses", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_role("doctor"))])
async def record_diagnosis(
    encounter_id: str, body: RecordDiagnosisRequest, request: Request
) -> None:
    principal = get_current_principal(request)
    handler = RecordDiagnosisHandler(request.app.state.uow_factory)
    await handler.handle(RecordDiagnosisCommand(
        encounter_id=EncounterId.parse(encounter_id),
        recorded_by=principal.subject,
        **body.model_dump(),
    ))


@router.post("/{encounter_id}/prescriptions", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_role("doctor"))])
async def issue_prescription(
    encounter_id: str, body: IssuePrescriptionRequest, request: Request
) -> None:
    principal = get_current_principal(request)
    handler = IssuePrescriptionHandler(request.app.state.uow_factory)
    lines = [PrescriptionLineInput(**ln.model_dump()) for ln in body.lines]
    await handler.handle(IssuePrescriptionCommand(
        encounter_id=EncounterId.parse(encounter_id),
        lines=lines,
        issued_by=principal.subject,
    ))


@router.post("/{encounter_id}/lab-orders", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_role("doctor"))])
async def place_lab_order(
    encounter_id: str, body: PlaceLabOrderRequest, request: Request
) -> None:
    principal = get_current_principal(request)
    handler = PlaceLabOrderHandler(request.app.state.uow_factory)
    tests = [LabOrderLineInput(**t.model_dump()) for t in body.tests]
    await handler.handle(PlaceLabOrderCommand(
        encounter_id=EncounterId.parse(encounter_id),
        tests=tests,
        ordered_by=principal.subject,
    ))


@router.post("/{encounter_id}/close", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_role("doctor"))])
async def close_encounter(encounter_id: str, request: Request) -> None:
    principal = get_current_principal(request)
    handler = CloseEncounterHandler(request.app.state.uow_factory)
    await handler.handle(CloseEncounterCommand(
        encounter_id=EncounterId.parse(encounter_id),
        closed_by=principal.subject,
    ))


@router.post("/{encounter_id}/void", status_code=status.HTTP_204_NO_CONTENT)
async def void_encounter(
    encounter_id: str, body: VoidRequest, request: Request
) -> None:
    principal = get_current_principal(request)
    if not (principal.has_role("doctor") or principal.has_role("receptionist")):
        raise HTTPException(status_code=403, detail="Forbidden")
    handler = VoidEncounterHandler(request.app.state.uow_factory)
    await handler.handle(VoidEncounterCommand(
        encounter_id=EncounterId.parse(encounter_id),
        reason=body.reason,
        voided_by=principal.subject,
    ))


# ---------------------------------------------------------------------------
# Read endpoints (query the read model)

@router.get("")
async def list_encounters(
    request: Request,
    patient_id: str | None = None,
    doctor_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    _: None = Depends(require_any_role("doctor", "receptionist")),
) -> dict:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        q = select(EncounterSummaryRow)
        if patient_id:
            q = q.where(EncounterSummaryRow.patient_id == patient_id)
        if doctor_id:
            q = q.where(EncounterSummaryRow.doctor_id == doctor_id)
        if status:
            q = q.where(EncounterSummaryRow.status == status)
        from sqlalchemy import func
        total_q = select(func.count()).select_from(q.subquery())
        total = (await session.execute(total_q)).scalar_one()
        rows = (await session.execute(q.order_by(
            EncounterSummaryRow.started_at.desc()
        ).limit(limit).offset(offset))).scalars().all()
    return {
        "items": [_summary_to_dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{encounter_id}")
async def get_encounter(
    encounter_id: str,
    request: Request,
    _: None = Depends(require_any_role("doctor", "receptionist")),
) -> dict:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        row = (await session.execute(
            select(EncounterSummaryRow).where(
                EncounterSummaryRow.encounter_id == uuid.UUID(encounter_id)
            )
        )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Encounter {encounter_id} not found")
    return _summary_to_dict(row)


@router.get("/{encounter_id}/audit", dependencies=[Depends(require_role("doctor"))])
async def audit_chain(encounter_id: str, request: Request) -> dict:
    """Verify the hash chain for an encounter (medico-legal audit endpoint)."""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        repo = SqlAlchemyEncounterRepository(session)
        return await repo.verify_chain(EncounterId.parse(encounter_id))


# ---------------------------------------------------------------------------

def _summary_to_dict(row: EncounterSummaryRow) -> dict:
    return {
        "encounter_id": str(row.encounter_id),
        "patient_id": row.patient_id,
        "doctor_id": row.doctor_id,
        "appointment_id": row.appointment_id,
        "status": row.status,
        "started_at": row.started_at.isoformat(),
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
        "primary_icd10": row.primary_icd10,
        "has_prescription": row.has_prescription,
        "has_lab_order": row.has_lab_order,
        "vital_signs_count": row.vital_signs_count,
        "notes_count": row.notes_count,
        "diagnoses_count": row.diagnoses_count,
    }
