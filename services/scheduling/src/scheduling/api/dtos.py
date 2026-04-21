"""Scheduling HTTP API DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from scheduling.domain.appointment import Appointment
from scheduling.domain.value_objects import AppointmentStatus, CancellationReason


class _APIBase(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class BookAppointmentRequest(_APIBase):
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    start_at: datetime = Field(description="UTC ISO-8601.")
    end_at: datetime = Field(description="UTC ISO-8601.")
    reason: str | None = Field(default=None, max_length=500)


class RescheduleRequest(_APIBase):
    new_start_at: datetime
    new_end_at: datetime


class CancelRequest(_APIBase):
    reason: CancellationReason


class AppointmentResponse(_APIBase):
    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    duration_minutes: int
    status: AppointmentStatus
    reason: str | None = None
    booked_by: str
    booked_at: datetime
    version: int

    @classmethod
    def from_domain(cls, appt: Appointment) -> AppointmentResponse:
        return cls(
            appointment_id=appt.id.value,
            patient_id=appt.patient_id.value,
            doctor_id=appt.doctor_id.value,
            start_at=appt.slot.start_at,
            end_at=appt.slot.end_at,
            duration_minutes=appt.slot.duration_minutes,
            status=appt.status,
            reason=appt.reason,
            booked_by=appt.booked_by,
            booked_at=appt.booked_at,
            version=appt.version,
        )


class AppointmentListResponse(_APIBase):
    items: list[AppointmentResponse]
    total: int
    limit: int
    offset: int


class BookAppointmentResponse(_APIBase):
    appointment_id: uuid.UUID
    message: str = "Appointment booked successfully."
