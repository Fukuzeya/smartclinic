"""Clinical application-layer commands (write side)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from shared_kernel.types.identifiers import EncounterId


class StartEncounterCommand(BaseModel):
    encounter_id: EncounterId
    patient_id: str
    doctor_id: str
    appointment_id: str | None = None
    started_by: str           # Keycloak subject of the doctor


class RecordVitalSignsCommand(BaseModel):
    encounter_id: EncounterId
    temperature_celsius: Decimal | None = None
    systolic_bp_mmhg: int | None = None
    diastolic_bp_mmhg: int | None = None
    pulse_bpm: int | None = None
    respiratory_rate_rpm: int | None = None
    oxygen_saturation_pct: Decimal | None = None
    weight_kg: Decimal | None = None
    height_cm: Decimal | None = None
    recorded_by: str


class AddSOAPNoteCommand(BaseModel):
    encounter_id: EncounterId
    subjective: str
    objective: str
    assessment: str
    plan: str
    authored_by: str


class RecordDiagnosisCommand(BaseModel):
    encounter_id: EncounterId
    icd10_code: str
    description: str
    is_primary: bool = False
    recorded_by: str


class IssuePrescriptionCommand(BaseModel):
    encounter_id: EncounterId
    prescription_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    lines: list[PrescriptionLineInput]
    issued_by: str


class PrescriptionLineInput(BaseModel):
    drug_name: str
    dose: str
    route: str
    frequency: str
    duration_days: int
    instructions: str | None = None


class PlaceLabOrderCommand(BaseModel):
    encounter_id: EncounterId
    lab_order_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tests: list[LabOrderLineInput]
    ordered_by: str


class LabOrderLineInput(BaseModel):
    test_code: str
    urgency: str = "routine"
    notes: str | None = None


class CloseEncounterCommand(BaseModel):
    encounter_id: EncounterId
    closed_by: str


class VoidEncounterCommand(BaseModel):
    encounter_id: EncounterId
    reason: str
    voided_by: str


class DraftSOAPNoteCommand(BaseModel):
    encounter_id: EncounterId
    requested_by: str


class ExplainDrugSafetyCommand(BaseModel):
    encounter_id: EncounterId
    drug_names: list[str]
    spec_failure_reasons: list[str]
    requested_by: str


class RecordAIDecisionCommand(BaseModel):
    suggestion_id: uuid.UUID
    decision: str   # "accepted" | "discarded"
    decided_by: str
