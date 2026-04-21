"""Domain tests for the Encounter aggregate.

These are pure unit tests — no I/O, no framework.  They verify:
* The state machine guards illegal transitions.
* Events are recorded with correct payloads and version stamps.
* Rehydration produces identical state to the original aggregate.
* Business invariants (one primary diagnosis, at least one line per
  prescription, etc.) are enforced.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from shared_kernel.domain.exceptions import InvariantViolation, PreconditionFailed
from shared_kernel.types.identifiers import EncounterId

from clinical.domain.encounter import Encounter
from clinical.domain.events import (
    DiagnosisRecordedV1,
    EncounterClosedV1,
    EncounterStartedV1,
)
from clinical.domain.value_objects import (
    ClinicalStatus,
    Diagnosis,
    ICD10Code,
    LabOrderLine,
    PrescriptionLine,
    SOAPNote,
    VitalSigns,
)

# ---------------------------------------------------------------------------
# Fixtures

ENC_ID = EncounterId.new()
PATIENT_ID = "pat_" + str(uuid.uuid4())
DOCTOR_ID = "doc_" + str(uuid.uuid4())


def make_encounter() -> Encounter:
    return Encounter.start(
        encounter_id=ENC_ID,
        patient_id=PATIENT_ID,
        doctor_id=DOCTOR_ID,
        appointment_id=None,
        started_by=DOCTOR_ID,
    )


def primary_diagnosis() -> Diagnosis:
    return Diagnosis(
        icd10_code=ICD10Code(code="J18.9"),
        description="Pneumonia, unspecified",
        is_primary=True,
        recorded_by=DOCTOR_ID,
    )


# ---------------------------------------------------------------------------
# Start

class TestStartEncounter:
    def test_status_is_in_progress(self):
        enc = make_encounter()
        assert enc.status == ClinicalStatus.IN_PROGRESS

    def test_emits_encounter_started_event(self):
        enc = make_encounter()
        events = enc.peek_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], EncounterStartedV1)

    def test_event_payload_contains_patient_and_doctor(self):
        enc = make_encounter()
        payload = enc.peek_domain_events()[0].payload
        assert payload["patient_id"] == PATIENT_ID
        assert payload["doctor_id"] == DOCTOR_ID

    def test_first_event_has_version_1(self):
        enc = make_encounter()
        assert enc.peek_domain_events()[0].aggregate_version == 1

    def test_patient_id_accessible(self):
        enc = make_encounter()
        assert enc.patient_id == PATIENT_ID

    def test_doctor_id_accessible(self):
        enc = make_encounter()
        assert enc.doctor_id == DOCTOR_ID


# ---------------------------------------------------------------------------
# Vital signs

class TestRecordVitalSigns:
    def test_adds_vital_signs_to_state(self):
        enc = make_encounter()
        enc.pull_domain_events()  # clear start event
        vitals = VitalSigns(temperature_celsius=Decimal("37.2"), pulse_bpm=72, recorded_by=DOCTOR_ID)
        enc.record_vital_signs(vitals=vitals)
        assert len(enc.vital_signs) == 1

    def test_cannot_record_on_closed_encounter(self):
        enc = make_encounter()
        enc.pull_domain_events()
        enc.record_diagnosis(diagnosis=primary_diagnosis())
        enc.pull_domain_events()
        enc.close(closed_by=DOCTOR_ID)
        vitals = VitalSigns(pulse_bpm=72, recorded_by=DOCTOR_ID)
        with pytest.raises(PreconditionFailed):
            enc.record_vital_signs(vitals=vitals)

    def test_at_least_one_measurement_required(self):
        with pytest.raises(Exception):  # Pydantic validation
            VitalSigns(recorded_by=DOCTOR_ID)

    def test_temperature_out_of_range_rejected(self):
        with pytest.raises(Exception):
            VitalSigns(temperature_celsius=Decimal("70"), recorded_by=DOCTOR_ID)


# ---------------------------------------------------------------------------
# SOAP notes

class TestSOAPNote:
    def test_adds_soap_note(self):
        enc = make_encounter()
        enc.pull_domain_events()
        note = SOAPNote(
            subjective="Chest pain for 2 days",
            objective="Temp 38.5, SpO2 94%, decreased breath sounds on left",
            assessment="Likely community-acquired pneumonia",
            plan="Amoxicillin 500mg TDS x 7 days; chest X-ray; follow-up in 3 days",
            authored_by=DOCTOR_ID,
        )
        enc.add_soap_note(note=note)
        assert len(enc.soap_notes) == 1

    def test_multiple_notes_allowed(self):
        enc = make_encounter()
        enc.pull_domain_events()
        note = SOAPNote(
            subjective="s", objective="o", assessment="a", plan="p", authored_by=DOCTOR_ID
        )
        enc.add_soap_note(note=note)
        enc.add_soap_note(note=note)
        assert len(enc.soap_notes) == 2


# ---------------------------------------------------------------------------
# Diagnosis

class TestRecordDiagnosis:
    def test_records_diagnosis(self):
        enc = make_encounter()
        enc.pull_domain_events()
        enc.record_diagnosis(diagnosis=primary_diagnosis())
        assert len(enc.diagnoses) == 1

    def test_only_one_primary_diagnosis_allowed(self):
        enc = make_encounter()
        enc.pull_domain_events()
        enc.record_diagnosis(diagnosis=primary_diagnosis())
        enc.pull_domain_events()
        second_primary = Diagnosis(
            icd10_code=ICD10Code(code="J06.9"),
            description="Acute upper respiratory infection",
            is_primary=True,
            recorded_by=DOCTOR_ID,
        )
        with pytest.raises(InvariantViolation, match="primary diagnosis"):
            enc.record_diagnosis(diagnosis=second_primary)

    def test_multiple_non_primary_diagnoses_allowed(self):
        enc = make_encounter()
        enc.pull_domain_events()
        secondary = Diagnosis(
            icd10_code=ICD10Code(code="E11.9"),
            description="Type 2 diabetes mellitus",
            is_primary=False,
            recorded_by=DOCTOR_ID,
        )
        enc.record_diagnosis(diagnosis=secondary)
        enc.pull_domain_events()
        enc.record_diagnosis(diagnosis=secondary)
        assert len(enc.diagnoses) == 2

    def test_invalid_icd10_code_rejected(self):
        with pytest.raises(Exception):
            ICD10Code(code="NOTVALID")


# ---------------------------------------------------------------------------
# Prescription

class TestIssuePrescription:
    def test_issues_prescription(self):
        enc = make_encounter()
        enc.pull_domain_events()
        lines = [PrescriptionLine(
            drug_name="Amoxicillin", dose="500mg", route="oral",
            frequency="TDS", duration_days=7,
        )]
        enc.issue_prescription(
            prescription_id=uuid.uuid4(), lines=lines, issued_by=DOCTOR_ID
        )
        events = enc.peek_domain_events()
        assert events[-1].payload["lines"][0]["drug_name"] == "Amoxicillin"

    def test_empty_prescription_rejected(self):
        enc = make_encounter()
        enc.pull_domain_events()
        with pytest.raises(InvariantViolation, match="at least one drug line"):
            enc.issue_prescription(
                prescription_id=uuid.uuid4(), lines=[], issued_by=DOCTOR_ID
            )


# ---------------------------------------------------------------------------
# Close

class TestCloseEncounter:
    def test_close_requires_diagnosis(self):
        enc = make_encounter()
        enc.pull_domain_events()
        with pytest.raises(InvariantViolation, match="diagnosis"):
            enc.close(closed_by=DOCTOR_ID)

    def test_close_succeeds_with_diagnosis(self):
        enc = make_encounter()
        enc.pull_domain_events()
        enc.record_diagnosis(diagnosis=primary_diagnosis())
        enc.pull_domain_events()
        enc.close(closed_by=DOCTOR_ID)
        assert enc.status == ClinicalStatus.CLOSED

    def test_closed_encounter_cannot_be_closed_again(self):
        enc = make_encounter()
        enc.pull_domain_events()
        enc.record_diagnosis(diagnosis=primary_diagnosis())
        enc.pull_domain_events()
        enc.close(closed_by=DOCTOR_ID)
        enc.pull_domain_events()
        with pytest.raises(PreconditionFailed):
            enc.close(closed_by=DOCTOR_ID)

    def test_close_event_includes_primary_icd10(self):
        enc = make_encounter()
        enc.pull_domain_events()
        enc.record_diagnosis(diagnosis=primary_diagnosis())
        enc.pull_domain_events()
        enc.close(closed_by=DOCTOR_ID)
        close_event = enc.peek_domain_events()[0]
        assert isinstance(close_event, EncounterClosedV1)
        assert close_event.payload["primary_icd10"] == "J18.9"


# ---------------------------------------------------------------------------
# Void

class TestVoidEncounter:
    def test_void_in_progress_encounter(self):
        enc = make_encounter()
        enc.pull_domain_events()
        enc.void(reason="Wrong patient entered", voided_by=DOCTOR_ID)
        assert enc.status == ClinicalStatus.VOIDED

    def test_cannot_void_closed_encounter(self):
        enc = make_encounter()
        enc.pull_domain_events()
        enc.record_diagnosis(diagnosis=primary_diagnosis())
        enc.pull_domain_events()
        enc.close(closed_by=DOCTOR_ID)
        enc.pull_domain_events()
        with pytest.raises(PreconditionFailed, match="closed"):
            enc.void(reason="Test", voided_by=DOCTOR_ID)


# ---------------------------------------------------------------------------
# Version stamping

class TestVersionStamping:
    def test_each_event_version_increments(self):
        enc = make_encounter()
        enc.pull_domain_events()
        enc.record_diagnosis(diagnosis=primary_diagnosis())
        enc.pull_domain_events()
        enc.close(closed_by=DOCTOR_ID)
        events = enc.peek_domain_events()
        # After start (v1) and diagnosis (v2), close should be v3
        assert events[0].aggregate_version == 3

    def test_version_accounts_for_pending_events(self):
        enc = make_encounter()
        # start event is pending (v1), next should be v2
        enc.record_diagnosis(diagnosis=primary_diagnosis())
        events = enc.peek_domain_events()
        assert events[0].aggregate_version == 1   # start
        assert events[1].aggregate_version == 2   # diagnosis


# ---------------------------------------------------------------------------
# Rehydration

class TestRehydration:
    def test_rehydrate_produces_correct_status(self):
        original = make_encounter()
        events = original.pull_domain_events()
        rehydrated = Encounter.rehydrate(encounter_id=ENC_ID, events=events)
        assert rehydrated.status == ClinicalStatus.IN_PROGRESS

    def test_rehydrate_reproduces_diagnoses(self):
        original = make_encounter()
        original.record_diagnosis(diagnosis=primary_diagnosis())
        events = original.pull_domain_events()
        rehydrated = Encounter.rehydrate(encounter_id=ENC_ID, events=events)
        assert len(rehydrated.diagnoses) == 1
        assert rehydrated.diagnoses[0].icd10_code.code == "J18.9"

    def test_rehydrate_sets_correct_version(self):
        original = make_encounter()
        original.record_diagnosis(diagnosis=primary_diagnosis())
        original.close(closed_by=DOCTOR_ID)
        events = original.pull_domain_events()
        # Simulate UoW bump: set version on events
        rehydrated = Encounter.rehydrate(encounter_id=ENC_ID, events=events)
        assert rehydrated.version == events[-1].aggregate_version

    def test_rehydrate_from_empty_stream_raises(self):
        with pytest.raises(InvariantViolation, match="empty"):
            Encounter.rehydrate(encounter_id=ENC_ID, events=[])

    def test_rehydrated_encounter_produces_no_pending_events(self):
        original = make_encounter()
        events = original.pull_domain_events()
        rehydrated = Encounter.rehydrate(encounter_id=ENC_ID, events=events)
        assert not rehydrated.has_pending_events()
