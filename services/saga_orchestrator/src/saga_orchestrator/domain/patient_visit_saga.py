"""Patient Visit Saga aggregate (ADR 0005 — Saga Orchestrator pattern).

This aggregate is the single source of truth for the cross-context Patient
Visit lifecycle.  It is driven purely by integration events arriving from
Scheduling, Clinical, Laboratory, and Billing.  It never issues commands
directly — instead it records domain events that the Saga Orchestrator service
publishes on the bus, where each bounded context's own handler acts.

State machine::

    AWAITING_ENCOUNTER  ──(encounter started)──────────────────► ENCOUNTER_OPEN
    ENCOUNTER_OPEN      ──(lab order placed)───────────────────► AWAITING_LAB
    ENCOUNTER_OPEN      ──(encounter closed, no labs)──────────► AWAITING_PAYMENT
    AWAITING_LAB        ──(lab completed, encounter not closed)─► AWAITING_LAB (stays)
    AWAITING_LAB        ──(encounter closed)───────────────────► AWAITING_LAB (stays, waits for labs)
    AWAITING_LAB        ──(all labs done AND encounter closed)──► AWAITING_PAYMENT
    AWAITING_PAYMENT    ──(invoice paid in full)────────────────► COMPLETED
    (any active state)  ──(appointment cancelled / void)────────► CANCELLED

Invariants:
* Only one saga per appointment.
* Terminal states (COMPLETED, CANCELLED) cannot be advanced.
* The saga context accumulates correlated ids from each context.
"""

from __future__ import annotations

import uuid

from shared_kernel.domain.aggregate_root import AggregateRoot
from shared_kernel.domain.entity import Entity
from shared_kernel.domain.exceptions import InvariantViolation, PreconditionFailed
from shared_kernel.types.identifiers import BillId

from saga_orchestrator.domain.events import (
    PatientVisitSagaCancelledV1,
    PatientVisitSagaCompletedV1,
    PatientVisitSagaStartedV1,
    SagaStepAdvancedV1,
)
from saga_orchestrator.domain.value_objects import SagaContext, SagaStatus, SagaStep

_TERMINAL = {SagaStep.COMPLETED, SagaStep.CANCELLED}


class SagaId(BillId):
    """Typed identifier for a PatientVisitSaga.

    Reuses BillId's UUID infrastructure — the 'saga' prefix differentiates
    it at the type-system level and in log output.
    """
    # We cannot change _prefix on BillId, so we create our own subtype.
    pass


# Use a standalone identifier to avoid coupling to Billing's BillId semantics
import uuid as _uuid
from shared_kernel.types.identifiers import Identifier as _Identifier
from typing import ClassVar as _ClassVar


class SagaId(_Identifier):  # type: ignore[no-redef]
    _prefix: _ClassVar[str] = "saga"


