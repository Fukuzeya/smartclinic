"""Clinical bounded context — Encounter aggregate root (Event Sourced).

The ``Encounter`` is the central aggregate of the Clinical context.  It
represents one patient–doctor consultation from the moment the doctor opens
the encounter until it is formally closed.

**Event sourcing means there is no ``encounters`` state table.**  The aggregate
state is fully derived by replaying the event stream from
``clinical_events`` (see ``infrastructure/event_store.py``).  This gives us:

* Medico-legal audit: every change is an immutable, hash-chained fact.
* Temporal queries: "what did the record look like at 14:32?" is a free
  by-product of replaying only events up to that timestamp.
* Tamper evidence: the chain hash proves the event stream has not been
  silently modified (ADR 0012).

State is reconstructed by dispatching each event to the corresponding
``_apply_*`` method via :class:`EventSourcedAggregateRoot._dispatch_apply`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Sequence

from shared_kernel.domain.event_sourced_aggregate import EventSourcedAggregateRoot
from shared_kernel.domain.exceptions import (
    InvariantViolation,
    NotFound,
    PreconditionFailed,
)
from shared_kernel.types.identifiers import EncounterId

from clinical.domain.events import (
    DiagnosisRecordedV1,
    EncounterClosedV1,
    EncounterStartedV1,
    EncounterVoidedV1,
    LabOrderPlacedV1,
    PrescriptionIssuedV1,
    SOAPNoteAddedV1,
    VitalSignsRecordedV1,
)
from clinical.domain.value_objects import (
    ClinicalStatus,
    Diagnosis,
    LabOrderLine,
    PrescriptionLine,
    SOAPNote,
    VitalSigns,
)


class Encounter(EventSourcedAggregateRoot[EncounterId]):
    """A patient consultation — the consistency boundary for all clinical data.

    Create via :meth:`start` (new encounter) or :meth:`rehydrate` (from event
    store).  Never construct directly.

    State rules enforced:
    * Vital signs, notes, diagnoses, prescriptions can only be added while the
      encounter is ``IN_PROGRESS``.
    * Closing requires at least one diagnosis to be recorded (clinical safety).
    * A closed or voided encounter cannot be re-opened.
    """

    # ------------------------------------------------------------------ factory

    @classmethod
    def start(
        cls,
        *,
        encounter_id: EncounterId,
        patient_id: str,
        doctor_id: str,
        appointment_id: str | None,
        started_by: str,
        clock: datetime | None = None,
    ) -> Encounter:
        """Open a new encounter.  Emits :class:`EncounterStartedV1`."""
        now = clock or datetime.now(UTC)
        instance = cls.__new__(cls)
        # Initialise base-class fields manually (no __init__ call so we don't
        # accidentally trigger any subclass logic).
        from shared_kernel.domain.entity import Entity
        from shared_kernel.domain.aggregate_root import AggregateRoot
        Entity.__init__(instance, id=encounter_id)
        instance._version = 0
        instance._pending_events = []
        # Domain state — safe defaults before first apply
        instance._status: ClinicalStatus | None = None
        instance._patient_id: str = ""
        instance._doctor_id: str = ""
        instance._appointment_id: str | None = None
        instance._started_at: datetime | None = None
        instance._closed_at: datetime | None = None
        instance._vital_signs: list[VitalSigns] = []
        instance._soap_notes: list[SOAPNote] = []
        instance._diagnoses: list[Diagnosis] = []
        instance._prescriptions: list[list[PrescriptionLine]] = []
        instance._lab_orders: list[list[LabOrderLine]] = []

        event = EncounterStartedV1.build(
            encounter_id=uuid.UUID(str(encounter_id)),
            aggregate_version=instance._next_version(),
            patient_id=patient_id,
            doctor_id=doctor_id,
            appointment_id=appointment_id,
            started_by=started_by,
        )
        instance._record_and_apply(event)
        return instance

    @classmethod
    def rehydrate(
        cls,
        *,
        encounter_id: EncounterId,
        events: Sequence[object],
    ) -> Encounter:
        """Rebuild an encounter by replaying its persisted event stream."""
        if not events:
            raise InvariantViolation("Cannot rehydrate Encounter from empty event stream")

        from shared_kernel.domain.entity import Entity
        instance = cls.__new__(cls)
        Entity.__init__(instance, id=encounter_id)
        instance._version = 0
        instance._pending_events = []
        instance._status = None
        instance._patient_id = ""
        instance._doctor_id = ""
        instance._appointment_id = None
        instance._started_at = None
        instance._closed_at = None
        instance._vital_signs = []
        instance._soap_notes = []
        instance._diagnoses = []
        instance._prescriptions = []
        instance._lab_orders = []

        instance._replay(events)  # type: ignore[arg-type]
        return instance

    # ------------------------------------------------------------------ commands

    def record_vital_signs(self, *, vitals: VitalSigns) -> None:
        """Record a set of vital-sign observations."""
        self._assert_in_progress()
        event = VitalSignsRecordedV1.build(
            encounter_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            vitals_payload=vitals.model_dump(mode="json"),
        )
        self._record_and_apply(event)

    def add_soap_note(self, *, note: SOAPNote) -> None:
        """Append a structured SOAP note."""
        self._assert_in_progress()
        event = SOAPNoteAddedV1.build(
            encounter_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            note_payload=note.model_dump(mode="json"),
        )
        self._record_and_apply(event)

    def record_diagnosis(self, *, diagnosis: Diagnosis) -> None:
        """Add a diagnosis.  Multiple diagnoses allowed; only one may be primary."""
        self._assert_in_progress()
        if diagnosis.is_primary:
            existing_primary = next(
                (d for d in self._diagnoses if d.is_primary), None
            )
            if existing_primary is not None:
                raise InvariantViolation(
                    f"A primary diagnosis ({existing_primary.icd10_code.code}) is "
                    "already recorded. Demote it first before marking a new primary."
                )
        event = DiagnosisRecordedV1.build(
            encounter_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            diagnosis_payload=diagnosis.model_dump(mode="json"),
        )
        self._record_and_apply(event)

    def issue_prescription(
        self,
        *,
        prescription_id: uuid.UUID,
        lines: list[PrescriptionLine],
        issued_by: str,
    ) -> None:
        """Issue a multi-line prescription."""
        self._assert_in_progress()
        if not lines:
            raise InvariantViolation("A prescription must have at least one drug line")
        event = PrescriptionIssuedV1.build(
            encounter_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            prescription_id=prescription_id,
            lines_payload=[ln.model_dump(mode="json") for ln in lines],
            issued_by=issued_by,
        )
        self._record_and_apply(event)

    def place_lab_order(
        self,
        *,
        lab_order_id: uuid.UUID,
        tests: list[LabOrderLine],
        ordered_by: str,
    ) -> None:
        """Place a laboratory order."""
        self._assert_in_progress()
        if not tests:
            raise InvariantViolation("A lab order must request at least one test")
        event = LabOrderPlacedV1.build(
            encounter_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            lab_order_id=lab_order_id,
            tests_payload=[t.model_dump(mode="json") for t in tests],
            ordered_by=ordered_by,
        )
        self._record_and_apply(event)

    def close(self, *, closed_by: str) -> None:
        """Close the encounter.  Requires at least one diagnosis to be recorded."""
        self._assert_in_progress()
        if not self._diagnoses:
            raise InvariantViolation(
                "Cannot close an encounter without at least one recorded diagnosis. "
                "A working diagnosis (e.g. Z00.0 — routine health check) is required."
            )
        primary = next((d for d in self._diagnoses if d.is_primary), None)
        event = EncounterClosedV1.build(
            encounter_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            patient_id=self._patient_id,
            doctor_id=self._doctor_id,
            primary_icd10=primary.icd10_code.code if primary else None,
            has_prescription=bool(self._prescriptions),
            has_lab_order=bool(self._lab_orders),
            closed_by=closed_by,
        )
        self._record_and_apply(event)

    def void(self, *, reason: str, voided_by: str) -> None:
        """Administratively void an in-progress encounter (e.g. wrong patient)."""
        if self._status == ClinicalStatus.CLOSED:
            raise PreconditionFailed("A closed encounter cannot be voided.")
        if self._status == ClinicalStatus.VOIDED:
            raise PreconditionFailed("Encounter is already voided.")
        event = EncounterVoidedV1.build(
            encounter_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            reason=reason,
            voided_by=voided_by,
        )
        self._record_and_apply(event)

    # ------------------------------------------------------------------ projections (read from state)

    @property
    def status(self) -> ClinicalStatus:
        return self._status  # type: ignore[return-value]

    @property
    def patient_id(self) -> str:
        return self._patient_id

    @property
    def doctor_id(self) -> str:
        return self._doctor_id

    @property
    def diagnoses(self) -> tuple[Diagnosis, ...]:
        return tuple(self._diagnoses)

    @property
    def vital_signs(self) -> tuple[VitalSigns, ...]:
        return tuple(self._vital_signs)

    @property
    def soap_notes(self) -> tuple[SOAPNote, ...]:
        return tuple(self._soap_notes)

    # ------------------------------------------------------------------ apply methods

    def _apply_encounter_started_v1(self, event: EncounterStartedV1) -> None:
        p = event.payload
        self._status = ClinicalStatus.IN_PROGRESS
        self._patient_id = p["patient_id"]
        self._doctor_id = p["doctor_id"]
        self._appointment_id = p.get("appointment_id")
        self._started_at = event.occurred_at

    def _apply_vital_signs_recorded_v1(self, event: VitalSignsRecordedV1) -> None:
        self._vital_signs.append(VitalSigns.model_validate(event.payload))

    def _apply_soap_note_added_v1(self, event: SOAPNoteAddedV1) -> None:
        self._soap_notes.append(SOAPNote.model_validate(event.payload))

    def _apply_diagnosis_recorded_v1(self, event: DiagnosisRecordedV1) -> None:
        self._diagnoses.append(Diagnosis.model_validate(event.payload))

    def _apply_prescription_issued_v1(self, event: PrescriptionIssuedV1) -> None:
        lines = [PrescriptionLine.model_validate(ln) for ln in event.payload["lines"]]
        self._prescriptions.append(lines)

    def _apply_lab_order_placed_v1(self, event: LabOrderPlacedV1) -> None:
        tests = [LabOrderLine.model_validate(t) for t in event.payload["tests"]]
        self._lab_orders.append(tests)

    def _apply_encounter_closed_v1(self, event: EncounterClosedV1) -> None:
        self._status = ClinicalStatus.CLOSED
        self._closed_at = event.occurred_at

    def _apply_encounter_voided_v1(self, event: EncounterVoidedV1) -> None:
        self._status = ClinicalStatus.VOIDED

    # ------------------------------------------------------------------ helpers

    def _next_version(self) -> int:
        return self._version + len(self._pending_events) + 1

    def _assert_in_progress(self) -> None:
        if self._status != ClinicalStatus.IN_PROGRESS:
            raise PreconditionFailed(
                f"Encounter is {self._status}; only in-progress encounters can be modified."
            )
