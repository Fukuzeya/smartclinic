"""Billing — Laboratory ACL intake.

Listens for ``laboratory.order.results_available.v1`` and appends a lab-test
charge line to the encounter's invoice (if the invoice is still in DRAFT).

If the invoice has already been ISSUED, the charge is silently skipped and
logged — in production this would raise a billing exception handled by staff.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel.domain.domain_event import DomainEvent
from shared_kernel.infrastructure.inbox import idempotent_consumer
from shared_kernel.infrastructure.logging import get_logger
from shared_kernel.types.money import Currency, Money

from billing.domain.value_objects import ChargeCategory, ChargeLine, InvoiceStatus
from billing.infrastructure.repository import SqlAlchemyInvoiceRepository

log = get_logger(__name__)

CONSUMER_NAME = "billing.laboratory_intake"

# Default lab panel fee — real system uses a per-test fee schedule
_DEFAULT_LAB_FEE = Money.of(Decimal("15.00"), Currency.USD)


async def handle_results_available(
    session: AsyncSession, payload: dict[str, Any], event_id: uuid.UUID
) -> None:
    async with idempotent_consumer(session, event_id=event_id, consumer_name=CONSUMER_NAME) as is_new:
        if not is_new:
            return

        encounter_id = payload.get("encounter_id", "")
        order_id = payload.get("lab_order_id", str(event_id))
        result_count = int(payload.get("result_count", 1))

        repo = SqlAlchemyInvoiceRepository(session)
        invoice = await repo.get_by_encounter(encounter_id)
        if invoice is None:
            # Invoice may not yet exist (race condition); log and skip.
            # The outbox relay will retry; or staff raises a manual charge.
            log.warning("billing.no_invoice_for_lab_charge", encounter_id=encounter_id)
            return

        if invoice.status != InvoiceStatus.DRAFT:
            log.warning(
                "billing.invoice_not_draft_for_lab_charge",
                invoice_id=str(invoice.id),
                status=invoice.status.value,
            )
            return

        invoice.add_charge(ChargeLine(
            category=ChargeCategory.LAB_TEST,
            description=f"Laboratory tests ({result_count} panel{'s' if result_count > 1 else ''})",
            unit_price=_DEFAULT_LAB_FEE,
            quantity=result_count,
            reference_id=order_id,
        ))
        await repo.save(invoice)
        log.info(
            "billing.lab_charge_added",
            invoice_id=str(invoice.id),
            encounter_id=encounter_id,
            result_count=result_count,
        )


def make_laboratory_event_handler(session_factory: async_sessionmaker[AsyncSession]):
    async def _dispatch(event: DomainEvent, message) -> None:
        if event.event_type != "laboratory.order.results_available.v1":
            return
        payload = {**event.payload, "lab_order_id": event.aggregate_id}
        async with session_factory() as session:
            async with session.begin():
                await handle_results_available(session, payload, event.event_id)
    return _dispatch
