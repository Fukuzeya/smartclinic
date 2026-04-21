"""Laboratory LabOrder aggregate.

Lifecycle::

    PENDING → SAMPLE_COLLECTED → IN_PROGRESS → COMPLETED
                                               → CANCELLED (any non-terminal state)

Invariants:
* Sample must be collected before results can be recorded.
* At least one result required before the order can be completed.
* Cancelled or completed orders cannot be modified.
* Critical results (CRITICAL_LOW / CRITICAL_HIGH) emit an immediate
  ``CriticalResultAlertV1`` in addition to the standard ``ResultRecordedV1``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from shared_kernel.domain.aggregate_root import AggregateRoot
from shared_kernel.domain.exceptions import InvariantViolation, PreconditionFailed
from shared_kernel.types.identifiers import LabOrderId

from laboratory.domain.events import (
    CriticalResultAlertV1,
    LabOrderCancelledV1,
    LabOrderReceivedV1,
    LabResultsAvailableV1,
    ResultRecordedV1,
    SampleCollectedV1,
)
from laboratory.domain.value_objects import (
    Interpretation,
    LabOrderLine,
    LabResult,
    OrderStatus,
    SampleType,
)

_TERMINAL = {OrderStatus.COMPLETED, OrderStatus.CANCELLED}


class LabOrder(AggregateRoot[LabOrderId]):
    """A laboratory test order — consistency boundary for sample collection
    and result recording."""

    @classmethod
    def receive(
        cls,
        *,
        order_id: LabOrderId,
        patient_id: str,
        encounter_id: str,
        lines: list[LabOrderLine],
        ordered_by: str,
    ) -> LabOrder:
        if not lines:
            raise InvariantViolation("A lab order must have at least one test")
        instance = cls.__new__(cls)
        from shared_kernel.domain.entity import Entity
        Entity.__init__(instance, id=order_id)
        instance._version = 0
        instance._pending_events = []
        instance._patient_id = patient_id
        instance._encounter_id = encounter_id
        instance._lines = lines
        instance._status = OrderStatus.PENDING
        instance._sample_type: SampleType | None = None
        instance._results: list[LabResult] = []
        instance._received_at = datetime.now(UTC)
        instance._record(LabOrderReceivedV1.build(
            order_id=uuid.UUID(str(order_id)),
            aggregate_version=instance._next_version(),
            patient_id=patient_id,
            encounter_id=encounter_id,
            tests=[ln.model_dump(mode="json") for ln in lines],
            ordered_by=ordered_by,
        ))
        return instance

    @classmethod
    def rehydrate(
        cls, *, order_id: LabOrderId, version: int, patient_id: str,
        encounter_id: str, lines: list[LabOrderLine], status: OrderStatus,
        sample_type: SampleType | None, results: list[LabResult],
        received_at: datetime,
    ) -> LabOrder:
        instance = cls.__new__(cls)
        from shared_kernel.domain.entity import Entity
        Entity.__init__(instance, id=order_id)
        instance._version = version
        instance._pending_events = []
        instance._patient_id = patient_id
        instance._encounter_id = encounter_id
        instance._lines = lines
        instance._status = status
        instance._sample_type = sample_type
        instance._results = results
        instance._received_at = received_at
        return instance

    # ---------------------------------------------------------------- commands

    def collect_sample(self, *, sample_type: SampleType, collected_by: str) -> None:
        self._assert_modifiable()
        if self._status != OrderStatus.PENDING:
            raise PreconditionFailed("Sample already collected for this order.")
        self._status = OrderStatus.SAMPLE_COLLECTED
        self._sample_type = sample_type
        self._record(SampleCollectedV1.build(
            order_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            sample_type=sample_type.value,
            collected_by=collected_by,
        ))

    def record_result(self, *, result: LabResult) -> None:
        """Record one test result. Emits a critical alert if the result is critical."""
        self._assert_modifiable()
        if self._status == OrderStatus.PENDING:
            raise PreconditionFailed(
                "Cannot record results before a sample has been collected."
            )
        self._status = OrderStatus.IN_PROGRESS
        self._results.append(result)

        result_payload = result.model_dump(mode="json")
        self._record(ResultRecordedV1.build(
            order_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            result_payload=result_payload,
            is_critical=result.is_critical,
        ))

        if result.is_critical:
            self._record(CriticalResultAlertV1.build(
                order_id=uuid.UUID(str(self.id)),
                aggregate_version=self._next_version(),
                patient_id=self._patient_id,
                test_code=result.test_code,
                interpretation=result.interpretation.value,
                value=result.value,
                unit=result.unit,
            ))

    def complete(self, *, reported_by: str) -> None:
        """Mark order complete and publish results-available integration event."""
        self._assert_modifiable()
        if self._status not in (OrderStatus.SAMPLE_COLLECTED, OrderStatus.IN_PROGRESS):
            raise PreconditionFailed(
                f"Cannot complete an order in status '{self._status}'."
            )
        if not self._results:
            raise InvariantViolation(
                "Cannot complete a lab order with no recorded results."
            )
        self._status = OrderStatus.COMPLETED
        has_critical = any(r.is_critical for r in self._results)
        self._record(LabResultsAvailableV1.build(
            order_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            patient_id=self._patient_id,
            encounter_id=self._encounter_id,
            has_critical_results=has_critical,
            result_count=len(self._results),
            reported_by=reported_by,
        ))

    def cancel(self, *, reason: str, cancelled_by: str) -> None:
        self._assert_modifiable()
        self._status = OrderStatus.CANCELLED
        self._record(LabOrderCancelledV1.build(
            order_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            reason=reason,
            cancelled_by=cancelled_by,
        ))

    # ---------------------------------------------------------------- read

    @property
    def status(self) -> OrderStatus:
        return self._status

    @property
    def patient_id(self) -> str:
        return self._patient_id

    @property
    def encounter_id(self) -> str:
        return self._encounter_id

    @property
    def results(self) -> tuple[LabResult, ...]:
        return tuple(self._results)

    @property
    def lines(self) -> tuple[LabOrderLine, ...]:
        return tuple(self._lines)

    # ---------------------------------------------------------------- helpers

    def _next_version(self) -> int:
        return self._version + len(self._pending_events) + 1

    def _assert_modifiable(self) -> None:
        if self._status in _TERMINAL:
            raise PreconditionFailed(
                f"Lab order is {self._status} and cannot be modified."
            )
