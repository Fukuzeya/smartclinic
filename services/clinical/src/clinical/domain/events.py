"""Clinical bounded context — domain events.

All events carry ``aggregate_type = "Encounter"`` and are versioned with a
``.v1`` suffix so the event bus can evolve schemas without flag-day migrations.

Payload design rules:
* Include only what downstream contexts need — not a full aggregate dump.
* PII kept to a minimum: patient_id (a UUID reference) is acceptable; names,
  diagnoses, and drug names stay in the Clinical write DB.
* ``EncounterClosedV1`` is the boundary at which the Pharmacy context acts
  (prescription fulfilment) and the Billing context raises an invoice trigger.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from pydantic import Field

from shared_kernel.domain.domain_event import DomainEvent


class ClinicalEvent(DomainEvent):
    """Marker base for all Clinical bounded-context events."""

    aggregate_type: str = Field(default="Encounter")


# ---------------------------------------------------------------------------
# Write-side events (used internally for event sourcing)

class EncounterStartedV1(ClinicalEvent):
    event_type: str = Field(default="clinical.encounter.started.v1")

    @classmethod
    def build(
        cls,
        *,
        encounter_id: uuid.UUID,
        aggregate_version: int,
        patient_id: str,
        doctor_id: str,
        appointment_id: str | None,
        started_by: str,
        trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> EncounterStartedV1:
        return cls(
            aggregate_id=str(encounter_id),
            aggregate_version=aggregate_version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            payload={
                "patient_id": patient_id,
                "doctor_id": doctor_id,
                "appointment_id": appointment_id,
                "started_by": started_by,
            },
        )


class VitalSignsRecordedV1(ClinicalEvent):
    event_type: str = Field(default="clinical.encounter.vital_signs_recorded.v1")

    @classmethod
    def build(
        cls,
        *,
        encounter_id: uuid.UUID,
        aggregate_version: int,
        vitals_payload: dict[str, Any],
        trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> VitalSignsRecordedV1:
        return cls(
            aggregate_id=str(encounter_id),
            aggregate_version=aggregate_version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            payload=vitals_payload,
        )


class SOAPNoteAddedV1(ClinicalEvent):
    event_type: str = Field(default="clinical.encounter.soap_note_added.v1")

    @classmethod
    def build(
        cls,
        *,
        encounter_id: uuid.UUID,
        aggregate_version: int,
        note_payload: dict[str, Any],
        trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> SOAPNoteAddedV1:
        return cls(
            aggregate_id=str(encounter_id),
            aggregate_version=aggregate_version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            payload=note_payload,
        )


class DiagnosisRecordedV1(ClinicalEvent):
    event_type: str = Field(default="clinical.encounter.diagnosis_recorded.v1")

    @classmethod
    def build(
        cls,
        *,
        encounter_id: uuid.UUID,
        aggregate_version: int,
        diagnosis_payload: dict[str, Any],
        trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> DiagnosisRecordedV1:
        return cls(
            aggregate_id=str(encounter_id),
            aggregate_version=aggregate_version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            payload=diagnosis_payload,
        )


class PrescriptionIssuedV1(ClinicalEvent):
    event_type: str = Field(default="clinical.encounter.prescription_issued.v1")

    @classmethod
    def build(
        cls,
        *,
        encounter_id: uuid.UUID,
        aggregate_version: int,
        prescription_id: uuid.UUID,
        patient_id: str,
        lines_payload: list[dict[str, Any]],
        issued_by: str,
        trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> PrescriptionIssuedV1:
        return cls(
            aggregate_id=str(encounter_id),
            aggregate_version=aggregate_version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            payload={
                "prescription_id": str(prescription_id),
                "patient_id": patient_id,
                "encounter_id": str(encounter_id),
                "lines": lines_payload,
                "issued_by": issued_by,
            },
        )


class LabOrderPlacedV1(ClinicalEvent):
    event_type: str = Field(default="clinical.encounter.lab_order_placed.v1")

    @classmethod
    def build(
        cls,
        *,
        encounter_id: uuid.UUID,
        aggregate_version: int,
        lab_order_id: uuid.UUID,
        patient_id: str,
        tests_payload: list[dict[str, Any]],
        ordered_by: str,
        trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> LabOrderPlacedV1:
        return cls(
            aggregate_id=str(encounter_id),
            aggregate_version=aggregate_version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            payload={
                "lab_order_id": str(lab_order_id),
                "patient_id": patient_id,
                "encounter_id": str(encounter_id),
                "tests": tests_payload,
                "ordered_by": ordered_by,
            },
        )


class EncounterClosedV1(ClinicalEvent):
    """Published cross-context: triggers Pharmacy fulfilment + Billing invoice."""

    event_type: str = Field(default="clinical.encounter.closed.v1")

    @classmethod
    def build(
        cls,
        *,
        encounter_id: uuid.UUID,
        aggregate_version: int,
        patient_id: str,
        doctor_id: str,
        primary_icd10: str | None,
        has_prescription: bool,
        has_lab_order: bool,
        closed_by: str,
        trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> EncounterClosedV1:
        return cls(
            aggregate_id=str(encounter_id),
            aggregate_version=aggregate_version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            payload={
                "patient_id": patient_id,
                "doctor_id": doctor_id,
                "primary_icd10": primary_icd10,
                "has_prescription": has_prescription,
                "has_lab_order": has_lab_order,
                "closed_by": closed_by,
            },
        )


class EncounterVoidedV1(ClinicalEvent):
    event_type: str = Field(default="clinical.encounter.voided.v1")

    @classmethod
    def build(
        cls,
        *,
        encounter_id: uuid.UUID,
        aggregate_version: int,
        reason: str,
        voided_by: str,
        trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> EncounterVoidedV1:
        return cls(
            aggregate_id=str(encounter_id),
            aggregate_version=aggregate_version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            payload={"reason": reason, "voided_by": voided_by},
        )
