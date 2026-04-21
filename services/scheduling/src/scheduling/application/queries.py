"""Scheduling read-side queries."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import Field

from shared_kernel.application.query import Query


class GetAppointment(Query):
    appointment_id: uuid.UUID


class GetAppointmentsForPatient(Query):
    patient_id: uuid.UUID
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class GetAppointmentsForDoctorOnDate(Query):
    doctor_id: uuid.UUID
    on_date: date
