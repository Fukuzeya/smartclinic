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
    DraftSOAPNoteCommand,
    ExplainDrugSafetyCommand,
    IssuePrescriptionCommand,
    LabOrderLineInput,
    PlaceLabOrderCommand,
    PrescriptionLineInput,
    RecordAIDecisionCommand,
    RecordDiagnosisCommand,
    RecordVitalSignsCommand,
    StartEncounterCommand,
    VoidEncounterCommand,
)
from clinical.application.handlers import (
    AddSOAPNoteHandler,
    CloseEncounterHandler,
    DraftSOAPNoteHandler,
    ExplainDrugSafetyHandler,
    IssuePrescriptionHandler,
    PlaceLabOrderHandler,
    RecordAIDecisionHandler,
    RecordDiagnosisHandler,
    RecordVitalSignsHandler,
    StartEncounterHandler,
    VoidEncounterHandler,
)
from clinical.infrastructure.orm import AISuggestionRecord, EncounterSummaryRow, EventStoreRecord
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
    principal = await get_current_principal(request, request.headers.get("authorization"))
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
    principal = await get_current_principal(request, request.headers.get("authorization"))
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
    principal = await get_current_principal(request, request.headers.get("authorization"))
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
    principal = await get_current_principal(request, request.headers.get("authorization"))
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
    principal = await get_current_principal(request, request.headers.get("authorization"))
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
    principal = await get_current_principal(request, request.headers.get("authorization"))
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
    principal = await get_current_principal(request, request.headers.get("authorization"))
    handler = CloseEncounterHandler(request.app.state.uow_factory)
    await handler.handle(CloseEncounterCommand(
        encounter_id=EncounterId.parse(encounter_id),
        closed_by=principal.subject,
    ))


