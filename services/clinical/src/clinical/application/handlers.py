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

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel.domain.exceptions import NotFound
from shared_kernel.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork

from clinical.application.commands import (
    AddSOAPNoteCommand,
    CloseEncounterCommand,
    IssuePrescriptionCommand,
    PlaceLabOrderCommand,
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
