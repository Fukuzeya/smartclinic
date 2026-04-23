"""Laboratory — Clinical event handler (ACL intake)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel.domain.domain_event import DomainEvent
from shared_kernel.infrastructure.inbox import idempotent_consumer
from shared_kernel.infrastructure.logging import get_logger
from shared_kernel.types.identifiers import LabOrderId

from laboratory.domain.lab_order import LabOrder
from laboratory.domain.value_objects import LabOrderLine
from laboratory.infrastructure.orm import LabOrderRow

log = get_logger(__name__)

CONSUMER_NAME = "laboratory.clinical_order_intake"


async def handle_lab_order_placed(
    session: AsyncSession, payload: dict[str, Any], event_id: uuid.UUID
) -> None:
    async with idempotent_consumer(session, event_id=event_id, consumer_name=CONSUMER_NAME) as is_new:
        if not is_new:
            return
        lab_order_id = LabOrderId.parse(payload["lab_order_id"])
        lines = [LabOrderLine.model_validate(t) for t in payload.get("tests", [])]
        order = LabOrder.receive(
            order_id=lab_order_id,
            patient_id=payload["patient_id"],
            encounter_id=payload.get("encounter_id", ""),
            lines=lines,
            ordered_by=payload.get("ordered_by", ""),
        )
        row = LabOrderRow(
            order_id=order.id.value,
            patient_id=order.patient_id,
            encounter_id=order.encounter_id,
            ordered_by=payload.get("ordered_by", ""),
            lines=[ln.model_dump(mode="json") for ln in order.lines],
            results=[],
            status=order.status.value,
            version=0,
        )
        session.add(row)
        log.info("laboratory.order_received", order_id=str(lab_order_id))


def make_clinical_event_handler(session_factory: async_sessionmaker[AsyncSession]):
    async def _dispatch(event: DomainEvent, message) -> None:
        if event.event_type != "clinical.encounter.lab_order_placed.v1":
            return
        payload = {**event.payload, "encounter_id": event.aggregate_id}
        async with session_factory() as session:
            async with session.begin():
                await handle_lab_order_placed(session, payload, event.event_id)
    return _dispatch
