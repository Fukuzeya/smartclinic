"""Saga Orchestrator — value objects.

The Patient Visit Saga tracks a single patient encounter from appointment
check-in through to full billing settlement.  The saga's step enum drives
state-machine transitions; the context bag carries correlated ids from each
bounded context so the saga can provide a unified view of the visit.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from shared_kernel.domain.value_object import ValueObject


class SagaStep(StrEnum):
    """Ordered steps of the Patient Visit Saga lifecycle.

    Transitions::

        AWAITING_ENCOUNTER
            → ENCOUNTER_OPEN          (doctor starts consultation)
            → AWAITING_LAB            (any lab order placed during encounter)
        ENCOUNTER_OPEN
            → AWAITING_LAB            (lab order placed)
            → AWAITING_PAYMENT        (encounter closed, no pending labs)
        AWAITING_LAB
            → AWAITING_PAYMENT        (all lab results in AND encounter closed)
        AWAITING_PAYMENT
            → COMPLETED               (invoice paid in full)

        (any non-terminal) → CANCELLED
    """

    AWAITING_ENCOUNTER = "awaiting_encounter"
    ENCOUNTER_OPEN = "encounter_open"
    AWAITING_LAB = "awaiting_lab"
    AWAITING_PAYMENT = "awaiting_payment"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SagaStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SagaContext(ValueObject):
    """Correlated identifiers accumulated as the saga progresses.

    All fields are optional because they are populated incrementally
    as events arrive from different bounded contexts.
    """

    appointment_id: str | None = None
    encounter_id: str | None = None
    invoice_id: str | None = None
    # Lab order ids placed during the encounter
    lab_order_ids: list[str] = Field(default_factory=list)
    # Lab order ids for which results_available has been received
    lab_orders_completed: list[str] = Field(default_factory=list)
    # Whether the clinical encounter has been formally closed
    encounter_closed: bool = False

    @property
    def all_labs_completed(self) -> bool:
        if not self.lab_order_ids:
            return True
        return set(self.lab_order_ids).issubset(set(self.lab_orders_completed))
