"""Domain events emitted by the Appointment aggregate.

Routing keys follow the pattern ``scheduling.appointment.<action>.v1``.
The ``checked_in`` event is special: it is the cross-context trigger
that causes Clinical to open an Encounter for the visit.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from shared_kernel.domain.domain_event import DomainEvent


class _PayloadBase(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, populate_by_name=True
    )


class AppointmentBookedPayload(_PayloadBase):
    appointment_id: str
    patient_id: str
    doctor_id: str
    start_at: datetime
    end_at: datetime
    reason: str | None
    booked_by: str


class AppointmentCheckedInPayload(_PayloadBase):
    appointment_id: str
    patient_id: str
    doctor_id: str
    start_at: datetime
    checked_in_at: datetime
    checked_in_by: str


class AppointmentCancelledPayload(_PayloadBase):
    appointment_id: str
    patient_id: str
    cancellation_reason: str
    cancelled_by: str
    cancelled_at: datetime


class AppointmentNoShowPayload(_PayloadBase):
    appointment_id: str
    patient_id: str
    marked_by: str
    marked_at: datetime


class AppointmentRescheduledPayload(_PayloadBase):
    appointment_id: str
    patient_id: str
    old_start_at: datetime
    old_end_at: datetime
    new_start_at: datetime
    new_end_at: datetime
    rescheduled_by: str


class _SchedulingEvent(DomainEvent):
    aggregate_type: str = "Appointment"


class AppointmentBooked(_SchedulingEvent):
    event_type: str = "scheduling.appointment.booked.v1"

    @classmethod
    def build(
        cls,
        *,
        aggregate_id: str,
        aggregate_version: int,
        data: AppointmentBookedPayload,
    ) -> AppointmentBooked:
        return cls(
            aggregate_id=aggregate_id,
            aggregate_version=aggregate_version,
            payload=data.model_dump(mode="json"),
        )


class AppointmentCheckedIn(_SchedulingEvent):
    event_type: str = "scheduling.appointment.checked_in.v1"

    @classmethod
    def build(
        cls,
        *,
        aggregate_id: str,
        aggregate_version: int,
        data: AppointmentCheckedInPayload,
    ) -> AppointmentCheckedIn:
        return cls(
            aggregate_id=aggregate_id,
            aggregate_version=aggregate_version,
            payload=data.model_dump(mode="json"),
        )


class AppointmentCancelled(_SchedulingEvent):
    event_type: str = "scheduling.appointment.cancelled.v1"

    @classmethod
    def build(
        cls,
        *,
        aggregate_id: str,
        aggregate_version: int,
        data: AppointmentCancelledPayload,
    ) -> AppointmentCancelled:
        return cls(
            aggregate_id=aggregate_id,
            aggregate_version=aggregate_version,
            payload=data.model_dump(mode="json"),
        )


class AppointmentNoShow(_SchedulingEvent):
    event_type: str = "scheduling.appointment.no_show.v1"

    @classmethod
    def build(
        cls,
        *,
        aggregate_id: str,
        aggregate_version: int,
        data: AppointmentNoShowPayload,
    ) -> AppointmentNoShow:
        return cls(
            aggregate_id=aggregate_id,
            aggregate_version=aggregate_version,
            payload=data.model_dump(mode="json"),
        )


class AppointmentRescheduled(_SchedulingEvent):
    event_type: str = "scheduling.appointment.rescheduled.v1"

    @classmethod
    def build(
        cls,
        *,
        aggregate_id: str,
        aggregate_version: int,
        data: AppointmentRescheduledPayload,
    ) -> AppointmentRescheduled:
        return cls(
            aggregate_id=aggregate_id,
            aggregate_version=aggregate_version,
            payload=data.model_dump(mode="json"),
        )
