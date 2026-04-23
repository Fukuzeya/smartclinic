from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared_kernel.domain.exceptions import ConcurrencyConflict, NotFound

from saga_orchestrator.domain.patient_visit_saga import PatientVisitSaga, SagaId
from saga_orchestrator.domain.value_objects import SagaContext, SagaStatus, SagaStep
from saga_orchestrator.infrastructure.orm import SagaRow


class SqlAlchemySagaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, saga_id: SagaId) -> PatientVisitSaga:
        row = (await self._session.execute(
            select(SagaRow).where(SagaRow.saga_id == saga_id.value)
        )).scalar_one_or_none()
        if row is None:
            raise NotFound(f"Saga {saga_id} not found")
        return _row_to_aggregate(row)

    async def get_by_encounter(self, encounter_id: str) -> PatientVisitSaga | None:
        row = (await self._session.execute(
            select(SagaRow).where(SagaRow.encounter_id == encounter_id)
        )).scalar_one_or_none()
        if row is None:
            return None
        return _row_to_aggregate(row)

    async def update_encounter_id(self, saga_id: SagaId, new_encounter_id: str) -> None:
        """Re-key the saga row from appointment_id to the real encounter_id."""
        row = (await self._session.execute(
            select(SagaRow).where(SagaRow.saga_id == saga_id.value)
        )).scalar_one_or_none()
        if row is not None:
            row.encounter_id = new_encounter_id
            await self._session.flush()

    async def add(self, saga: PatientVisitSaga) -> None:
        # Pre-compute post-commit version — UoW bumps after flush.
        final_version = saga.version + len(saga.peek_domain_events())
        row = SagaRow(
            saga_id=saga.id.value,
            patient_id=saga.patient_id,
            encounter_id=saga.context.encounter_id or "",
            step=saga.step.value,
            status=saga.status.value,
            context=saga.context.model_dump(mode="json"),
            version=final_version,
        )
        self._session.add(row)
        await self._session.flush()

    async def save(self, saga: PatientVisitSaga) -> None:
        row = (await self._session.execute(
            select(SagaRow).where(
                SagaRow.saga_id == saga.id.value
            )
        )).scalar_one_or_none()
        if row is None:
            raise NotFound(f"Saga {saga.id} not found for save")
        if row.version != saga.version:
            raise ConcurrencyConflict(f"Saga {saga.id}: version conflict")

        row.step = saga.step.value
        row.status = saga.status.value
        row.context = saga.context.model_dump(mode="json")
        row.version = saga.version + len(saga.peek_domain_events())

        if saga.status in (SagaStatus.COMPLETED, SagaStatus.CANCELLED):
            if row.completed_at is None:
                row.completed_at = datetime.now(UTC)

        await self._session.flush()


def _row_to_aggregate(row: SagaRow) -> PatientVisitSaga:
    return PatientVisitSaga.rehydrate(
        saga_id=SagaId.parse(str(row.saga_id)),
        version=row.version,
        patient_id=row.patient_id,
        step=SagaStep(row.step),
        status=SagaStatus(row.status),
        context=SagaContext.model_validate(row.context),
    )
