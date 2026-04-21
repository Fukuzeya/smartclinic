"""Laboratory bounded context — value objects."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import Field, model_validator

from shared_kernel.domain.value_object import ValueObject


class OrderStatus(StrEnum):
    PENDING = "pending"               # Order received, awaiting sample
    SAMPLE_COLLECTED = "sample_collected"  # Sample taken from patient
    IN_PROGRESS = "in_progress"       # Analysing in lab
    COMPLETED = "completed"           # All results reported
    CANCELLED = "cancelled"


class SampleType(StrEnum):
    BLOOD = "blood"
    URINE = "urine"
    STOOL = "stool"
    SPUTUM = "sputum"
    SWAB = "swab"
    TISSUE = "tissue"
    CSF = "csf"     # Cerebrospinal fluid
    OTHER = "other"


class Interpretation(StrEnum):
    NORMAL = "normal"
    LOW = "low"
    HIGH = "high"
    CRITICAL_LOW = "critical_low"
    CRITICAL_HIGH = "critical_high"
    POSITIVE = "positive"       # for qualitative tests (e.g. HIV, malaria RDT)
    NEGATIVE = "negative"
    INDETERMINATE = "indeterminate"


class ReferenceRange(ValueObject):
    """Normal range for a quantitative laboratory test."""
    lower: Decimal | None = None
    upper: Decimal | None = None
    unit: str = ""
    note: str | None = None  # e.g. "Adult male reference range"

    @model_validator(mode="after")
    def _at_least_one_bound(self) -> ReferenceRange:
        if self.lower is None and self.upper is None and not self.note:
            raise ValueError("Reference range must have at least one bound or a note")
        return self


class LabResult(ValueObject):
    """One test result within a laboratory order.

    Both quantitative (e.g. Haemoglobin 12.5 g/dL) and qualitative
    (e.g. Malaria RDT: Positive) results are supported.
    """
    test_code: str = Field(min_length=1, max_length=50)
    test_name: str = Field(min_length=1, max_length=200)
    value: str                          # string covers both "12.5" and "Positive"
    unit: str | None = None
    reference_range: ReferenceRange | None = None
    interpretation: Interpretation
    notes: str | None = None
    performed_by: str                   # Keycloak subject of the lab technician

    @property
    def is_critical(self) -> bool:
        return self.interpretation in (
            Interpretation.CRITICAL_LOW, Interpretation.CRITICAL_HIGH
        )


class LabOrderLine(ValueObject):
    """One test requested in the incoming lab order (mirrors Clinical's VO)."""
    test_code: str = Field(min_length=1, max_length=50)
    urgency: str = Field(pattern=r"^(routine|urgent|stat)$")
    notes: str | None = None
