"""Scheduling command and query handlers."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from shared_kernel.infrastructure.logging import get_logger
from shared_kernel.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork
from shared_kernel.types.clock import Clock, SystemClock
from shared_kernel.types.identifiers import AppointmentId, DoctorId, PatientId

from scheduling.application.commands import (
    BookAppointment,
    CancelAppointment,
    CheckInAppointment,
    MarkNoShow,
    RescheduleAppointment,
)
from scheduling.application.queries import (
    GetAppointment,
    GetAppointmentsForDoctorOnDate,
    GetAppointmentsForPatient,
)
from scheduling.domain.appointment import Appointment
from scheduling.domain.value_objects import TimeSlot
from scheduling.infrastructure.repository import SqlAlchemyAppointmentRepository

log = get_logger(__name__)


class BookAppointmentHandler:
    def __init__(self, uow: SqlAlchemyUnitOfWork, clock: Clock | None = None) -> None:
        self._uow = uow
        self._clock = clock or SystemClock()

    async def __call__(self, cmd: BookAppointment) -> AppointmentId:
        async with self._uow:
            repo = SqlAlchemyAppointmentRepository(self._uow.session)
            appt = Appointment.book(
                appointment_id=(
                    AppointmentId(value=cmd.appointment_id) if cmd.appointment_id else None
                ),
                patient_id=PatientId(value=cmd.patient_id),
                doctor_id=DoctorId(value=cmd.doctor_id),
                slot=TimeSlot(start_at=cmd.start_at, end_at=cmd.end_at),
                reason=cmd.reason,
                booked_by=cmd.booked_by,
                clock=self._clock,
            )
            await repo.add(appt)
            self._uow.register(appt)
            await self._uow.commit()
            log.info(
                "appointment.booked",
                appointment_id=str(appt.id.value),
                patient_id=str(appt.patient_id.value),
            )
            return appt.id


class CheckInAppointmentHandler:
    def __init__(self, uow: SqlAlchemyUnitOfWork, clock: Clock | None = None) -> None:
        self._uow = uow
        self._clock = clock or SystemClock()

    async def __call__(self, cmd: CheckInAppointment) -> None:
        async with self._uow:
            repo = SqlAlchemyAppointmentRepository(self._uow.session)
            appt = await repo.get(AppointmentId(value=cmd.appointment_id))
            appt.check_in(checked_in_by=cmd.checked_in_by, clock=self._clock)
            await repo.save(appt)
            self._uow.register(appt)
            await self._uow.commit()


class CancelAppointmentHandler:
    def __init__(self, uow: SqlAlchemyUnitOfWork, clock: Clock | None = None) -> None:
        self._uow = uow
        self._clock = clock or SystemClock()

    async def __call__(self, cmd: CancelAppointment) -> None:
        async with self._uow:
            repo = SqlAlchemyAppointmentRepository(self._uow.session)
            appt = await repo.get(AppointmentId(value=cmd.appointment_id))
            appt.cancel(reason=cmd.reason, cancelled_by=cmd.cancelled_by, clock=self._clock)
            await repo.save(appt)
            self._uow.register(appt)
            await self._uow.commit()


class MarkNoShowHandler:
    def __init__(self, uow: SqlAlchemyUnitOfWork, clock: Clock | None = None) -> None:
        self._uow = uow
        self._clock = clock or SystemClock()

    async def __call__(self, cmd: MarkNoShow) -> None:
        async with self._uow:
            repo = SqlAlchemyAppointmentRepository(self._uow.session)
            appt = await repo.get(AppointmentId(value=cmd.appointment_id))
            appt.mark_no_show(marked_by=cmd.marked_by, clock=self._clock)
            await repo.save(appt)
            self._uow.register(appt)
            await self._uow.commit()


class RescheduleAppointmentHandler:
    def __init__(self, uow: SqlAlchemyUnitOfWork, clock: Clock | None = None) -> None:
        self._uow = uow
        self._clock = clock or SystemClock()

    async def __call__(self, cmd: RescheduleAppointment) -> None:
        async with self._uow:
            repo = SqlAlchemyAppointmentRepository(self._uow.session)
            appt = await repo.get(AppointmentId(value=cmd.appointment_id))
            appt.reschedule(
                new_slot=TimeSlot(start_at=cmd.new_start_at, end_at=cmd.new_end_at),
                rescheduled_by=cmd.rescheduled_by,
                clock=self._clock,
            )
            await repo.save(appt)
            self._uow.register(appt)
            await self._uow.commit()


class GetAppointmentHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __call__(self, query: GetAppointment) -> Appointment:
        repo = SqlAlchemyAppointmentRepository(self._session)
        return await repo.get(AppointmentId(value=query.appointment_id))


class GetAppointmentsForPatientHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __call__(self, query: GetAppointmentsForPatient) -> list[Appointment]:
        repo = SqlAlchemyAppointmentRepository(self._session)
        return await repo.list_for_patient(
            PatientId(value=query.patient_id),
            limit=query.limit,
            offset=query.offset,
        )


class GetAppointmentsForDoctorOnDateHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __call__(
        self, query: GetAppointmentsForDoctorOnDate
    ) -> list[Appointment]:
        repo = SqlAlchemyAppointmentRepository(self._session)
        return await repo.list_for_doctor_on_date(
            DoctorId(value=query.doctor_id), query.on_date
        )
