"""Scheduling write-side commands."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from shared_kernel.application.command import Command

from scheduling.domain.value_objects import CancellationReason


class BookAppointment(Command):
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    start_at: datetime = Field(description="UTC ISO-8601 datetime.")
    end_at: datetime = Field(description="UTC ISO-8601 datetime.")
    reason: str | None = Field(default=None, max_length=500)
    booked_by: str = Field(min_length=1, max_length=128)
    appointment_id: uuid.UUID | None = None


class CheckInAppointment(Command):
    appointment_id: uuid.UUID
    checked_in_by: str = Field(min_length=1, max_length=128)


class CancelAppointment(Command):
    appointment_id: uuid.UUID
    reason: CancellationReason
    cancelled_by: str = Field(min_length=1, max_length=128)


class MarkNoShow(Command):
    appointment_id: uuid.UUID
    marked_by: str = Field(min_length=1, max_length=128)


class RescheduleAppointment(Command):
    appointment_id: uuid.UUID
    new_start_at: datetime
    new_end_at: datetime
    rescheduled_by: str = Field(min_length=1, max_length=128)
