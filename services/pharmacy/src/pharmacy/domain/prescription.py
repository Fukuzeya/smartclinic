"""Pharmacy Prescription aggregate.

The ``Prescription`` aggregate in the Pharmacy context represents an
*intake* of a Clinical prescription into the dispensing workflow.  It is
created when the Pharmacy service consumes a
``clinical.encounter.prescription_issued.v1`` event (via the ACL inbox
handler), then transitions through the dispensing lifecycle.

This is a **state-based** aggregate (not event-sourced): the state is stored
in the ``prescriptions`` table.  The Clinical context's Event Sourcing is the
ground truth for the encounter record; Pharmacy only cares about its own
dispensing view.

Lifecycle::

    PENDING → DISPENSED       (full dispense)
    PENDING → PARTIAL         (some drugs dispensed)
    PENDING → REJECTED        (specification failure)
    PENDING → CANCELLED       (administrative cancellation)
    PARTIAL → DISPENSED       (remaining drugs dispensed in follow-up)
    PARTIAL → CANCELLED
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from shared_kernel.domain.aggregate_root import AggregateRoot
from shared_kernel.domain.exceptions import InvariantViolation, PreconditionFailed
from shared_kernel.types.identifiers import PrescriptionId

from pharmacy.domain.events import (
    DispensingCompletedV1,
    DispensingPartialV1,
    DispensingRejectedV1,
    PrescriptionReceivedV1,
)
from pharmacy.domain.value_objects import DispensingStatus, PrescriptionLine


_TERMINAL_STATES = {
    DispensingStatus.DISPENSED,
    DispensingStatus.REJECTED,
    DispensingStatus.CANCELLED,
}


class Prescription(AggregateRoot[PrescriptionId]):
    """A dispensable prescription received from the Clinical context."""

    @classmethod
    def receive(
        cls,
        *,
        prescription_id: PrescriptionId,
        patient_id: str,
        encounter_id: str,
        lines: list[PrescriptionLine],
        issued_by: str,
    ) -> Prescription:
        """Create a new Prescription intake from a Clinical event."""
        if not lines:
            raise InvariantViolation("A prescription must have at least one drug line")

        instance = cls.__new__(cls)
        from shared_kernel.domain.entity import Entity
        Entity.__init__(instance, id=prescription_id)
        instance._version = 0
        instance._pending_events = []
        instance._patient_id = patient_id
        instance._encounter_id = encounter_id
        instance._lines = lines
        instance._status = DispensingStatus.PENDING
        instance._received_at = datetime.now(UTC)
        instance._dispensed_at = None

        event = PrescriptionReceivedV1.build(
            prescription_id=uuid.UUID(str(prescription_id)),
            aggregate_version=instance._next_version(),
            patient_id=patient_id,
            encounter_id=encounter_id,
            drug_names=[ln.drug_name for ln in lines],
            issued_by=issued_by,
        )
        instance._record(event)
        return instance

    @classmethod
    def rehydrate(
        cls,
        *,
        prescription_id: PrescriptionId,
        version: int,
        patient_id: str,
        encounter_id: str,
        lines: list[PrescriptionLine],
        status: DispensingStatus,
        received_at: datetime,
        dispensed_at: datetime | None,
    ) -> Prescription:
        instance = cls.__new__(cls)
        from shared_kernel.domain.entity import Entity
        Entity.__init__(instance, id=prescription_id)
        instance._version = version
        instance._pending_events = []
        instance._patient_id = patient_id
        instance._encounter_id = encounter_id
        instance._lines = lines
        instance._status = status
        instance._received_at = received_at
        instance._dispensed_at = dispensed_at
        return instance

    # ---------------------------------------------------------------- commands

    def dispense(self, *, dispensed_by: str) -> None:
        """Mark the full prescription as dispensed."""
        self._assert_actionable()
        self._status = DispensingStatus.DISPENSED
        self._dispensed_at = datetime.now(UTC)
        self._record(DispensingCompletedV1.build(
            prescription_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            patient_id=self._patient_id,
            dispensed_by=dispensed_by,
            lines_dispensed=[ln.model_dump(mode="json") for ln in self._lines],
        ))

    def dispense_partial(
        self,
        *,
        dispensed_line_names: list[str],
        dispensed_by: str,
    ) -> None:
        """Dispense a subset of lines; remainder stays pending."""
        self._assert_actionable()
        dispensed_upper = {n.upper() for n in dispensed_line_names}
        dispensed = [ln for ln in self._lines if ln.drug_name.upper() in dispensed_upper]
        pending = [ln.drug_name for ln in self._lines if ln.drug_name.upper() not in dispensed_upper]
        if not dispensed:
            raise InvariantViolation("No matching drug lines found for partial dispense")
        self._status = DispensingStatus.PARTIAL
        self._record(DispensingPartialV1.build(
            prescription_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            patient_id=self._patient_id,
            dispensed_lines=[ln.model_dump(mode="json") for ln in dispensed],
            pending_lines=pending,
            dispensed_by=dispensed_by,
        ))

    def reject(self, *, reasons: list[str], rejected_by: str) -> None:
        """Block dispensing due to specification failure."""
        self._assert_actionable()
        self._status = DispensingStatus.REJECTED
        self._record(DispensingRejectedV1.build(
            prescription_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            patient_id=self._patient_id,
            reasons=reasons,
            rejected_by=rejected_by,
        ))

    def cancel(self) -> None:
        self._assert_actionable()
        self._status = DispensingStatus.CANCELLED

    # ---------------------------------------------------------------- read

    @property
    def status(self) -> DispensingStatus:
        return self._status

    @property
    def patient_id(self) -> str:
        return self._patient_id

    @property
    def encounter_id(self) -> str:
        return self._encounter_id

    @property
    def lines(self) -> tuple[PrescriptionLine, ...]:
        return tuple(self._lines)

    @property
    def drug_names(self) -> list[str]:
        return [ln.drug_name for ln in self._lines]

    # ---------------------------------------------------------------- helpers

    def _next_version(self) -> int:
        return self._version + len(self._pending_events) + 1

    def _assert_actionable(self) -> None:
        if self._status in _TERMINAL_STATES:
            raise PreconditionFailed(
                f"Prescription is {self._status} and cannot be modified."
            )
