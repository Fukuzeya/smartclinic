"""Clinical command handlers.

All handlers follow the same structure:
1. Open a UoW scope.
2. Load the aggregate (or create a new one).
3. Call the domain method.
4. Persist via the repository.
5. Register the aggregate with the UoW so its pending events are flushed to
   the outbox in the same commit.
6. Commit — both the event store rows and the outbox rows land atomically.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel.ai.copilot_port import AISuggestion, ClinicalCopilotPort
from shared_kernel.domain.exceptions import NotFound
from shared_kernel.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork

from clinical.application.commands import (
    AddSOAPNoteCommand,
    CloseEncounterCommand,
    DraftSOAPNoteCommand,
    ExplainDrugSafetyCommand,
    IssuePrescriptionCommand,
    PlaceLabOrderCommand,
    RecordAIDecisionCommand,
    RecordDiagnosisCommand,
    RecordVitalSignsCommand,
    StartEncounterCommand,
    VoidEncounterCommand,
)
from clinical.domain.encounter import Encounter
from clinical.domain.value_objects import (
    Diagnosis,
    ICD10Code,
    LabOrderLine,
    PrescriptionLine,
    SOAPNote,
    VitalSigns,
)
from clinical.infrastructure.orm import AISuggestionRecord
from clinical.infrastructure.repository import SqlAlchemyEncounterRepository


class StartEncounterHandler:
    def __init__(self, uow_factory: type[SqlAlchemyUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def handle(self, cmd: StartEncounterCommand) -> str:
        async with self._uow_factory() as uow:
            repo = SqlAlchemyEncounterRepository(uow.session)
            encounter = Encounter.start(
                encounter_id=cmd.encounter_id,
                patient_id=cmd.patient_id,
                doctor_id=cmd.doctor_id,
                appointment_id=cmd.appointment_id,
                started_by=cmd.started_by,
            )
            await repo.add(encounter)
            uow.register(encounter)
            await uow.commit()
        return str(cmd.encounter_id)


class RecordVitalSignsHandler:
    def __init__(self, uow_factory: type[SqlAlchemyUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def handle(self, cmd: RecordVitalSignsCommand) -> None:
        async with self._uow_factory() as uow:
            repo = SqlAlchemyEncounterRepository(uow.session)
            encounter = await repo.get(cmd.encounter_id)
            vitals = VitalSigns(
                temperature_celsius=cmd.temperature_celsius,
                systolic_bp_mmhg=cmd.systolic_bp_mmhg,
                diastolic_bp_mmhg=cmd.diastolic_bp_mmhg,
                pulse_bpm=cmd.pulse_bpm,
                respiratory_rate_rpm=cmd.respiratory_rate_rpm,
                oxygen_saturation_pct=cmd.oxygen_saturation_pct,
                weight_kg=cmd.weight_kg,
                height_cm=cmd.height_cm,
                recorded_by=cmd.recorded_by,
            )
            encounter.record_vital_signs(vitals=vitals)
            await repo.save(encounter)
            uow.register(encounter)
            await uow.commit()


class AddSOAPNoteHandler:
    def __init__(self, uow_factory: type[SqlAlchemyUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def handle(self, cmd: AddSOAPNoteCommand) -> None:
        async with self._uow_factory() as uow:
            repo = SqlAlchemyEncounterRepository(uow.session)
            encounter = await repo.get(cmd.encounter_id)
            note = SOAPNote(
                subjective=cmd.subjective,
                objective=cmd.objective,
                assessment=cmd.assessment,
                plan=cmd.plan,
                authored_by=cmd.authored_by,
            )
            encounter.add_soap_note(note=note)
            await repo.save(encounter)
            uow.register(encounter)
            await uow.commit()


class RecordDiagnosisHandler:
    def __init__(self, uow_factory: type[SqlAlchemyUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def handle(self, cmd: RecordDiagnosisCommand) -> None:
        async with self._uow_factory() as uow:
            repo = SqlAlchemyEncounterRepository(uow.session)
            encounter = await repo.get(cmd.encounter_id)
            diagnosis = Diagnosis(
                icd10_code=ICD10Code(code=cmd.icd10_code),
                description=cmd.description,
                is_primary=cmd.is_primary,
                recorded_by=cmd.recorded_by,
            )
            encounter.record_diagnosis(diagnosis=diagnosis)
            await repo.save(encounter)
            uow.register(encounter)
            await uow.commit()


class IssuePrescriptionHandler:
    def __init__(self, uow_factory: type[SqlAlchemyUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def handle(self, cmd: IssuePrescriptionCommand) -> None:
        async with self._uow_factory() as uow:
            repo = SqlAlchemyEncounterRepository(uow.session)
            encounter = await repo.get(cmd.encounter_id)
            lines = [
                PrescriptionLine(
                    drug_name=ln.drug_name,
                    dose=ln.dose,
                    route=ln.route,
                    frequency=ln.frequency,
                    duration_days=ln.duration_days,
                    instructions=ln.instructions,
                )
                for ln in cmd.lines
            ]
            encounter.issue_prescription(
                prescription_id=cmd.prescription_id,
                lines=lines,
                issued_by=cmd.issued_by,
            )
            await repo.save(encounter)
            uow.register(encounter)
            await uow.commit()


class PlaceLabOrderHandler:
    def __init__(self, uow_factory: type[SqlAlchemyUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def handle(self, cmd: PlaceLabOrderCommand) -> None:
        async with self._uow_factory() as uow:
            repo = SqlAlchemyEncounterRepository(uow.session)
            encounter = await repo.get(cmd.encounter_id)
            tests = [
                LabOrderLine(
                    test_code=t.test_code,
                    urgency=t.urgency,
                    notes=t.notes,
                )
                for t in cmd.tests
            ]
            encounter.place_lab_order(
                lab_order_id=cmd.lab_order_id,
                tests=tests,
                ordered_by=cmd.ordered_by,
            )
            await repo.save(encounter)
            uow.register(encounter)
            await uow.commit()


class CloseEncounterHandler:
    def __init__(self, uow_factory: type[SqlAlchemyUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def handle(self, cmd: CloseEncounterCommand) -> None:
        async with self._uow_factory() as uow:
            repo = SqlAlchemyEncounterRepository(uow.session)
            encounter = await repo.get(cmd.encounter_id)
            encounter.close(closed_by=cmd.closed_by)
            await repo.save(encounter)
            uow.register(encounter)
            await uow.commit()


class VoidEncounterHandler:
    def __init__(self, uow_factory: type[SqlAlchemyUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def handle(self, cmd: VoidEncounterCommand) -> None:
        async with self._uow_factory() as uow:
            repo = SqlAlchemyEncounterRepository(uow.session)
            encounter = await repo.get(cmd.encounter_id)
            encounter.void(reason=cmd.reason, voided_by=cmd.voided_by)
            await repo.save(encounter)
            uow.register(encounter)
            await uow.commit()


# ---------------------------------------------------------------------------
# AI Copilot handlers

class DraftSOAPNoteHandler:
    """Generate an AI draft SOAP note from existing encounter data.

    Reads vitals + diagnoses from the read model (encounter_summaries is
    already projected; raw vitals come from the event store snapshot).
    Stores the suggestion in ai_suggestions for audit.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker,
        copilot: ClinicalCopilotPort,
    ) -> None:
        self._session_factory = session_factory
        self._copilot = copilot

    async def handle(self, cmd: DraftSOAPNoteCommand) -> dict:
        from clinical.infrastructure.orm import EventStoreRecord
        from sqlalchemy import select as sa_select

        async with self._session_factory() as session:
            # Fetch encounter events to extract vitals + complaint
            rows = (await session.execute(
                sa_select(EventStoreRecord)
                .where(EventStoreRecord.aggregate_id == cmd.encounter_id.value)
                .order_by(EventStoreRecord.sequence)
            )).scalars().all()

        if not rows:
            raise NotFound(f"Encounter {cmd.encounter_id} not found")

        # Extract presenting complaint from the first SOAP note (subjective),
        # or fall back to the encounter's presenting details if none yet.
        vitals: dict = {}
        diagnoses: list[str] = []
        complaint = "General consultation"

        for row in rows:
            et = row.event_type
            if et == "clinical.encounter.vital_signs_recorded.v1":
                vitals.update({
                    k: v for k, v in row.payload.items()
                    if k not in ("recorded_by",) and v is not None
                })
            elif et == "clinical.encounter.soap_note_added.v1":
                # Use the most recent subjective as the complaint
                complaint = row.payload.get("subjective", complaint)
            elif et == "clinical.encounter.diagnosis_recorded.v1":
                desc = row.payload.get("description", "")
                code = row.payload.get("icd10_code", {})
                if isinstance(code, dict):
                    code = code.get("code", "")
                diagnoses.append(f"{code} {desc}".strip())

        suggestion: AISuggestion = await self._copilot.draft_soap_note(
            presenting_complaint=complaint,
            vitals=vitals,
            existing_diagnoses=diagnoses or None,
        )

        record = AISuggestionRecord(
            id=uuid.uuid4(),
            encounter_id=cmd.encounter_id.value,
            suggestion_type="soap_draft",
            model_id=suggestion.model_id,
            prompt_summary=f"complaint={complaint!r}; vitals={list(vitals.keys())}",
            suggestion_text=suggestion.text,
            requested_by=cmd.requested_by,
            requested_at=suggestion.generated_at,
        )
        async with self._session_factory() as session:
            session.add(record)
            await session.commit()

        return {
            "suggestion_id": str(record.id),
            "suggestion_text": suggestion.text,
            "model_id": suggestion.model_id,
            "generated_at": suggestion.generated_at.isoformat(),
            "disclaimer": suggestion.disclaimer,
        }


