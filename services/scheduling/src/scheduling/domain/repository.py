"""Repository contract for the Appointment aggregate."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from shared_kernel.types.identifiers import AppointmentId, DoctorId, PatientId

from scheduling.domain.appointment import Appointment


class AppointmentRepository(Protocol):
    async def get(self, appointment_id: AppointmentId) -> Appointment: ...

    async def add(self, appointment: Appointment) -> None: ...

    async def save(self, appointment: Appointment) -> None: ...

    async def list_for_patient(
        self, patient_id: PatientId, *, limit: int = 50, offset: int = 0
    ) -> list[Appointment]: ...

    async def list_for_doctor_on_date(
        self, doctor_id: DoctorId, on_date: date
    ) -> list[Appointment]: ...