class PatientVisitSaga(AggregateRoot[SagaId]):
    """Orchestrator for the Patient Visit lifecycle."""

    # ─────────────────────────────────────────── factory / rehydration ───────

    @classmethod
    def start(
        cls,
        *,
        saga_id: SagaId,
        patient_id: str,
        appointment_id: str,
        encounter_id: str,
    ) -> PatientVisitSaga:
        """Create a new saga when an appointment is checked in."""
        instance = cls.__new__(cls)
        Entity.__init__(instance, id=saga_id)
        instance._version = 0
        instance._pending_events = []
        instance._patient_id = patient_id
        instance._step = SagaStep.AWAITING_ENCOUNTER
        instance._status = SagaStatus.ACTIVE
        instance._context = SagaContext(
            appointment_id=appointment_id,
            encounter_id=encounter_id,
        )
        instance._record(PatientVisitSagaStartedV1.build(
            saga_id=uuid.UUID(str(saga_id)),
            aggregate_version=instance._next_version(),
            patient_id=patient_id,
            appointment_id=appointment_id,
        ))
        return instance

    @classmethod
    def rehydrate(
        cls,
        *,
        saga_id: SagaId,
        version: int,
        patient_id: str,
        step: SagaStep,
        status: SagaStatus,
        context: SagaContext,
    ) -> PatientVisitSaga:
        instance = cls.__new__(cls)
        Entity.__init__(instance, id=saga_id)
        instance._version = version
        instance._pending_events = []
        instance._patient_id = patient_id
        instance._step = step
        instance._status = status
        instance._context = context
        return instance

    # ─────────────────────────────────────────── integration event handlers ──
    # Each method corresponds to one integration event type received on the bus.

    def on_encounter_started(self, *, encounter_id: str) -> None:
        """Clinical: doctor opened the encounter."""
        self._assert_active()
        if self._step != SagaStep.AWAITING_ENCOUNTER:
            return  # idempotent
        self._context = SagaContext(**{
            **self._context.model_dump(),
            "encounter_id": encounter_id,
        })
        self._advance(SagaStep.ENCOUNTER_OPEN, "clinical.encounter.started.v1")

    def on_lab_order_placed(self, *, lab_order_id: str) -> None:
        """Clinical: a lab order was added to the encounter."""
        self._assert_active()
        if self._step in _TERMINAL:
            return
        current_ids = list(self._context.lab_order_ids)
        if lab_order_id not in current_ids:
            current_ids.append(lab_order_id)
        self._context = SagaContext(**{
            **self._context.model_dump(),
            "lab_order_ids": current_ids,
        })
        if self._step == SagaStep.ENCOUNTER_OPEN:
            self._advance(SagaStep.AWAITING_LAB, "clinical.encounter.lab_order_placed.v1")

    def on_encounter_closed(self) -> None:
        """Clinical: doctor closed/signed the encounter."""
        self._assert_active()
        self._context = SagaContext(**{
            **self._context.model_dump(),
            "encounter_closed": True,
        })
        if self._step == SagaStep.ENCOUNTER_OPEN:
            # No labs were ordered — go straight to payment
            self._advance(SagaStep.AWAITING_PAYMENT, "clinical.encounter.closed.v1")
        elif self._step == SagaStep.AWAITING_LAB:
            if self._context.all_labs_completed:
                self._advance(SagaStep.AWAITING_PAYMENT, "clinical.encounter.closed.v1")
            # else: remain AWAITING_LAB until all labs are done

    def on_lab_results_available(self, *, lab_order_id: str) -> None:
        """Laboratory: results for a lab order are available."""
        self._assert_active()
        completed = list(self._context.lab_orders_completed)
        if lab_order_id not in completed:
            completed.append(lab_order_id)
        self._context = SagaContext(**{
            **self._context.model_dump(),
            "lab_orders_completed": completed,
        })
        if self._step == SagaStep.AWAITING_LAB:
            if self._context.all_labs_completed and self._context.encounter_closed:
                self._advance(SagaStep.AWAITING_PAYMENT, "laboratory.order.results_available.v1")

    def on_invoice_issued(self, *, invoice_id: str) -> None:
        """Billing: the invoice has been issued to the patient."""
        self._assert_active()
        self._context = SagaContext(**{
            **self._context.model_dump(),
            "invoice_id": invoice_id,
        })
        # Step stays at AWAITING_PAYMENT — invoice issued but not yet paid

    def on_invoice_paid(self) -> None:
        """Billing: invoice has been paid in full."""
        self._assert_active()
        if self._step != SagaStep.AWAITING_PAYMENT:
            return  # unexpected, ignore
        self._step = SagaStep.COMPLETED
        self._status = SagaStatus.COMPLETED
        self._record(PatientVisitSagaCompletedV1.build(
            saga_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            patient_id=self._patient_id,
            encounter_id=self._context.encounter_id or "",
        ))

    def on_appointment_cancelled(self) -> None:
        """Scheduling: appointment was cancelled."""
        if self._step in _TERMINAL:
            return
        self._cancel("Appointment cancelled", "scheduling.appointment.cancelled.v1")

    def on_invoice_voided(self) -> None:
        """Billing: invoice was voided (write-off)."""
        if self._step in _TERMINAL:
            return
        self._cancel("Invoice voided", "billing.invoice.voided.v1")

    # ─────────────────────────────────────────── read properties ─────────────

    @property
    def step(self) -> SagaStep:
        return self._step

    @property
    def status(self) -> SagaStatus:
        return self._status

    @property
    def patient_id(self) -> str:
        return self._patient_id

    @property
    def context(self) -> SagaContext:
        return self._context

    # ─────────────────────────────────────────── helpers ─────────────────────

    def _advance(self, to: SagaStep, trigger: str) -> None:
        from_step = self._step
        self._step = to
        self._record(SagaStepAdvancedV1.build(
            saga_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            from_step=from_step.value,
            to_step=to.value,
            trigger_event_type=trigger,
        ))

    def _cancel(self, reason: str, trigger: str) -> None:
        self._step = SagaStep.CANCELLED
        self._status = SagaStatus.CANCELLED
        self._record(PatientVisitSagaCancelledV1.build(
            saga_id=uuid.UUID(str(self.id)),
            aggregate_version=self._next_version(),
            reason=reason,
            trigger_event_type=trigger,
        ))

    def _next_version(self) -> int:
        return self._version + len(self._pending_events) + 1

    def _assert_active(self) -> None:
        if self._status != SagaStatus.ACTIVE:
            raise PreconditionFailed(
                f"Saga is {self._status} and cannot be advanced."
            )
