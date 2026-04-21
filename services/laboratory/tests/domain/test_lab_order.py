"""Unit tests for the LabOrder aggregate.

Covers:
* Happy-path lifecycle: PENDING → SAMPLE_COLLECTED → IN_PROGRESS → COMPLETED
* Critical-result alert emission
* All invariant violations (terminal state guard, ordering constraints)
* Cancellation at every valid state
* Event version sequencing
* Rehydration from persisted state
"""

from __future__ import annotations

import pytest

from shared_kernel.domain.exceptions import InvariantViolation, PreconditionFailed
from shared_kernel.types.identifiers import LabOrderId

from laboratory.domain.events import (
    CriticalResultAlertV1,
    LabOrderCancelledV1,
    LabOrderReceivedV1,
    LabResultsAvailableV1,
    ResultRecordedV1,
    SampleCollectedV1,
)
from laboratory.domain.lab_order import LabOrder
from laboratory.domain.value_objects import (
    Interpretation,
    LabOrderLine,
    LabResult,
    OrderStatus,
    ReferenceRange,
    SampleType,
)

# ──────────────────────────────────────── fixtures ───────────────────────────

ORDER_ID = LabOrderId.new()
PATIENT_ID = "patient-001"
ENCOUNTER_ID = "encounter-001"
LINES = [LabOrderLine(test_code="CBC", urgency="routine")]
TECHNICIAN = "tech-sub-001"
DOCTOR = "doctor-sub-001"


def _make_order(**kwargs) -> LabOrder:
    return LabOrder.receive(
        order_id=kwargs.get("order_id", ORDER_ID),
        patient_id=kwargs.get("patient_id", PATIENT_ID),
        encounter_id=kwargs.get("encounter_id", ENCOUNTER_ID),
        lines=kwargs.get("lines", LINES),
        ordered_by=kwargs.get("ordered_by", DOCTOR),
    )


def _normal_result(test_code: str = "CBC") -> LabResult:
    return LabResult(
        test_code=test_code,
        test_name="Complete Blood Count",
        value="12.5",
        unit="g/dL",
        interpretation=Interpretation.NORMAL,
        performed_by=TECHNICIAN,
    )


def _critical_result(test_code: str = "K") -> LabResult:
    return LabResult(
        test_code=test_code,
        test_name="Potassium",
        value="6.8",
        unit="mmol/L",
        interpretation=Interpretation.CRITICAL_HIGH,
        reference_range=ReferenceRange(lower=None, upper=None, note="3.5–5.0 mmol/L"),
        performed_by=TECHNICIAN,
    )


def _collect(order: LabOrder) -> None:
    order.collect_sample(sample_type=SampleType.BLOOD, collected_by=TECHNICIAN)


# ──────────────────────────────────────── construction ───────────────────────

class TestReceive:
    def test_creates_pending_order(self):
        order = _make_order()
        assert order.status == OrderStatus.PENDING

    def test_records_received_event(self):
        order = _make_order()
        events = order.peek_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], LabOrderReceivedV1)

    def test_received_event_carries_patient_id(self):
        order = _make_order()
        ev = order.peek_domain_events()[0]
        assert ev.payload["patient_id"] == PATIENT_ID

    def test_refuses_empty_lines(self):
        with pytest.raises(InvariantViolation, match="at least one test"):
            _make_order(lines=[])

    def test_stores_all_lines(self):
        lines = [
            LabOrderLine(test_code="CBC", urgency="routine"),
            LabOrderLine(test_code="LFT", urgency="urgent"),
        ]
        order = _make_order(lines=lines)
        assert len(order.lines) == 2


# ──────────────────────────────────────── sample collection ──────────────────

class TestCollectSample:
    def test_transitions_to_sample_collected(self):
        order = _make_order()
        _collect(order)
        assert order.status == OrderStatus.SAMPLE_COLLECTED

    def test_records_sample_collected_event(self):
        order = _make_order()
        _collect(order)
        event_types = [type(e) for e in order.peek_domain_events()]
        assert SampleCollectedV1 in event_types

    def test_event_carries_sample_type(self):
        order = _make_order()
        _collect(order)
        ev = next(e for e in order.peek_domain_events() if isinstance(e, SampleCollectedV1))
        assert ev.payload["sample_type"] == SampleType.BLOOD.value

    def test_cannot_collect_twice(self):
        order = _make_order()
        _collect(order)
        with pytest.raises(PreconditionFailed, match="already collected"):
            _collect(order)

    def test_cannot_collect_on_completed_order(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_normal_result())
        order.complete(reported_by=TECHNICIAN)
        with pytest.raises(PreconditionFailed):
            _collect(order)

    def test_cannot_collect_on_cancelled_order(self):
        order = _make_order()
        order.cancel(reason="test", cancelled_by=DOCTOR)
        with pytest.raises(PreconditionFailed):
            _collect(order)


