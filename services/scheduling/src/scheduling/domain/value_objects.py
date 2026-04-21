"""Scheduling — domain value objects."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from shared_kernel.domain.value_object import ValueObject


class AppointmentStatus(StrEnum):
    BOOKED = "booked"
    CHECKED_IN = "checked_in"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class CancellationReason(StrEnum):
    PATIENT_REQUEST = "patient_request"
    DOCTOR_UNAVAILABLE = "doctor_unavailable"
    FACILITY_ISSUE = "facility_issue"
    OTHER = "other"


class TimeSlot(ValueObject):
    """An immutable, validated time interval for an appointment.

    Invariants:
    * ``end_at`` must be strictly after ``start_at``.
    * The slot must be at least 5 minutes long (guards mis-entries).
    * Maximum 8 hours (prevents unbounded blocks).
    """

    start_at: datetime = Field(description="UTC start of the appointment slot.")
    end_at: datetime = Field(description="UTC end of the appointment slot.")

    @model_validator(mode="after")
    def _validate_interval(self) -> Self:
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("TimeSlot datetimes must be timezone-aware")
        duration = self.end_at - self.start_at
        if duration < timedelta(minutes=5):
            raise ValueError("slot duration must be at least 5 minutes")
        if duration > timedelta(hours=8):
            raise ValueError("slot duration must not exceed 8 hours")
        return self

    @property
    def duration_minutes(self) -> int:
        return int((self.end_at - self.start_at).total_seconds() / 60)

    def overlaps(self, other: TimeSlot) -> bool:
        return self.start_at < other.end_at and other.start_at < self.end_at

    def is_in_future(self, now: datetime) -> bool:
        return self.start_at > now
