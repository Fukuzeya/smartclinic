"""Unit tests for the Appointment aggregate."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from shared_kernel.domain.exceptions import InvariantViolation, PreconditionFailed
from shared_kernel.types.clock import FrozenClock
from shared_kernel.types.identifiers import AppointmentId, DoctorId, PatientId

from scheduling.domain.appointment import Appointment
from scheduling.domain.events import (
    AppointmentBooked,
    AppointmentCancelled,
    AppointmentCheckedIn,
    AppointmentNoShow,
    AppointmentRescheduled,
)
from scheduling.domain.value_objects import AppointmentStatus, CancellationReason, TimeSlot


NOW = datetime(2026, 4, 1, 8, 0, 0, tzinfo=UTC)
CLOCK = FrozenClock(at=NOW)
FUTURE_SLOT = TimeSlot(
    start_at=NOW + timedelta(hours=2),
    end_at=NOW + timedelta(hours=2, minutes=30),
)
PATIENT = PatientId.new()
DOCTOR = DoctorId.new()


def _book(**kwargs) -> Appointment:
    defaults = dict(
        patient_id=PATIENT,
        doctor_id=DOCTOR,
        slot=FUTURE_SLOT,
        booked_by="recep-001",
        clock=CLOCK,
    )
    return Appointment.book(**{**defaults, **kwargs})


class TestBook:
    def test_emits_booked_event(self) -> None:
        appt = _book()
        events = appt.peek_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], AppointmentBooked)

    def test_status_is_booked(self) -> None:
        assert _book().status == AppointmentStatus.BOOKED

    def test_rejects_past_slot(self) -> None:
        past_slot = TimeSlot(
            start_at=NOW - timedelta(hours=1),
            end_at=NOW - timedelta(minutes=30),
        )
        with pytest.raises(InvariantViolation, match="past"):
            _book(slot=past_slot)

    def test_rejects_empty_booked_by(self) -> None:
        with pytest.raises(InvariantViolation, match="booked_by"):
            _book(booked_by="")


class TestCheckIn:
    def test_emits_checked_in_event(self) -> None:
        appt = _book()
        appt.pull_domain_events()
        appt.check_in(checked_in_by="recep-001", clock=CLOCK)
        events = appt.peek_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], AppointmentCheckedIn)
        assert appt.status == AppointmentStatus.CHECKED_IN

    def test_cannot_cancel_after_checkin(self) -> None:
        appt = _book()
        appt.check_in(checked_in_by="recep-001", clock=CLOCK)
        with pytest.raises(PreconditionFailed):
            appt.cancel(
                reason=CancellationReason.PATIENT_REQUEST,
                cancelled_by="recep-001",
                clock=CLOCK,
            )

    def test_cannot_checkin_twice(self) -> None:
        appt = _book()
        appt.check_in(checked_in_by="recep-001", clock=CLOCK)
        with pytest.raises(PreconditionFailed):
            appt.check_in(checked_in_by="recep-001", clock=CLOCK)


class TestCancel:
    def test_emits_cancelled_event(self) -> None:
        appt = _book()
        appt.pull_domain_events()
        appt.cancel(
            reason=CancellationReason.PATIENT_REQUEST,
            cancelled_by="recep-001",
            clock=CLOCK,
        )
        events = appt.peek_domain_events()
        assert isinstance(events[0], AppointmentCancelled)
        assert appt.status == AppointmentStatus.CANCELLED

    def test_event_carries_reason(self) -> None:
        appt = _book()
        appt.cancel(
            reason=CancellationReason.DOCTOR_UNAVAILABLE,
            cancelled_by="recep-001",
            clock=CLOCK,
        )
        event = appt.peek_domain_events()[-1]
        assert event.payload["cancellation_reason"] == "doctor_unavailable"


class TestNoShow:
    def test_emits_no_show_event(self) -> None:
        appt = _book()
        appt.pull_domain_events()
        appt.mark_no_show(marked_by="recep-001", clock=CLOCK)
        events = appt.peek_domain_events()
        assert isinstance(events[0], AppointmentNoShow)
        assert appt.status == AppointmentStatus.NO_SHOW


class TestReschedule:
    def test_emits_rescheduled_event(self) -> None:
        appt = _book()
        appt.pull_domain_events()
        new_slot = TimeSlot(
            start_at=NOW + timedelta(days=1),
            end_at=NOW + timedelta(days=1, minutes=30),
        )
        appt.reschedule(new_slot=new_slot, rescheduled_by="recep-001", clock=CLOCK)
        events = appt.peek_domain_events()
        assert isinstance(events[0], AppointmentRescheduled)
        assert appt.slot == new_slot

    def test_cannot_reschedule_cancelled(self) -> None:
        appt = _book()
        appt.cancel(
            reason=CancellationReason.PATIENT_REQUEST,
            cancelled_by="recep-001",
            clock=CLOCK,
        )
        new_slot = TimeSlot(
            start_at=NOW + timedelta(days=1),
            end_at=NOW + timedelta(days=1, minutes=30),
        )
        with pytest.raises(PreconditionFailed):
            appt.reschedule(
                new_slot=new_slot, rescheduled_by="recep-001", clock=CLOCK
            )


class TestTimeSlot:
    def test_rejects_too_short(self) -> None:
        with pytest.raises(ValueError, match="5 minutes"):
            TimeSlot(
                start_at=NOW + timedelta(hours=1),
                end_at=NOW + timedelta(hours=1, minutes=2),
            )

    def test_rejects_end_before_start(self) -> None:
        with pytest.raises(ValueError):
            TimeSlot(
                start_at=NOW + timedelta(hours=2),
                end_at=NOW + timedelta(hours=1),
            )

    def test_overlap_detection(self) -> None:
        s1 = TimeSlot(
            start_at=NOW + timedelta(hours=1),
            end_at=NOW + timedelta(hours=2),
        )
        s2 = TimeSlot(
            start_at=NOW + timedelta(hours=1, minutes=30),
            end_at=NOW + timedelta(hours=2, minutes=30),
        )
        s3 = TimeSlot(
            start_at=NOW + timedelta(hours=3),
            end_at=NOW + timedelta(hours=4),
        )
        assert s1.overlaps(s2)
        assert not s1.overlaps(s3)

    def test_version_stamping_multi_event_transaction(self) -> None:
        appt = _book()
        # version=0, 1 pending event
        events = appt.peek_domain_events()
        assert events[0].aggregate_version == 1
