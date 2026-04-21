from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared_kernel.domain.exceptions import ConcurrencyConflict, NotFound
from shared_kernel.types.identifiers import LabOrderId

from laboratory.domain.lab_order import LabOrder
from laboratory.domain.value_objects import (
    LabOrderLine,
    LabResult,
    OrderStatus,
    SampleType,
)
from laboratory.infrastructure.orm import LabOrderRow


class SqlAlchemyLabOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, order_id: LabOrderId) -> LabOrder:
        row = (await self._session.execute(
            select(LabOrderRow).where(LabOrderRow.order_id == uuid.UUID(str(order_id)))
        )).scalar_one_or_none()
        if row is None:
            raise NotFound(f"Lab order {order_id} not found")
        return _row_to_aggregate(row)

    async def add(self, order: LabOrder) -> None:
        row = LabOrderRow(
            order_id=uuid.UUID(str(order.id)),
            patient_id=order.patient_id,
            encounter_id=order.encounter_id,
            ordered_by="",
            lines=[ln.model_dump(mode="json") for ln in order.lines],
            results=[],
            status=order.status.value,
            version=0,
        )
        self._session.add(row)
        await self._session.flush()

    async def save(self, order: LabOrder) -> None:
        row = (await self._session.execute(
            select(LabOrderRow).where(LabOrderRow.order_id == uuid.UUID(str(order.id)))
        )).scalar_one_or_none()
        if row is None:
            raise NotFound(f"Lab order {order.id} not found for save")
        if row.version != order.version:
            raise ConcurrencyConflict(f"Lab order {order.id}: version conflict")
        row.status = order.status.value
        row.sample_type = order._sample_type.value if order._sample_type else None
        row.results = [r.model_dump(mode="json") for r in order.results]
        row.version = order.version + len(order.peek_domain_events())
        if order.status == OrderStatus.COMPLETED:
            row.completed_at = datetime.now(UTC)
        await self._session.flush()


def _row_to_aggregate(row: LabOrderRow) -> LabOrder:
    lines = [LabOrderLine.model_validate(ln) for ln in row.lines]
    results = [LabResult.model_validate(r) for r in (row.results or [])]
    return LabOrder.rehydrate(
        order_id=LabOrderId.parse(str(row.order_id)),
        version=row.version,
        patient_id=row.patient_id,
        encounter_id=row.encounter_id,
        lines=lines,
        status=OrderStatus(row.status),
        sample_type=SampleType(row.sample_type) if row.sample_type else None,
        results=results,
        received_at=row.received_at,
    )