# ──────────────────────────────────────── result recording ───────────────────

class TestRecordResult:
    def test_transitions_to_in_progress(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_normal_result())
        assert order.status == OrderStatus.IN_PROGRESS

    def test_records_result_event(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_normal_result())
        event_types = [type(e) for e in order.peek_domain_events()]
        assert ResultRecordedV1 in event_types

    def test_result_appended_to_results(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_normal_result())
        assert len(order.results) == 1

    def test_multiple_results_accumulate(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_normal_result("CBC"))
        order.record_result(result=_normal_result("LFT"))
        assert len(order.results) == 2

    def test_cannot_record_without_sample(self):
        order = _make_order()
        with pytest.raises(PreconditionFailed, match="sample"):
            order.record_result(result=_normal_result())

    def test_cannot_record_on_completed_order(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_normal_result())
        order.complete(reported_by=TECHNICIAN)
        with pytest.raises(PreconditionFailed):
            order.record_result(result=_normal_result())

    def test_cannot_record_on_cancelled_order(self):
        order = _make_order()
        order.cancel(reason="test", cancelled_by=DOCTOR)
        with pytest.raises(PreconditionFailed):
            order.record_result(result=_normal_result())


# ──────────────────────────────────────── critical results ───────────────────

class TestCriticalResults:
    def test_critical_result_emits_alert_event(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_critical_result())
        event_types = [type(e) for e in order.peek_domain_events()]
        assert CriticalResultAlertV1 in event_types

    def test_normal_result_does_not_emit_alert(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_normal_result())
        event_types = [type(e) for e in order.peek_domain_events()]
        assert CriticalResultAlertV1 not in event_types

    def test_critical_alert_carries_test_code(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_critical_result("K"))
        alert = next(e for e in order.peek_domain_events() if isinstance(e, CriticalResultAlertV1))
        assert alert.payload["test_code"] == "K"

    def test_critical_alert_carries_interpretation(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_critical_result())
        alert = next(e for e in order.peek_domain_events() if isinstance(e, CriticalResultAlertV1))
        assert alert.payload["interpretation"] == Interpretation.CRITICAL_HIGH.value

    def test_critical_alert_carries_patient_id(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_critical_result())
        alert = next(e for e in order.peek_domain_events() if isinstance(e, CriticalResultAlertV1))
        assert alert.payload["patient_id"] == PATIENT_ID

    def test_critical_low_also_triggers_alert(self):
        low_result = LabResult(
            test_code="GLU", test_name="Glucose", value="2.1", unit="mmol/L",
            interpretation=Interpretation.CRITICAL_LOW, performed_by=TECHNICIAN,
        )
        order = _make_order()
        _collect(order)
        order.record_result(result=low_result)
        event_types = [type(e) for e in order.peek_domain_events()]
        assert CriticalResultAlertV1 in event_types


# ──────────────────────────────────────── completion ─────────────────────────

class TestComplete:
    def test_completes_successfully_after_result(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_normal_result())
        order.complete(reported_by=TECHNICIAN)
        assert order.status == OrderStatus.COMPLETED

    def test_emits_results_available_event(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_normal_result())
        order.complete(reported_by=TECHNICIAN)
        event_types = [type(e) for e in order.peek_domain_events()]
        assert LabResultsAvailableV1 in event_types

    def test_results_available_carries_patient_and_encounter(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_normal_result())
        order.complete(reported_by=TECHNICIAN)
        ev = next(e for e in order.peek_domain_events() if isinstance(e, LabResultsAvailableV1))
        assert ev.payload["patient_id"] == PATIENT_ID
        assert ev.payload["encounter_id"] == ENCOUNTER_ID

    def test_results_available_flags_critical(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_critical_result())
        order.complete(reported_by=TECHNICIAN)
        ev = next(e for e in order.peek_domain_events() if isinstance(e, LabResultsAvailableV1))
        assert ev.payload["has_critical_results"] is True

    def test_results_available_no_critical_flag_for_normal(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_normal_result())
        order.complete(reported_by=TECHNICIAN)
        ev = next(e for e in order.peek_domain_events() if isinstance(e, LabResultsAvailableV1))
        assert ev.payload["has_critical_results"] is False

    def test_cannot_complete_without_results(self):
        order = _make_order()
        _collect(order)
        with pytest.raises(InvariantViolation, match="no recorded results"):
            order.complete(reported_by=TECHNICIAN)

    def test_cannot_complete_from_pending(self):
        order = _make_order()
        with pytest.raises(PreconditionFailed):
            order.complete(reported_by=TECHNICIAN)

    def test_cannot_complete_twice(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_normal_result())
        order.complete(reported_by=TECHNICIAN)
        with pytest.raises(PreconditionFailed):
            order.complete(reported_by=TECHNICIAN)


# ──────────────────────────────────────── cancellation ───────────────────────

