"""CQRS read-side projections for the Clinical context.

This module contains the event handlers that subscribe to ``clinical.*``
routing keys and maintain the ``encounter_summaries`` read model.  Each
handler is wrapped in an idempotent consumer guard from the shared kernel so
duplicate event deliveries (RabbitMQ at-least-once) are safely skipped.

The projection is intentionally simple — it is a denormalised summary table
optimised for the list and detail views.  It is acceptable to rebuild it by
replaying the full event store if a schema migration requires it (a natural
benefit of Event Sourcing: the event log is the ground truth).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel.infrastructure.inbox import idempotent_consumer
from shared_kernel.infrastructure.logging import get_logger

from clinical.infrastructure.orm import EncounterSummaryRow

log = get_logger(__name__)

CONSUMER_NAME = "clinical.encounter_summary_projection"


async def handle_encounter_started(
    session: AsyncSession, payload: dict[str, Any], event_id: uuid.UUID
) -> None:
    async with idempotent_consumer(session, event_id=event_id, consumer_name=CONSUMER_NAME) as is_new:
        if not is_new:
            return
        enc_id = uuid.UUID(payload["aggregate_id"]) if "aggregate_id" in payload else uuid.UUID(payload.get("encounter_id", ""))
        row = EncounterSummaryRow(
            encounter_id=enc_id,
            patient_id=payload["patient_id"],
            doctor_id=payload["doctor_id"],
            appointment_id=payload.get("appointment_id"),
            status="in_progress",
            started_at=datetime.now(UTC),
            last_updated_at=datetime.now(UTC),
        )
        session.add(row)
        log.info("projection.encounter_started", encounter_id=str(enc_id))


async def handle_vital_signs_recorded(
    session: AsyncSession, payload: dict[str, Any], event_id: uuid.UUID
) -> None:
    async with idempotent_consumer(session, event_id=event_id, consumer_name=CONSUMER_NAME) as is_new:
        if not is_new:
            return
        enc_id = _encounter_id_from(payload)
        row = await _get_row(session, enc_id)
        if row:
            row.vital_signs_count += 1
            row.last_updated_at = datetime.now(UTC)


async def handle_soap_note_added(
    session: AsyncSession, payload: dict[str, Any], event_id: uuid.UUID
) -> None:
    async with idempotent_consumer(session, event_id=event_id, consumer_name=CONSUMER_NAME) as is_new:
        if not is_new:
            return
        enc_id = _encounter_id_from(payload)
        row = await _get_row(session, enc_id)
        if row:
            row.notes_count += 1
            row.last_updated_at = datetime.now(UTC)


async def handle_diagnosis_recorded(
    session: AsyncSession, payload: dict[str, Any], event_id: uuid.UUID
) -> None:
    async with idempotent_consumer(session, event_id=event_id, consumer_name=CONSUMER_NAME) as is_new:
        if not is_new:
            return
        enc_id = _encounter_id_from(payload)
        row = await _get_row(session, enc_id)
        if row:
            row.diagnoses_count += 1
            if payload.get("is_primary"):
                row.primary_icd10 = payload.get("icd10_code", {}).get("code")
            row.last_updated_at = datetime.now(UTC)


async def handle_prescription_issued(
    session: AsyncSession, payload: dict[str, Any], event_id: uuid.UUID
) -> None:
    async with idempotent_consumer(session, event_id=event_id, consumer_name=CONSUMER_NAME) as is_new:
        if not is_new:
            return
        enc_id = _encounter_id_from(payload)
        row = await _get_row(session, enc_id)
        if row:
            row.has_prescription = True
            row.last_updated_at = datetime.now(UTC)


async def handle_lab_order_placed(
    session: AsyncSession, payload: dict[str, Any], event_id: uuid.UUID
) -> None:
    async with idempotent_consumer(session, event_id=event_id, consumer_name=CONSUMER_NAME) as is_new:
        if not is_new:
            return
        enc_id = _encounter_id_from(payload)
        row = await _get_row(session, enc_id)
        if row:
            row.has_lab_order = True
            row.last_updated_at = datetime.now(UTC)


async def handle_encounter_closed(
    session: AsyncSession, payload: dict[str, Any], event_id: uuid.UUID
) -> None:
    async with idempotent_consumer(session, event_id=event_id, consumer_name=CONSUMER_NAME) as is_new:
        if not is_new:
            return
        enc_id = _encounter_id_from(payload)
        row = await _get_row(session, enc_id)
        if row:
            row.status = "closed"
            row.closed_at = datetime.now(UTC)
            row.primary_icd10 = payload.get("primary_icd10") or row.primary_icd10
            row.has_prescription = payload.get("has_prescription", row.has_prescription)
            row.has_lab_order = payload.get("has_lab_order", row.has_lab_order)
            row.last_updated_at = datetime.now(UTC)


async def handle_encounter_voided(
    session: AsyncSession, payload: dict[str, Any], event_id: uuid.UUID
) -> None:
    async with idempotent_consumer(session, event_id=event_id, consumer_name=CONSUMER_NAME) as is_new:
        if not is_new:
            return
        enc_id = _encounter_id_from(payload)
        row = await _get_row(session, enc_id)
        if row:
            row.status = "voided"
            row.last_updated_at = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Event → handler dispatch map (keyed by routing-key / event_type)

EVENT_HANDLERS: dict[str, Callable[..., Any]] = {
    "clinical.encounter.started.v1": handle_encounter_started,
    "clinical.encounter.vital_signs_recorded.v1": handle_vital_signs_recorded,
    "clinical.encounter.soap_note_added.v1": handle_soap_note_added,
    "clinical.encounter.diagnosis_recorded.v1": handle_diagnosis_recorded,
    "clinical.encounter.prescription_issued.v1": handle_prescription_issued,
    "clinical.encounter.lab_order_placed.v1": handle_lab_order_placed,
    "clinical.encounter.closed.v1": handle_encounter_closed,
    "clinical.encounter.voided.v1": handle_encounter_voided,
}


def make_projection_handler(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[dict[str, Any]], Any]:
    """Return a single callable that routes incoming events to the right handler."""

    async def _dispatch(message: dict[str, Any]) -> None:
        event_type = message.get("event_type", "")
        handler = EVENT_HANDLERS.get(event_type)
        if handler is None:
            log.debug("projection.unknown_event", event_type=event_type)
            return
        event_id = uuid.UUID(message["event_id"])
        payload = message.get("payload", {})
        # Inject aggregate_id into payload so handlers can locate the row.
        payload = {**payload, "aggregate_id": message.get("aggregate_id", "")}
        async with session_factory() as session:
            async with session.begin():
                await handler(session, payload, event_id)
        log.debug("projection.applied", event_type=event_type, event_id=str(event_id))

    return _dispatch


# ---------------------------------------------------------------------------
# Private helpers

def _encounter_id_from(payload: dict[str, Any]) -> uuid.UUID:
    return uuid.UUID(payload["aggregate_id"])


async def _get_row(
    session: AsyncSession, encounter_id: uuid.UUID
) -> EncounterSummaryRow | None:
    return (
        await session.execute(
            select(EncounterSummaryRow).where(
                EncounterSummaryRow.encounter_id == encounter_id
            )
        )
    ).scalar_one_or_none()
