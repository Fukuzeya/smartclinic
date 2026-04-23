"""Clinical bounded context — value objects.

All VOs are frozen Pydantic models (identity-by-value, immutable).
Medical domain rules are encoded as validators rather than scattered
across handlers (ubiquitous language principle).
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from shared_kernel.domain.value_object import ValueObject


# ---------------------------------------------------------------------------
# Status

class ClinicalStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"
    VOIDED = "voided"


# ---------------------------------------------------------------------------
# ICD-10 code

class ICD10Code(ValueObject):
    """Validated ICD-10-CM code (letter + 2 digits + optional decimal refinement).

    Validates the canonical format (e.g. A00, J18.9, K21.0) but does *not*
    perform a database lookup — the ACL to the external code-table handles
    that validation in the Pharmacy context.
    """

    code: Annotated[str, Field(min_length=3, max_length=8)]

    @field_validator("code")
    @classmethod
    def _valid_format(cls, v: str) -> str:
        import re
        if not re.match(r"^[A-Z][0-9]{2}(\.[0-9A-Z]{1,4})?$", v.upper()):
            raise ValueError(f"'{v}' is not a valid ICD-10 code (e.g. J18.9)")
        return v.upper()


# ---------------------------------------------------------------------------
# Vital signs

class VitalSigns(ValueObject):
    """One set of observations recorded at a point in time during an encounter.

    All fields are optional because not every consultation measures every
    vital — e.g. a phone follow-up may only record weight.  At least one
    measurement must be present (enforced by the model validator).
    """

    temperature_celsius: Decimal | None = None      # normal: 36.1–37.2
    systolic_bp_mmhg: int | None = None             # normal: 90–140
    diastolic_bp_mmhg: int | None = None            # normal: 60–90
    pulse_bpm: int | None = None                     # normal: 60–100
    respiratory_rate_rpm: int | None = None          # normal: 12–20
    oxygen_saturation_pct: Decimal | None = None    # normal: ≥95
    weight_kg: Decimal | None = None
    height_cm: Decimal | None = None
    recorded_by: str                                  # Keycloak subject

    # Domain events persist vitals as JSON; Decimal fields round-trip through
    # strings. Strict mode rejects the coercion, so coerce pre-validate.
    @field_validator(
        "temperature_celsius",
        "oxygen_saturation_pct",
        "weight_kg",
        "height_cm",
        mode="before",
    )
    @classmethod
    def _coerce_decimal(cls, v: object) -> object:
        if isinstance(v, (str, int, float)):
            return Decimal(str(v))
        return v

    @model_validator(mode="after")
    def _at_least_one_measurement(self) -> VitalSigns:
        measurements = [
            self.temperature_celsius, self.systolic_bp_mmhg,
            self.diastolic_bp_mmhg, self.pulse_bpm,
            self.respiratory_rate_rpm, self.oxygen_saturation_pct,
            self.weight_kg, self.height_cm,
        ]
        if all(m is None for m in measurements):
            raise ValueError("At least one vital-sign measurement is required")
        return self

    @field_validator("temperature_celsius")
    @classmethod
    def _temp_range(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and not (Decimal("25") <= v <= Decimal("45")):
            raise ValueError(f"Temperature {v}°C is outside the plausible range (25–45)")
        return v

    @field_validator("oxygen_saturation_pct")
    @classmethod
    def _spo2_range(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and not (Decimal("0") <= v <= Decimal("100")):
            raise ValueError("SpO₂ must be 0–100 %")
        return v


# ---------------------------------------------------------------------------
# SOAP note

class SOAPNote(ValueObject):
    """Structured clinical note following the SOAP format (standard in ZW clinics)."""

    subjective: str = Field(min_length=1)   # patient's chief complaint in their own words
    objective: str = Field(min_length=1)    # clinician's findings / exam results
    assessment: str = Field(min_length=1)   # working / differential diagnosis
    plan: str = Field(min_length=1)         # treatment plan, referrals, follow-up
    authored_by: str                         # Keycloak subject of the authoring clinician


# ---------------------------------------------------------------------------
# Diagnosis

class Diagnosis(ValueObject):
    """A single diagnosis linked to an ICD-10 code."""

    icd10_code: ICD10Code
    description: str = Field(min_length=1, max_length=500)
    is_primary: bool = False
    recorded_by: str


# ---------------------------------------------------------------------------
# Prescription line

class PrescriptionLine(ValueObject):
    """One drug line within a prescription issued during an encounter."""

    drug_name: str = Field(min_length=1, max_length=200)
    dose: str = Field(min_length=1)        # e.g. "500mg"
    route: str = Field(min_length=1)       # e.g. "oral", "IV"
    frequency: str = Field(min_length=1)  # e.g. "TDS", "BD"
    duration_days: int = Field(ge=1, le=365)
    instructions: str | None = None


# ---------------------------------------------------------------------------
# Lab order

class LabOrderLine(ValueObject):
    """One test requested in a laboratory order from an encounter."""

    test_code: str = Field(min_length=1, max_length=50)   # e.g. "FBC", "LFT", "HbA1c"
    urgency: str = Field(pattern=r"^(routine|urgent|stat)$")
    notes: str | None = None
