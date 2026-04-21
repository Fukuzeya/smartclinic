"""Pharmacy bounded context — value objects.

Key domain concepts in the Pharmacy context:

* **Drug** — identified by a name (free text from Clinical) and optionally
  an RxNorm CUI (populated by the ACL after lookup). Names are normalised
  to uppercase for reliable comparison.
* **StockLevel** — how much of a drug is available in the dispensary.
* **DispensingStatus** — lifecycle state of a prescription through the
  dispensing workflow.
* **DrugInteraction** — a clinically significant interaction between two
  drugs as reported by the RxNav ACL. Severity drives how the specification
  responds (SEVERE = hard block; MODERATE = soft block / warning).
* **DispensableCandidate** — the VO checked against all specifications.
  It is constructed from Prescription state + external lookups and is the
  single object that flows through the composed specification chain.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import Field, field_validator

from shared_kernel.domain.value_object import ValueObject


class DispensingStatus(StrEnum):
    PENDING = "pending"           # Awaiting pharmacist action
    DISPENSED = "dispensed"       # All lines successfully dispensed
    PARTIAL = "partial"           # Some lines dispensed (e.g. one drug out of stock)
    REJECTED = "rejected"         # Specification failure — not safe to dispense
    CANCELLED = "cancelled"       # Cancelled by receptionist / doctor


class InteractionSeverity(StrEnum):
    SEVERE = "severe"         # Hard block — must not dispense
    MODERATE = "moderate"     # Soft block — pharmacist override required
    MINOR = "minor"           # Warning — dispense with counselling note


class Drug(ValueObject):
    """A drug identified by name within the Pharmacy context.

    The name is normalised to UPPERCASE on validation so that comparisons
    between Clinical's free-text drug name ("amoxicillin") and RxNav's
    canonical form ("AMOXICILLIN") succeed without fragile case handling
    scattered through the domain.
    """

    name: Annotated[str, Field(min_length=1, max_length=200)]
    rxcui: str | None = None  # Populated by ACL after RxNorm lookup

    @field_validator("name")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return v.strip().upper()


class StockLevel(ValueObject):
    """Current stock of one drug at the dispensary."""

    drug_name: str
    quantity_on_hand: Decimal = Field(ge=Decimal("0"))
    unit: str = "tablets"  # tablets, capsules, vials, mL, etc.
    reorder_threshold: Decimal = Field(default=Decimal("50"), ge=Decimal("0"))

    def is_available(self, requested: Decimal = Decimal("1")) -> bool:
        return self.quantity_on_hand >= requested


class DrugInteraction(ValueObject):
    """One clinically significant interaction between two drugs, from RxNav.

    ``drug_a`` and ``drug_b`` are RxNorm CUIs or normalised drug names when
    the CUI lookup failed.  ``description`` is the human-readable explanation
    surfaced to the pharmacist via ``reasons_for_failure``.
    """

    drug_a: str
    drug_b: str
    severity: InteractionSeverity
    description: str


class PrescriptionLine(ValueObject):
    """One drug line within a Pharmacy prescription (mirrors Clinical's line)."""

    drug_name: str = Field(min_length=1, max_length=200)
    dose: str
    route: str
    frequency: str
    duration_days: int = Field(ge=1, le=365)
    instructions: str | None = None


class DispensableCandidate(ValueObject):
    """The subject evaluated by the Specification chain before dispensing.

    This VO is assembled by the application layer from:
    * The Prescription aggregate's state.
    * The patient's active consent (queried via Patient Identity's API or
      a local projection).
    * Drug-interaction data from the RxNav ACL.

    Keeping all check inputs in one VO lets us compose specifications purely
    without coupling them to repositories or HTTP clients.
    """

    prescription_id: str
    patient_id: str
    drug_names: list[str]                        # normalised uppercase names
    stock_levels: list[StockLevel]               # current stock for each drug
    has_treatment_consent: bool                  # from Patient Identity projection
    interactions: list[DrugInteraction]          # from RxNav ACL
    current_medications: list[str] = Field(      # other active prescriptions
        default_factory=list
    )
