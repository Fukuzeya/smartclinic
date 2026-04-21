"""Scheduling — domain layer.

Pure Python. No SQLAlchemy, no FastAPI, no RabbitMQ.
"""

from scheduling.domain.appointment import Appointment
from scheduling.domain.events import (
    AppointmentBooked,
    AppointmentCancelled,
    AppointmentCheckedIn,
    AppointmentNoShow,
    AppointmentRescheduled,
)
from scheduling.domain.repository import AppointmentRepository
from scheduling.domain.value_objects import (
    AppointmentStatus,
    CancellationReason,
    TimeSlot,
)

__all__ = [
    "Appointment",
    "AppointmentBooked",
    "AppointmentCancelled",
    "AppointmentCheckedIn",
    "AppointmentNoShow",
    "AppointmentRepository",
    "AppointmentRescheduled",
    "AppointmentStatus",
    "CancellationReason",
    "TimeSlot",
]
