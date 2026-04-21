"""SQLAlchemy repository for the Appointment aggregate."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared_kernel.domain.exceptions import ConcurrencyConflict, NotFound
from shared_kernel.types.identifiers import AppointmentId, DoctorId, PatientId

from scheduling.domain.appointment import Appointment
from scheduling.domain.value_objects import AppointmentStatus, TimeSlot
from scheduling.infrastructure.orm import AppointmentRow


class SqlAlchemyAppointmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, appointment_id: AppointmentId) -> Appointment:
        row = await self._session.get(
            AppointmentRow, appointment_id.value, populate_existing=True
        )
        if row is None:
            raise NotFound(f"appointment '{appointment_id.value}' not found")
        return _to_domain(row)

    async def add(self, appointment: Appointment) -> None:
        self._session.add(_to_orm(appointment))

    async def save(self, appointment: Appointment) -> None:
        row = await self._session.get(AppointmentRow, appointment.id.value)
        if row is None:
            raise NotFound(f"appointment '{appointment.id.value}' not found for update")
        if row.version != appointment.version:
            raise ConcurrencyConflict(
                f"appointment '{appointment.id.value}' version conflict"
            )
        _update_row(row, appointment)

    async def list_for_patient(
        self,
        patient_id: PatientId,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Appointment]:
        stmt = (
            select(AppointmentRow)
            .where(AppointmentRow.patient_id == patient_id.value)
            .order_by(AppointmentRow.start_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]

    async def list_for_doctor_on_date(
        self, doctor_id: DoctorId, on_date: date
    ) -> list[Appointment]:
        day_start = datetime(
            on_date.year, on_date.month, on_date.day,
            tzinfo=timezone.utc,
        )
        day_end = day_start + timedelta(days=1)
        stmt = (
            select(AppointmentRow)
            .where(
                and_(
                    AppointmentRow.doctor_id == doctor_id.value,
                    AppointmentRow.start_at >= day_start,
                    AppointmentRow.start_at < day_end,
                )
            )
            .order_by(AppointmentRow.start_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]


def _to_domain(row: AppointmentRow) -> Appointment:
    return Appointment.rehydrate(
        id=AppointmentId(value=row.id),
        version=row.version,
        patient_id=PatientId(value=row.patient_id),
        doctor_id=DoctorId(value=row.doctor_id),
        slot=TimeSlot(start_at=row.start_at, end_at=row.end_at),
        status=AppointmentStatus(row.status),
        reason=row.reason,
        booked_by=row.booked_by,
        booked_at=row.booked_at,
    )


def _to_orm(appt: Appointment) -> AppointmentRow:
    return AppointmentRow(
        id=appt.id.value,
        version=appt.version,
        patient_id=appt.patient_id.value,
        doctor_id=appt.doctor_id.value,
        start_at=appt.slot.start_at,
        end_at=appt.slot.end_at,
        status=appt.status.value,
        reason=appt.reason,
        booked_by=appt.booked_by,
        booked_at=appt.booked_at,
    )


def _update_row(row: AppointmentRow, appt: Appointment) -> None:
    row.version = appt.version
    row.start_at = appt.slot.start_at
    row.end_at = appt.slot.end_at
    row.status = appt.status.value
    row.reason = appt.reason
