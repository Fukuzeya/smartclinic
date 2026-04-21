"""Unit tests for the PatientVisitSaga aggregate.

Covers:
* Full happy path: check-in → encounter → lab → results → closed → paid
* Happy path without labs: check-in → encounter → closed → paid
* Out-of-order: lab results arrive before encounter is closed
* Out-of-order: encounter closed before all labs complete
* All cancellation paths
* Idempotent event handling (duplicate events are safe)
* Version sequencing
* Rehydration
"""

from __future__ import annotations

import pytest

from shared_kernel.domain.exceptions import PreconditionFailed

from saga_orchestrator.domain.events import (
    PatientVisitSagaCancelledV1,
    PatientVisitSagaCompletedV1,
    PatientVisitSagaStartedV1,
    SagaStepAdvancedV1,
)
from saga_orchestrator.domain.patient_visit_saga import PatientVisitSaga, SagaId
from saga_orchestrator.domain.value_objects import SagaContext, SagaStatus, SagaStep

# ──────────────────────────────────────── helpers ────────────────────────────

PATIENT_ID = "patient-001"
APPOINTMENT_ID = "apt-001"
ENCOUNTER_ID = "enc-001"
LAB_ORDER_1 = "lab-001"
LAB_ORDER_2 = "lab-002"
INVOICE_ID = "bil-001"


def _start() -> PatientVisitSaga:
    return PatientVisitSaga.start(
        saga_id=SagaId.new(),
        patient_id=PATIENT_ID,
        appointment_id=APPOINTMENT_ID,
        encounter_id=ENCOUNTER_ID,
    )


def _steps(saga: PatientVisitSaga) -> list[str]:
    return [
        e.payload["to_step"]
        for e in saga.peek_domain_events()
        if isinstance(e, SagaStepAdvancedV1)
    ]


# ──────────────────────────────────────── creation ───────────────────────────

class TestStart:
    def test_creates_in_awaiting_encounter(self):
        saga = _start()
        assert saga.step == SagaStep.AWAITING_ENCOUNTER

    def test_status_is_active(self):
        saga = _start()
        assert saga.status == SagaStatus.ACTIVE

    def test_records_started_event(self):
        saga = _start()
        types = [type(e) for e in saga.peek_domain_events()]
        assert PatientVisitSagaStartedV1 in types

    def test_context_holds_appointment_id(self):
        saga = _start()
        assert saga.context.appointment_id == APPOINTMENT_ID

    def test_context_holds_encounter_id(self):
        saga = _start()
        assert saga.context.encounter_id == ENCOUNTER_ID


# ──────────────────────────────────────── happy path without labs ─────────────