@router.post("/{encounter_id}/void", status_code=status.HTTP_204_NO_CONTENT)
async def void_encounter(
    encounter_id: str, body: VoidRequest, request: Request
) -> None:
    principal = await get_current_principal(request, request.headers.get("authorization"))
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
    enc_id = EncounterId.parse(encounter_id)
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        row = (await session.execute(
            select(EncounterSummaryRow).where(
                EncounterSummaryRow.encounter_id == enc_id.value
            )
        )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Encounter {encounter_id} not found")

    # Hydrate aggregate from event store to get vitals/soap/diagnoses
    async with session_factory() as session:
        repo = SqlAlchemyEncounterRepository(session)
        encounter = await repo.get(enc_id)

    result = _summary_to_dict(row)
    if encounter:
        vs = encounter.vital_signs
        if vs:
            latest = vs[-1]
            result["vitals"] = {
                "temperature_c": float(latest.temperature_celsius) if latest.temperature_celsius is not None else None,
                "pulse_bpm": latest.pulse_bpm,
                "respiratory_rate": latest.respiratory_rate_rpm,
                "systolic_bp": latest.systolic_bp_mmhg,
                "diastolic_bp": latest.diastolic_bp_mmhg,
                "oxygen_saturation": float(latest.oxygen_saturation_pct) if latest.oxygen_saturation_pct is not None else None,
                "weight_kg": float(latest.weight_kg) if latest.weight_kg is not None else None,
                "height_cm": float(latest.height_cm) if latest.height_cm is not None else None,
            }
        sn = encounter.soap_notes
        if sn:
            latest_soap = sn[-1]
            result["soap"] = {
                "subjective": latest_soap.subjective,
                "objective": latest_soap.objective,
                "assessment": latest_soap.assessment,
                "plan": latest_soap.plan,
            }
        result["diagnoses"] = [
            {
                "icd10_code": dx.icd10_code.code,
                "description": dx.description,
                "is_primary": dx.is_primary,
            }
            for dx in encounter.diagnoses
        ]
    return result


@router.get("/{encounter_id}/audit", dependencies=[Depends(require_role("doctor"))])
async def audit_chain(encounter_id: str, request: Request) -> dict:
    """Verify the hash chain for an encounter (medico-legal audit endpoint)."""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        repo = SqlAlchemyEncounterRepository(session)
        return await repo.verify_chain(EncounterId.parse(encounter_id))


@router.get("/{encounter_id}/events",
            dependencies=[Depends(require_role("doctor"))])
async def get_event_stream(encounter_id: str, request: Request) -> dict:
    """Return the raw event stream for an encounter — the foundation of event sourcing.

    Each record includes its sequence number, event type, payload, occurred_at
    timestamp, and chain_hash — allowing the client to visualise the full
    temporal history and verify tamper evidence.
    """
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        enc_id = EncounterId.parse(encounter_id)
        rows = (await session.execute(
            select(EventStoreRecord)
            .where(EventStoreRecord.aggregate_id == enc_id.value)
            .order_by(EventStoreRecord.sequence)
        )).scalars().all()
    if not rows:
        raise HTTPException(status_code=404,
                            detail=f"No event stream found for encounter {encounter_id}")
    # Verify chain integrity inline so the UI can show the badge
    from clinical.infrastructure.event_store import verify_chain
    chain_result = verify_chain(rows)
    return {
        "encounter_id": encounter_id,
        "event_count": len(rows),
        "chain_valid": chain_result.is_valid,
        "chain_message": chain_result.message,
        "events": [
            {
                "sequence": r.sequence,
                "event_id": str(r.id),
                "event_type": r.event_type,
                "occurred_at": r.occurred_at.isoformat(),
                "payload": r.payload,
                "chain_hash_prefix": r.chain_hash[:16],
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# AI Clinical Copilot endpoints

class ExplainDrugSafetyRequest(BaseModel):
    drug_names: list[str]
    spec_failure_reasons: list[str]


class RecordAIDecisionRequest(BaseModel):
    decision: str = Field(pattern=r"^(accepted|discarded)$")


@router.post("/{encounter_id}/ai/soap-draft",
             dependencies=[Depends(require_role("doctor"))])
async def draft_soap_note(encounter_id: str, request: Request) -> dict:
    """Generate an AI draft SOAP note from the encounter's vitals and complaint.

    The AI suggestion is non-authoritative: it is stored in ai_suggestions
    (separate from clinical_events) and must be accepted/discarded by the
    doctor.  ADR 0013.
    """
    principal = await get_current_principal(request, request.headers.get("authorization"))
    handler = DraftSOAPNoteHandler(
        session_factory=request.app.state.session_factory,
        copilot=request.app.state.copilot,
    )
    return await handler.handle(DraftSOAPNoteCommand(
        encounter_id=EncounterId.parse(encounter_id),
        requested_by=principal.subject,
    ))


@router.post("/{encounter_id}/ai/drug-safety",
             dependencies=[Depends(require_role("doctor"))])
async def explain_drug_safety(
    encounter_id: str, body: ExplainDrugSafetyRequest, request: Request
) -> dict:
    """Generate a clinician-readable drug-safety narrative from spec failures.

    Converts machine strings from the Specification chain into plain clinical
    language.  The Specification itself remains the enforcement gate — AI only
    adds readability.  ADR 0013.
    """
    principal = await get_current_principal(request, request.headers.get("authorization"))
    handler = ExplainDrugSafetyHandler(
        session_factory=request.app.state.session_factory,
        copilot=request.app.state.copilot,
    )
    return await handler.handle(ExplainDrugSafetyCommand(
        encounter_id=EncounterId.parse(encounter_id),
        drug_names=body.drug_names,
        spec_failure_reasons=body.spec_failure_reasons,
        requested_by=principal.subject,
    ))


@router.post("/ai/suggestions/{suggestion_id}/decision",
             status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_role("doctor"))])
async def record_ai_decision(
    suggestion_id: str, body: RecordAIDecisionRequest, request: Request
) -> None:
    """Record the clinician's accept/discard decision for an AI suggestion."""
    principal = await get_current_principal(request, request.headers.get("authorization"))
    handler = RecordAIDecisionHandler(
        session_factory=request.app.state.session_factory,
    )
    await handler.handle(RecordAIDecisionCommand(
        suggestion_id=uuid.UUID(suggestion_id),
        decision=body.decision,
        decided_by=principal.subject,
    ))


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
        # Provide defaults for the detail view (frontend Encounter interface)
        "vitals": None,
        "soap": None,
        "diagnoses": [],
    }
