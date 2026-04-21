"""Laboratory command handlers.

Each handler:
1. Opens a Unit-of-Work (transaction).
2. Loads the ``LabOrder`` aggregate.
3. Calls the appropriate domain command.
4. Persists the updated aggregate (outbox write included in the same tx).
5. Commits.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from shared_kernel.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork

from laboratory.application.commands import (
    CancelOrderCommand,
    CollectSampleCommand,
    CompleteOrderCommand,
    RecordResultCommand,
)
from laboratory.domain.value_objects import (
    Interpretation,
    LabResult,
    ReferenceRange,
    SampleType,
)
from laboratory.infrastructure.repository import SqlAlchemyLabOrderRepository


class CollectSampleHandler:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, cmd: CollectSampleCommand) -> None:
        async with self._uow_factory() as uow:
            repo = SqlAlchemyLabOrderRepository(uow.session)
            order = await repo.get(cmd.order_id)
            order.collect_sample(
                sample_type=SampleType(cmd.sample_type),
                collected_by=cmd.collected_by,
            )
            await repo.save(order)
            uow.register(order)
            await uow.commit()


class RecordResultHandler:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, cmd: RecordResultCommand) -> None:
        ref_range: ReferenceRange | None = None
        if (
            cmd.reference_range_lower is not None
            or cmd.reference_range_upper is not None
        ):
            def _dec(v: str | None) -> Decimal | None:
                if v is None:
                    return None
                try:
                    return Decimal(v)
                except InvalidOperation:
                    return None

            ref_range = ReferenceRange(
                lower=_dec(cmd.reference_range_lower),
                upper=_dec(cmd.reference_range_upper),
                unit=cmd.reference_range_unit or "",
            )

        result = LabResult(
            test_code=cmd.test_code,
            test_name=cmd.test_name,
            value=cmd.value,
            unit=cmd.unit,
            reference_range=ref_range,
            interpretation=Interpretation(cmd.interpretation),
            notes=cmd.notes,
            performed_by=cmd.performed_by,
        )

        async with self._uow_factory() as uow:
            repo = SqlAlchemyLabOrderRepository(uow.session)
            order = await repo.get(cmd.order_id)
            order.record_result(result=result)
            await repo.save(order)
            uow.register(order)
            await uow.commit()


class CompleteOrderHandler:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, cmd: CompleteOrderCommand) -> None:
        async with self._uow_factory() as uow:
            repo = SqlAlchemyLabOrderRepository(uow.session)
            order = await repo.get(cmd.order_id)
            order.complete(reported_by=cmd.reported_by)
            await repo.save(order)
            uow.register(order)
            await uow.commit()


class CancelOrderHandler:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, cmd: CancelOrderCommand) -> None:
        async with self._uow_factory() as uow:
            repo = SqlAlchemyLabOrderRepository(uow.session)
            order = await repo.get(cmd.order_id)
            order.cancel(reason=cmd.reason, cancelled_by=cmd.cancelled_by)
            await repo.save(order)
            uow.register(order)
            await uow.commit()
