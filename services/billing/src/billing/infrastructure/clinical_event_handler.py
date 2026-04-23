"""Billing — Clinical ACL intake.

Listens for ``clinical.encounter.closed.v1`` and auto-creates an invoice
with a consultation charge for the encounter.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel.domain.domain_event import DomainEvent
from shared_kernel.infrastructure.inbox import idempotent_consumer
from shared_kernel.infrastructure.logging import get_logger
from shared_kernel.types.identifiers import BillId
from shared_kernel.types.money import Currency, Money

from billing.domain.invoice import Invoice
from billing.domain.value_objects import ChargeCategory, ChargeLine
from billing.infrastructure.orm import InvoiceRow
from billing.infrastructure.repository import SqlAlchemyInvoiceRepository

log = get_logger(__name__)

CONSUMER_NAME = "billing.clinical_intake"

# Default consultation fee — in production this would come from a fee schedule
_DEFAULT_CONSULTATION_FEE = Money.of(Decimal("20.00"), Currency.USD)


async def handle_encounter_closed(
    session: AsyncSession, payload: dict[str, Any], event_id: uuid.UUID
) -> None:
    async with idempotent_consumer(session, event_id=event_id, consumer_name=CONSUMER_NAME) as is_new:
        if not is_new:
            return

        encounter_id = payload.get("encounter_id", "")
        patient_id = payload.get("patient_id", "")

        # Idempotent: skip if an invoice already exists for this encounter
        repo = SqlAlchemyInvoiceRepository(session)
        existing = await repo.get_by_encounter(encounter_id)
        if existing is not None:
            log.info("billing.invoice_already_exists", encounter_id=encounter_id)
            return

        invoice_id = BillId.new()
        invoice = Invoice.create(
            invoice_id=invoice_id,
            patient_id=patient_id,
            encounter_id=encounter_id,
            currency=Currency.USD,
        )
        invoice.add_charge(ChargeLine(
            category=ChargeCategory.CONSULTATION,
            description="Outpatient consultation",
            unit_price=_DEFAULT_CONSULTATION_FEE,
            quantity=1,
            reference_id=encounter_id,
        ))

        row = InvoiceRow(
            invoice_id=invoice_id.value,
            patient_id=patient_id,
            encounter_id=encounter_id,
            currency=Currency.USD.value,
            status=invoice.status.value,
            lines=[ln.model_dump(mode="json") for ln in invoice.lines],
            payments=[],
            version=0,
        )
        session.add(row)
        log.info("billing.invoice_created", invoice_id=str(invoice_id), encounter_id=encounter_id)


def make_clinical_event_handler(session_factory: async_sessionmaker[AsyncSession]):
    async def _dispatch(event: DomainEvent, message) -> None:
        if event.event_type != "clinical.encounter.closed.v1":
            return
        payload = {**event.payload, "encounter_id": event.aggregate_id}
        async with session_factory() as session:
            async with session.begin():
                await handle_encounter_closed(session, payload, event.event_id)
    return _dispatch