class ExplainDrugSafetyHandler:
    """Generate a clinician-readable drug-safety narrative from spec failures."""

    def __init__(
        self,
        session_factory: async_sessionmaker,
        copilot: ClinicalCopilotPort,
    ) -> None:
        self._session_factory = session_factory
        self._copilot = copilot

    async def handle(self, cmd: ExplainDrugSafetyCommand) -> dict:
        suggestion: AISuggestion = await self._copilot.explain_drug_safety(
            drug_names=cmd.drug_names,
            spec_failure_reasons=cmd.spec_failure_reasons,
        )

        record = AISuggestionRecord(
            id=uuid.uuid4(),
            encounter_id=cmd.encounter_id.value,
            suggestion_type="drug_safety",
            model_id=suggestion.model_id,
            prompt_summary=f"drugs={cmd.drug_names}; reasons={cmd.spec_failure_reasons}",
            suggestion_text=suggestion.text,
            requested_by=cmd.requested_by,
            requested_at=suggestion.generated_at,
        )
        async with self._session_factory() as session:
            session.add(record)
            await session.commit()

        return {
            "suggestion_id": str(record.id),
            "suggestion_text": suggestion.text,
            "model_id": suggestion.model_id,
            "generated_at": suggestion.generated_at.isoformat(),
            "disclaimer": suggestion.disclaimer,
        }


class RecordAIDecisionHandler:
    """Record a clinician's accept/discard decision for an AI suggestion."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def handle(self, cmd: RecordAIDecisionCommand) -> None:
        async with self._session_factory() as session:
            row = await session.get(AISuggestionRecord, cmd.suggestion_id)
            if row is None:
                raise NotFound(f"AI suggestion {cmd.suggestion_id} not found")
            row.decision = cmd.decision
            row.decided_by = cmd.decided_by
            row.decided_at = datetime.now(UTC)
            await session.commit()
