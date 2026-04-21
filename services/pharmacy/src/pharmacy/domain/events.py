"""Pharmacy domain events."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import Field

from shared_kernel.domain.domain_event import DomainEvent


class PharmacyEvent(DomainEvent):
    aggregate_type: str = Field(default="Prescription")


class PrescriptionReceivedV1(PharmacyEvent):
    """Raised when a Clinical prescription is accepted into the Pharmacy workflow."""

    event_type: str = Field(default="pharmacy.prescription.received.v1")

    @classmethod
    def build(
        cls,
        *,
        prescription_id: uuid.UUID,
        aggregate_version: int,
        patient_id: str,
        encounter_id: str,
        drug_names: list[str],
        issued_by: str,
        trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> PrescriptionReceivedV1:
        return cls(
            aggregate_id=str(prescription_id),
            aggregate_version=aggregate_version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            payload={
                "patient_id": patient_id,
                "encounter_id": encounter_id,
                "drug_names": drug_names,
                "issued_by": issued_by,
            },
        )


class DispensingCompletedV1(PharmacyEvent):
    """All lines on the prescription have been dispensed successfully."""

    event_type: str = Field(default="pharmacy.dispensing.completed.v1")

    @classmethod
    def build(
        cls,
        *,
        prescription_id: uuid.UUID,
        aggregate_version: int,
        patient_id: str,
        dispensed_by: str,
        lines_dispensed: list[dict[str, Any]],
        trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> DispensingCompletedV1:
        return cls(
            aggregate_id=str(prescription_id),
            aggregate_version=aggregate_version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            payload={
                "patient_id": patient_id,
                "dispensed_by": dispensed_by,
                "lines_dispensed": lines_dispensed,
            },
        )


class DispensingRejectedV1(PharmacyEvent):
    """Dispensing blocked by the specification chain — carries all reasons."""

    event_type: str = Field(default="pharmacy.dispensing.rejected.v1")

    @classmethod
    def build(
        cls,
        *,
        prescription_id: uuid.UUID,
        aggregate_version: int,
        patient_id: str,
        reasons: list[str],
        rejected_by: str,
        trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> DispensingRejectedV1:
        return cls(
            aggregate_id=str(prescription_id),
            aggregate_version=aggregate_version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            payload={
                "patient_id": patient_id,
                "reasons": reasons,
                "rejected_by": rejected_by,
            },
        )


class DispensingPartialV1(PharmacyEvent):
    """Some but not all lines dispensed (e.g. one drug substituted / out of stock)."""

    event_type: str = Field(default="pharmacy.dispensing.partial.v1")

    @classmethod
    def build(
        cls,
        *,
        prescription_id: uuid.UUID,
        aggregate_version: int,
        patient_id: str,
        dispensed_lines: list[dict[str, Any]],
        pending_lines: list[str],
        dispensed_by: str,
        trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> DispensingPartialV1:
        return cls(
            aggregate_id=str(prescription_id),
            aggregate_version=aggregate_version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            payload={
                "patient_id": patient_id,
                "dispensed_lines": dispensed_lines,
                "pending_lines": pending_lines,
                "dispensed_by": dispensed_by,
            },
        )
