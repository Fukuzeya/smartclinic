"""The Appointment aggregate.

Owns the lifecycle: BOOKED → CHECKED_IN | CANCELLED | NO_SHOW.
A CHECKED_IN appointment triggers ``scheduling.appointment.checked_in.v1``
which the Clinical context consumes to open an Encounter.

Like Patient, Appointment is **not** event-sourced — state is in a row,
events exist for integration only (ADR 0003 scopes ES to Clinical).
"""

from __future__ import annotations

from datetime import datetime

from shared_kernel.domain.aggregate_root import AggregateRoot
from shared_kernel.domain.exceptions import InvariantViolation, PreconditionFailed
from shared_kernel.types.clock import Clock
from shared_kernel.types.identifiers import AppointmentId, DoctorId, PatientId

from scheduling.domain.events import (
    AppointmentBooked,
    AppointmentBookedPayload,
    AppointmentCancelled,
    AppointmentCancelledPayload,
    AppointmentCheckedIn,
    AppointmentCheckedInPayload,
    AppointmentNoShow,
    AppointmentNoShowPayload,
    AppointmentRescheduled,
    AppointmentRescheduledPayload,
)
from scheduling.domain.value_objects import AppointmentStatus, CancellationReason, TimeSlot

# Status transition table — defines legal state-machine edges.
_VALID_TRANSITIONS: dict[AppointmentStatus, set[AppointmentStatus]] = {
    AppointmentStatus.BOOKED: {
        AppointmentStatus.CHECKED_IN,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    },
    AppointmentStatus.CHECKED_IN: set(),
    AppointmentStatus.CANCELLED: set(),
    AppointmentStatus.NO_SHOW: set(),
}


