"""Pharmacy application-layer commands."""

from __future__ import annotations

from pydantic import BaseModel

from shared_kernel.types.identifiers import PrescriptionId


class DispensePrescriptionCommand(BaseModel):
    prescription_id: PrescriptionId
    dispensed_by: str


class DispensePartialCommand(BaseModel):
    prescription_id: PrescriptionId
    dispensed_line_names: list[str]
    dispensed_by: str


class RejectPrescriptionCommand(BaseModel):
    """Manually reject a prescription (e.g. pharmacist override after advisory)."""
    prescription_id: PrescriptionId
    reasons: list[str]
    rejected_by: str
