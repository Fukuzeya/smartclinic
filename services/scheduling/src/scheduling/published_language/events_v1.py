"""Scheduling published-language wire schemas v1.

The ``checked_in`` event carries everything Clinical needs to open an
Encounter without calling back into Scheduling.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _V1Base(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow", populate_by_name=True)
    event_id: str
    event_type: str
    occurred_at: datetime
    aggregate_id: str
    correlation_id: str | None = None
    trace_id: str | None = None


class AppointmentBookedV1(_V1Base):
    event_type: Literal["scheduling.appointment.booked.v1"] = (
        "scheduling.appointment.booked.v1"
    )
    appointment_id: str
    patient_id: str
    doctor_id: str
    start_at: datetime
    end_at: datetime
    reason: str | None = None
    booked_by: str


class AppointmentCheckedInV1(_V1Base):
    """Consumed by Clinical to open an Encounter.

    Carries ``doctor_id`` and ``start_at`` so Clinical can initialise
    the Encounter without a synchronous call back to Scheduling.
    """
    event_type: Literal["scheduling.appointment.checked_in.v1"] = (
        "scheduling.appointment.checked_in.v1"
    )
    appointment_id: str
    patient_id: str
    doctor_id: str
    start_at: datetime
    checked_in_at: datetime
    checked_in_by: str


class AppointmentCancelledV1(_V1Base):
    event_type: Literal["scheduling.appointment.cancelled.v1"] = (
        "scheduling.appointment.cancelled.v1"
    )
    appointment_id: str
    patient_id: str
    cancellation_reason: str
    cancelled_by: str
    cancelled_at: datetime


class AppointmentNoShowV1(_V1Base):
    event_type: Literal["scheduling.appointment.no_show.v1"] = (
        "scheduling.appointment.no_show.v1"
    )
    appointment_id: str
    patient_id: str
    marked_by: str
    marked_at: datetime


class AppointmentRescheduledV1(_V1Base):
    event_type: Literal["scheduling.appointment.rescheduled.v1"] = (
        "scheduling.appointment.rescheduled.v1"
    )
    appointment_id: str
    patient_id: str
    old_start_at: datetime
    old_end_at: datetime
    new_start_at: datetime
    new_end_at: datetime
    rescheduled_by: str