class TestCancel:
    def test_cancels_from_pending(self):
        order = _make_order()
        order.cancel(reason="Duplicate order", cancelled_by=DOCTOR)
        assert order.status == OrderStatus.CANCELLED

    def test_cancels_from_sample_collected(self):
        order = _make_order()
        _collect(order)
        order.cancel(reason="Sample hemolysed", cancelled_by=TECHNICIAN)
        assert order.status == OrderStatus.CANCELLED

    def test_cancels_from_in_progress(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_normal_result())
        order.cancel(reason="Equipment failure", cancelled_by=TECHNICIAN)
        assert order.status == OrderStatus.CANCELLED

    def test_emits_cancelled_event(self):
        order = _make_order()
        order.cancel(reason="Test cancellation", cancelled_by=DOCTOR)
        event_types = [type(e) for e in order.peek_domain_events()]
        assert LabOrderCancelledV1 in event_types

    def test_cancelled_event_carries_reason(self):
        reason = "Patient discharged"
        order = _make_order()
        order.cancel(reason=reason, cancelled_by=DOCTOR)
        ev = next(e for e in order.peek_domain_events() if isinstance(e, LabOrderCancelledV1))
        assert ev.payload["reason"] == reason

    def test_cannot_cancel_completed_order(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_normal_result())
        order.complete(reported_by=TECHNICIAN)
        with pytest.raises(PreconditionFailed):
            order.cancel(reason="Too late", cancelled_by=DOCTOR)

    def test_cannot_cancel_twice(self):
        order = _make_order()
        order.cancel(reason="First", cancelled_by=DOCTOR)
        with pytest.raises(PreconditionFailed):
            order.cancel(reason="Second", cancelled_by=DOCTOR)


# ──────────────────────────────────────── version sequencing ─────────────────

class TestVersionSequencing:
    def test_first_event_version_is_one(self):
        order = _make_order()
        ev = order.peek_domain_events()[0]
        assert ev.aggregate_version == 1

    def test_each_event_increments_version(self):
        order = _make_order()
        _collect(order)
        order.record_result(result=_normal_result())
        versions = [e.aggregate_version for e in order.peek_domain_events()]
        assert versions == sorted(versions)
        assert len(set(versions)) == len(versions)

    def test_critical_result_produces_two_sequential_events(self):
        order = _make_order()
        _collect(order)
        events_before = len(order.peek_domain_events())
        order.record_result(result=_critical_result())
        new_events = order.peek_domain_events()[events_before:]
        assert len(new_events) == 2  # ResultRecordedV1 + CriticalResultAlertV1
        assert new_events[1].aggregate_version == new_events[0].aggregate_version + 1


# ──────────────────────────────────────── rehydration ────────────────────────

class TestRehydrate:
    def test_rehydrate_restores_status(self):
        from datetime import UTC, datetime
        order = LabOrder.rehydrate(
            order_id=ORDER_ID,
            version=3,
            patient_id=PATIENT_ID,
            encounter_id=ENCOUNTER_ID,
            lines=LINES,
            status=OrderStatus.IN_PROGRESS,
            sample_type=SampleType.BLOOD,
            results=[_normal_result()],
            received_at=datetime.now(UTC),
        )
        assert order.status == OrderStatus.IN_PROGRESS

    def test_rehydrate_does_not_record_events(self):
        from datetime import UTC, datetime
        order = LabOrder.rehydrate(
            order_id=ORDER_ID,
            version=5,
            patient_id=PATIENT_ID,
            encounter_id=ENCOUNTER_ID,
            lines=LINES,
            status=OrderStatus.COMPLETED,
            sample_type=SampleType.BLOOD,
            results=[_normal_result()],
            received_at=datetime.now(UTC),
        )
        assert len(order.peek_domain_events()) == 0

    def test_rehydrated_order_carries_correct_version(self):
        from datetime import UTC, datetime
        order = LabOrder.rehydrate(
            order_id=ORDER_ID,
            version=7,
            patient_id=PATIENT_ID,
            encounter_id=ENCOUNTER_ID,
            lines=LINES,
            status=OrderStatus.COMPLETED,
            sample_type=SampleType.BLOOD,
            results=[_normal_result()],
            received_at=datetime.now(UTC),
        )
        assert order.version == 7

    def test_rehydrated_completed_order_cannot_be_modified(self):
        from datetime import UTC, datetime
        order = LabOrder.rehydrate(
            order_id=ORDER_ID,
            version=5,
            patient_id=PATIENT_ID,
            encounter_id=ENCOUNTER_ID,
            lines=LINES,
            status=OrderStatus.COMPLETED,
            sample_type=SampleType.BLOOD,
            results=[_normal_result()],
            received_at=datetime.now(UTC),
        )
        with pytest.raises(PreconditionFailed):
            order.cancel(reason="Too late", cancelled_by=DOCTOR)
