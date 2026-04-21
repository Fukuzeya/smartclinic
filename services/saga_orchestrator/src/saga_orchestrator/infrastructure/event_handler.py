"""Saga Orchestrator — multi-context event handler (ACL intake).

This is the brain of the orchestrator.  It receives integration events from
**all four bounded contexts** (Scheduling, Clinical, Laboratory, Billing) and
drives the PatientVisitSaga state machine accordingly.

Design choices:
* Single `_dispatch` function routes by event_type to a dedicated handler.
* Every handler is wrapped in `idempotent_consumer` so replayed events are no-ops.
* The saga is keyed by `encounter_id`; the handler auto-creates the saga when
  the first scheduling check-in event arrives.
* All database access is inside the same transaction opened by the caller.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel.domain.domain_event import DomainEvent
from shared_kernel.infrastructure.inbox import idempotent_consumer
from shared_kernel.infrastructure.logging import get_logger
from shared_kernel.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork

from saga_orchestrator.domain.patient_visit_saga import PatientVisitSaga, SagaId
from saga_orchestrator.infrastructure.orm import SagaRow
from saga_orchestrator.infrastructure.repository import SqlAlchemySagaRepository

log = get_logger(__name__)

CONSUMER_NAME = "saga.patient_visit"

# ── routed event types ───────────────────────────────────────────────────────

_HANDLED = {
    "scheduling.appointment.checked_in.v1",
    "scheduling.appointment.cancelled.v1",
    "clinical.encounter.started.v1",
    "clinical.encounter.lab_order_placed.v1",
    "clinical.encounter.closed.v1",
    "laboratory.order.results_available.v1",
    "billing.invoice.issued.v1",
    "billing.invoice.payment_recorded.v1",
    "billing.invoice.voided.v1",
}


async def _handle(
    session: AsyncSession,
    event: DomainEvent,
    payload: dict[str, Any],
) -> None:
    repo = SqlAlchemySagaRepository(session)
    et = event.event_type

    # ── Saga creation ────────────────────────────────────────────────────────
    if et == "scheduling.appointment.checked_in.v1":
        encounter_id = payload.get("encounter_id", event.aggregate_id)
        patient_id = payload.get("patient_id", "")
        appointment_id = event.aggregate_id

        existing = await repo.get_by_encounter(encounter_id)
        if existing is not None:
            return  # already started

        saga_id = SagaId.new()
        saga = PatientVisitSaga.start(
            saga_id=saga_id,
            patient_id=patient_id,
            appointment_id=appointment_id,
            encounter_id=encounter_id,
        )
        await repo.add(saga)
        log.info("saga.started", saga_id=str(saga_id), encounter_id=encounter_id)
        return

    # ── All other events need an existing saga keyed by encounter_id ─────────
    encounter_id = (
        payload.get("encounter_id")
        or payload.get("aggregate_id")
        or event.aggregate_id
    )
    if not encounter_id:
        log.warning("saga.no_encounter_id", event_type=et)
        return

    saga = await repo.get_by_encounter(encounter_id)
    if saga is None:
        log.warning("saga.not_found", event_type=et, encounter_id=encounter_id)
        return

    if et == "scheduling.appointment.cancelled.v1":
        saga.on_appointment_cancelled()

    elif et == "clinical.encounter.started.v1":
        saga.on_encounter_started(encounter_id=encounter_id)

    elif et == "clinical.encounter.lab_order_placed.v1":
        lab_order_id = payload.get("lab_order_id", "")
        saga.on_lab_order_placed(lab_order_id=lab_order_id)

    elif et == "clinical.encounter.closed.v1":
        saga.on_encounter_closed()

    elif et == "laboratory.order.results_available.v1":
        lab_order_id = payload.get("lab_order_id", event.aggregate_id)
        saga.on_lab_results_available(lab_order_id=lab_order_id)

    elif et == "billing.invoice.issued.v1":
        invoice_id = event.aggregate_id
        saga.on_invoice_issued(invoice_id=invoice_id)

    elif et == "billing.invoice.payment_recorded.v1":
        if payload.get("new_status") == "paid":
            saga.on_invoice_paid()

    elif et == "billing.invoice.voided.v1":
        saga.on_invoice_voided()

    await repo.save(saga)
    log.info(
        "saga.step",
        saga_id=str(saga.id),
        step=saga.step.value,
        trigger=et,
    )


def make_event_handler(session_factory: async_sessionmaker[AsyncSession]):
    """Return a single dispatcher that handles events from all contexts."""

    async def _dispatch(event: DomainEvent, message) -> None:
        if event.event_type not in _HANDLED:
            return

        # Build a merged payload (some events encode encounter_id on aggregate_id)
        payload = {**event.payload}
        if event.event_type.startswith("clinical.encounter"):
            payload.setdefault("encounter_id", event.aggregate_id)
        if event.event_type.startswith("laboratory."):
            payload["lab_order_id"] = event.aggregate_id

        async with session_factory() as session:
            async with session.begin():
                async with idempotent_consumer(
                    session,
                    event_id=event.event_id,
                    consumer_name=CONSUMER_NAME,
                ) as is_new:
                    if not is_new:
                        return
                    await _handle(session, event, payload)

    return _dispatch