class TestHappyPathNoLabs:
    def test_encounter_started_advances_to_encounter_open(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        assert saga.step == SagaStep.ENCOUNTER_OPEN

    def test_encounter_closed_goes_to_awaiting_payment(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_encounter_closed()
        assert saga.step == SagaStep.AWAITING_PAYMENT

    def test_invoice_paid_completes_saga(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_encounter_closed()
        saga.on_invoice_paid()
        assert saga.step == SagaStep.COMPLETED
        assert saga.status == SagaStatus.COMPLETED

    def test_completed_event_emitted(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_encounter_closed()
        saga.on_invoice_paid()
        types = [type(e) for e in saga.peek_domain_events()]
        assert PatientVisitSagaCompletedV1 in types

    def test_step_sequence_no_labs(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_encounter_closed()
        saga.on_invoice_paid()
        assert _steps(saga) == [
            SagaStep.ENCOUNTER_OPEN.value,
            SagaStep.AWAITING_PAYMENT.value,
        ]


# ──────────────────────────────────────── happy path with labs ───────────────

class TestHappyPathWithLabs:
    def test_lab_order_placed_moves_to_awaiting_lab(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_lab_order_placed(lab_order_id=LAB_ORDER_1)
        assert saga.step == SagaStep.AWAITING_LAB

    def test_two_labs_tracked_in_context(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_lab_order_placed(lab_order_id=LAB_ORDER_1)
        saga.on_lab_order_placed(lab_order_id=LAB_ORDER_2)
        assert set(saga.context.lab_order_ids) == {LAB_ORDER_1, LAB_ORDER_2}

    def test_results_before_close_does_not_advance(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_lab_order_placed(lab_order_id=LAB_ORDER_1)
        saga.on_lab_results_available(lab_order_id=LAB_ORDER_1)
        # Encounter not yet closed — must stay in AWAITING_LAB
        assert saga.step == SagaStep.AWAITING_LAB

    def test_close_before_results_stays_awaiting_lab(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_lab_order_placed(lab_order_id=LAB_ORDER_1)
        saga.on_encounter_closed()
        # Results not yet in — must stay in AWAITING_LAB
        assert saga.step == SagaStep.AWAITING_LAB

    def test_results_after_close_advances_to_awaiting_payment(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_lab_order_placed(lab_order_id=LAB_ORDER_1)
        saga.on_encounter_closed()
        saga.on_lab_results_available(lab_order_id=LAB_ORDER_1)
        assert saga.step == SagaStep.AWAITING_PAYMENT

    def test_close_after_results_advances_to_awaiting_payment(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_lab_order_placed(lab_order_id=LAB_ORDER_1)
        saga.on_lab_results_available(lab_order_id=LAB_ORDER_1)
        saga.on_encounter_closed()
        assert saga.step == SagaStep.AWAITING_PAYMENT

    def test_two_labs_both_must_complete(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_lab_order_placed(lab_order_id=LAB_ORDER_1)
        saga.on_lab_order_placed(lab_order_id=LAB_ORDER_2)
        saga.on_encounter_closed()
        saga.on_lab_results_available(lab_order_id=LAB_ORDER_1)
        assert saga.step == SagaStep.AWAITING_LAB  # still one pending
        saga.on_lab_results_available(lab_order_id=LAB_ORDER_2)
        assert saga.step == SagaStep.AWAITING_PAYMENT

    def test_full_path_with_labs(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_lab_order_placed(lab_order_id=LAB_ORDER_1)
        saga.on_encounter_closed()
        saga.on_lab_results_available(lab_order_id=LAB_ORDER_1)
        saga.on_invoice_issued(invoice_id=INVOICE_ID)
        saga.on_invoice_paid()
        assert saga.step == SagaStep.COMPLETED
        assert saga.context.invoice_id == INVOICE_ID


# ──────────────────────────────────────── idempotency ────────────────────────

class TestIdempotency:
    def test_duplicate_encounter_started_is_safe(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)  # duplicate
        assert saga.step == SagaStep.ENCOUNTER_OPEN

    def test_duplicate_lab_order_not_double_counted(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_lab_order_placed(lab_order_id=LAB_ORDER_1)
        saga.on_lab_order_placed(lab_order_id=LAB_ORDER_1)  # duplicate
        assert saga.context.lab_order_ids.count(LAB_ORDER_1) == 1

    def test_duplicate_lab_result_not_double_counted(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_lab_order_placed(lab_order_id=LAB_ORDER_1)
        saga.on_encounter_closed()
        saga.on_lab_results_available(lab_order_id=LAB_ORDER_1)
        saga.on_lab_results_available(lab_order_id=LAB_ORDER_1)  # duplicate
        assert saga.context.lab_orders_completed.count(LAB_ORDER_1) == 1


# ──────────────────────────────────────── cancellation ───────────────────────

class TestCancellation:
    def test_appointment_cancelled_from_awaiting_encounter(self):
        saga = _start()
        saga.on_appointment_cancelled()
        assert saga.step == SagaStep.CANCELLED
        assert saga.status == SagaStatus.CANCELLED

    def test_appointment_cancelled_from_encounter_open(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_appointment_cancelled()
        assert saga.step == SagaStep.CANCELLED

    def test_invoice_voided_cancels_saga(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_encounter_closed()
        saga.on_invoice_voided()
        assert saga.step == SagaStep.CANCELLED

    def test_records_cancelled_event(self):
        saga = _start()
        saga.on_appointment_cancelled()
        types = [type(e) for e in saga.peek_domain_events()]
        assert PatientVisitSagaCancelledV1 in types

    def test_cancelled_event_carries_trigger(self):
        saga = _start()
        saga.on_appointment_cancelled()
        ev = next(
            e for e in saga.peek_domain_events()
            if isinstance(e, PatientVisitSagaCancelledV1)
        )
        assert ev.payload["trigger_event_type"] == "scheduling.appointment.cancelled.v1"

    def test_cannot_advance_after_cancelled(self):
        saga = _start()
        saga.on_appointment_cancelled()
        with pytest.raises(PreconditionFailed):
            saga.on_encounter_started(encounter_id=ENCOUNTER_ID)

    def test_cannot_advance_after_completed(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_encounter_closed()
        saga.on_invoice_paid()
        with pytest.raises(PreconditionFailed):
            saga.on_invoice_paid()

    def test_duplicate_cancellation_is_safe(self):
        saga = _start()
        saga.on_appointment_cancelled()
        # Should not raise
        saga.on_appointment_cancelled()
        assert saga.step == SagaStep.CANCELLED


# ──────────────────────────────────────── version sequencing ─────────────────

class TestVersionSequencing:
    def test_first_event_version_is_one(self):
        saga = _start()
        assert saga.peek_domain_events()[0].aggregate_version == 1

    def test_versions_are_monotonically_increasing(self):
        saga = _start()
        saga.on_encounter_started(encounter_id=ENCOUNTER_ID)
        saga.on_encounter_closed()
        versions = [e.aggregate_version for e in saga.peek_domain_events()]
        assert versions == sorted(versions)
        assert len(set(versions)) == len(versions)


# ──────────────────────────────────────── rehydration ────────────────────────

class TestRehydrate:
    def test_rehydrate_restores_step_and_status(self):
        saga = PatientVisitSaga.rehydrate(
            saga_id=SagaId.new(),
            version=4,
            patient_id=PATIENT_ID,
            step=SagaStep.AWAITING_PAYMENT,
            status=SagaStatus.ACTIVE,
            context=SagaContext(
                appointment_id=APPOINTMENT_ID,
                encounter_id=ENCOUNTER_ID,
                encounter_closed=True,
            ),
        )
        assert saga.step == SagaStep.AWAITING_PAYMENT
        assert saga.status == SagaStatus.ACTIVE

    def test_rehydrate_does_not_record_events(self):
        saga = PatientVisitSaga.rehydrate(
            saga_id=SagaId.new(),
            version=4,
            patient_id=PATIENT_ID,
            step=SagaStep.COMPLETED,
            status=SagaStatus.COMPLETED,
            context=SagaContext(),
        )
        assert len(saga.peek_domain_events()) == 0

    def test_rehydrate_restores_version(self):
        saga = PatientVisitSaga.rehydrate(
            saga_id=SagaId.new(),
            version=7,
            patient_id=PATIENT_ID,
            step=SagaStep.AWAITING_LAB,
            status=SagaStatus.ACTIVE,
            context=SagaContext(lab_order_ids=[LAB_ORDER_1]),
        )
        assert saga.version == 7


# ──────────────────────────────────────── SagaContext helpers ─────────────────

class TestSagaContext:
    def test_all_labs_completed_true_when_no_orders(self):
        ctx = SagaContext()
        assert ctx.all_labs_completed is True

    def test_all_labs_completed_false_when_pending(self):
        ctx = SagaContext(lab_order_ids=[LAB_ORDER_1])
        assert ctx.all_labs_completed is False

    def test_all_labs_completed_true_when_all_done(self):
        ctx = SagaContext(
            lab_order_ids=[LAB_ORDER_1, LAB_ORDER_2],
            lab_orders_completed=[LAB_ORDER_1, LAB_ORDER_2],
        )
        assert ctx.all_labs_completed is True

    def test_all_labs_completed_false_when_partial(self):
        ctx = SagaContext(
            lab_order_ids=[LAB_ORDER_1, LAB_ORDER_2],
            lab_orders_completed=[LAB_ORDER_1],
        )
        assert ctx.all_labs_completed is False
