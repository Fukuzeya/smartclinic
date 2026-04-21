"""Laboratory application-layer commands."""

from __future__ import annotations

from shared_kernel.application.command import Command
from shared_kernel.types.identifiers import LabOrderId


class CollectSampleCommand(Command):
    order_id: LabOrderId
    sample_type: str       # SampleType enum value
    collected_by: str      # Keycloak subject


class RecordResultCommand(Command):
    order_id: LabOrderId
    test_code: str
    test_name: str
    value: str
    unit: str | None = None
    reference_range_lower: str | None = None
    reference_range_upper: str | None = None
    reference_range_unit: str | None = None
    interpretation: str    # Interpretation enum value
    notes: str | None = None
    performed_by: str      # Keycloak subject


class CompleteOrderCommand(Command):
    order_id: LabOrderId
    reported_by: str       # Keycloak subject


class CancelOrderCommand(Command):
    order_id: LabOrderId
    reason: str
    cancelled_by: str      # Keycloak subject