class Appointment(AggregateRoot[AppointmentId]):
    """An appointment between a patient and a doctor.

    Terminal states (CHECKED_IN, CANCELLED, NO_SHOW) are immutable.
    """

    __slots__ = (
        "_patient_id",
        "_doctor_id",
        "_slot",
        "_status",
        "_reason",
        "_booked_by",
        "_booked_at",
    )

    def __init__(
        self,
        *,
        id: AppointmentId,
        version: int,
        patient_id: PatientId,
        doctor_id: DoctorId,
        slot: TimeSlot,
        status: AppointmentStatus,
        reason: str | None,
        booked_by: str,
        booked_at: datetime,
    ) -> None:
        super().__init__(id=id, version=version)
        self._patient_id = patient_id
        self._doctor_id = doctor_id
        self._slot = slot
        self._status = status
        self._reason = reason
        self._booked_by = booked_by
        self._booked_at = booked_at

    # -- Factory ----------------------------------------------------------

    @classmethod
    def book(
        cls,
        *,
        appointment_id: AppointmentId | None = None,
        patient_id: PatientId,
        doctor_id: DoctorId,
        slot: TimeSlot,
        reason: str | None = None,
        booked_by: str,
        clock: Clock,
    ) -> Appointment:
        if not booked_by.strip():
            raise InvariantViolation("booked_by must be a non-empty actor id")
        now = clock.now()
        if not slot.is_in_future(now):
            raise InvariantViolation("cannot book an appointment in the past")

        new_id = appointment_id or AppointmentId.new()
        appt = cls(
            id=new_id,
            version=0,
            patient_id=patient_id,
            doctor_id=doctor_id,
            slot=slot,
            status=AppointmentStatus.BOOKED,
            reason=reason,
            booked_by=booked_by,
            booked_at=now,
        )
        appt._record(
            AppointmentBooked.build(
                aggregate_id=str(new_id.value),
                aggregate_version=appt._next_version(),
                data=AppointmentBookedPayload(
                    appointment_id=str(new_id.value),
                    patient_id=str(patient_id.value),
                    doctor_id=str(doctor_id.value),
                    start_at=slot.start_at,
                    end_at=slot.end_at,
                    reason=reason,
                    booked_by=booked_by,
                ),
            )
        )
        return appt

    @classmethod
    def rehydrate(
        cls,
        *,
        id: AppointmentId,
        version: int,
        patient_id: PatientId,
        doctor_id: DoctorId,
        slot: TimeSlot,
        status: AppointmentStatus,
        reason: str | None,
        booked_by: str,
        booked_at: datetime,
    ) -> Appointment:
        if version < 1:
            raise InvariantViolation("rehydrated aggregate must have version >= 1")
        return cls(
            id=id,
            version=version,
            patient_id=patient_id,
            doctor_id=doctor_id,
            slot=slot,
            status=status,
            reason=reason,
            booked_by=booked_by,
            booked_at=booked_at,
        )

    # -- Behaviours -------------------------------------------------------

    def check_in(self, *, checked_in_by: str, clock: Clock) -> None:
        self._transition_to(AppointmentStatus.CHECKED_IN)
        now = clock.now()
        self._record(
            AppointmentCheckedIn.build(
                aggregate_id=str(self.id.value),
                aggregate_version=self._next_version(),
                data=AppointmentCheckedInPayload(
                    appointment_id=str(self.id.value),
                    patient_id=str(self._patient_id.value),
                    doctor_id=str(self._doctor_id.value),
                    start_at=self._slot.start_at,
                    checked_in_at=now,
                    checked_in_by=checked_in_by,
                ),
            )
        )
        self._status = AppointmentStatus.CHECKED_IN

    def cancel(
        self,
        *,
        reason: CancellationReason,
        cancelled_by: str,
        clock: Clock,
    ) -> None:
        self._transition_to(AppointmentStatus.CANCELLED)
        now = clock.now()
        self._record(
            AppointmentCancelled.build(
                aggregate_id=str(self.id.value),
                aggregate_version=self._next_version(),
                data=AppointmentCancelledPayload(
                    appointment_id=str(self.id.value),
                    patient_id=str(self._patient_id.value),
                    cancellation_reason=reason.value,
                    cancelled_by=cancelled_by,
                    cancelled_at=now,
                ),
            )
        )
        self._status = AppointmentStatus.CANCELLED

    def mark_no_show(self, *, marked_by: str, clock: Clock) -> None:
        self._transition_to(AppointmentStatus.NO_SHOW)
        now = clock.now()
        self._record(
            AppointmentNoShow.build(
                aggregate_id=str(self.id.value),
                aggregate_version=self._next_version(),
                data=AppointmentNoShowPayload(
                    appointment_id=str(self.id.value),
                    patient_id=str(self._patient_id.value),
                    marked_by=marked_by,
                    marked_at=now,
                ),
            )
        )
        self._status = AppointmentStatus.NO_SHOW

    def reschedule(
        self,
        *,
        new_slot: TimeSlot,
        rescheduled_by: str,
        clock: Clock,
    ) -> None:
        if self._status != AppointmentStatus.BOOKED:
            raise PreconditionFailed(
                f"cannot reschedule appointment in status '{self._status.value}'"
            )
        if not new_slot.is_in_future(clock.now()):
            raise InvariantViolation("cannot reschedule to a slot in the past")

        old_slot = self._slot
        self._record(
            AppointmentRescheduled.build(
                aggregate_id=str(self.id.value),
                aggregate_version=self._next_version(),
                data=AppointmentRescheduledPayload(
                    appointment_id=str(self.id.value),
                    patient_id=str(self._patient_id.value),
                    old_start_at=old_slot.start_at,
                    old_end_at=old_slot.end_at,
                    new_start_at=new_slot.start_at,
                    new_end_at=new_slot.end_at,
                    rescheduled_by=rescheduled_by,
                ),
            )
        )
        self._slot = new_slot

    # -- Read-only accessors ----------------------------------------------

    @property
    def patient_id(self) -> PatientId:
        return self._patient_id

    @property
    def doctor_id(self) -> DoctorId:
        return self._doctor_id

    @property
    def slot(self) -> TimeSlot:
        return self._slot

    @property
    def status(self) -> AppointmentStatus:
        return self._status

    @property
    def reason(self) -> str | None:
        return self._reason

    @property
    def booked_by(self) -> str:
        return self._booked_by

    @property
    def booked_at(self) -> datetime:
        return self._booked_at

    # -- Internals --------------------------------------------------------

    def _next_version(self) -> int:
        return self._version + len(self._pending_events) + 1

    def _transition_to(self, target: AppointmentStatus) -> None:
        allowed = _VALID_TRANSITIONS.get(self._status, set())
        if target not in allowed:
            raise PreconditionFailed(
                f"cannot transition appointment from "
                f"'{self._status.value}' to '{target.value}'"
            )
