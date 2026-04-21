"""Laboratory domain events."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import Field

from shared_kernel.domain.domain_event import DomainEvent


class LabEvent(DomainEvent):
    aggregate_type: str = Field(default="LabOrder")


class LabOrderReceivedV1(LabEvent):
    event_type: str = Field(default="laboratory.order.received.v1")

    @classmethod
    def build(cls, *, order_id: uuid.UUID, aggregate_version: int,
              patient_id: str, encounter_id: str, tests: list[dict],
              ordered_by: str, **kw) -> LabOrderReceivedV1:
        return cls(aggregate_id=str(order_id), aggregate_version=aggregate_version,
                   payload={"patient_id": patient_id, "encounter_id": encounter_id,
                            "tests": tests, "ordered_by": ordered_by}, **kw)


class SampleCollectedV1(LabEvent):
    event_type: str = Field(default="laboratory.order.sample_collected.v1")

    @classmethod
    def build(cls, *, order_id: uuid.UUID, aggregate_version: int,
              sample_type: str, collected_by: str, **kw) -> SampleCollectedV1:
        return cls(aggregate_id=str(order_id), aggregate_version=aggregate_version,
                   payload={"sample_type": sample_type, "collected_by": collected_by}, **kw)


class ResultRecordedV1(LabEvent):
    event_type: str = Field(default="laboratory.order.result_recorded.v1")

    @classmethod
    def build(cls, *, order_id: uuid.UUID, aggregate_version: int,
              result_payload: dict[str, Any], is_critical: bool, **kw) -> ResultRecordedV1:
        return cls(aggregate_id=str(order_id), aggregate_version=aggregate_version,
                   payload={**result_payload, "is_critical": is_critical}, **kw)


class LabResultsAvailableV1(LabEvent):
    """Cross-context integration event — triggers clinical doctor review + billing."""
    event_type: str = Field(default="laboratory.order.results_available.v1")

    @classmethod
    def build(cls, *, order_id: uuid.UUID, aggregate_version: int,
              patient_id: str, encounter_id: str,
              has_critical_results: bool, result_count: int,
              reported_by: str, **kw) -> LabResultsAvailableV1:
        return cls(aggregate_id=str(order_id), aggregate_version=aggregate_version,
                   payload={"patient_id": patient_id, "encounter_id": encounter_id,
                            "has_critical_results": has_critical_results,
                            "result_count": result_count, "reported_by": reported_by}, **kw)


class CriticalResultAlertV1(LabEvent):
    """Emitted immediately when a critical result is recorded (stat notification)."""
    event_type: str = Field(default="laboratory.order.critical_alert.v1")

    @classmethod
    def build(cls, *, order_id: uuid.UUID, aggregate_version: int,
              patient_id: str, test_code: str, interpretation: str,
              value: str, unit: str | None, **kw) -> CriticalResultAlertV1:
        return cls(aggregate_id=str(order_id), aggregate_version=aggregate_version,
                   payload={"patient_id": patient_id, "test_code": test_code,
                            "interpretation": interpretation, "value": value,
                            "unit": unit}, **kw)


class LabOrderCancelledV1(LabEvent):
    event_type: str = Field(default="laboratory.order.cancelled.v1")

    @classmethod
    def build(cls, *, order_id: uuid.UUID, aggregate_version: int,
              reason: str, cancelled_by: str, **kw) -> LabOrderCancelledV1:
        return cls(aggregate_id=str(order_id), aggregate_version=aggregate_version,
                   payload={"reason": reason, "cancelled_by": cancelled_by}, **kw)
