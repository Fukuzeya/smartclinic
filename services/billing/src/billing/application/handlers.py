"""Billing command handlers."""

from __future__ import annotations

from decimal import Decimal

from shared_kernel.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork
from shared_kernel.types.money import Currency, Money

from billing.application.commands import (
    AddChargeCommand,
    IssueInvoiceCommand,
    RecordPaymentCommand,
    VoidInvoiceCommand,
)
from billing.domain.value_objects import ChargeCategory, ChargeLine, PaymentMethod
from billing.infrastructure.repository import SqlAlchemyInvoiceRepository


class AddChargeHandler:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, cmd: AddChargeCommand) -> None:
        line = ChargeLine(
            category=ChargeCategory(cmd.category),
            description=cmd.description,
            unit_price=Money(
                amount=Decimal(cmd.unit_price_amount),
                currency=Currency(cmd.unit_price_currency),
            ),
            quantity=cmd.quantity,
            reference_id=cmd.reference_id,
        )
        async with self._uow_factory() as uow:
            repo = SqlAlchemyInvoiceRepository(uow.session)
            invoice = await repo.get(cmd.invoice_id)
            invoice.add_charge(line)
            await repo.save(invoice)
            uow.register(invoice)
            await uow.commit()


class IssueInvoiceHandler:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, cmd: IssueInvoiceCommand) -> None:
        async with self._uow_factory() as uow:
            repo = SqlAlchemyInvoiceRepository(uow.session)
            invoice = await repo.get(cmd.invoice_id)
            invoice.issue(issued_by=cmd.issued_by)
            await repo.save(invoice)
            uow.register(invoice)
            await uow.commit()


class RecordPaymentHandler:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, cmd: RecordPaymentCommand) -> None:
        amount = Money(
            amount=Decimal(cmd.amount),
            currency=Currency(cmd.currency),
        )
        async with self._uow_factory() as uow:
            repo = SqlAlchemyInvoiceRepository(uow.session)
            invoice = await repo.get(cmd.invoice_id)
            invoice.record_payment(
                amount=amount,
                method=PaymentMethod(cmd.method),
                reference=cmd.reference,
                recorded_by=cmd.recorded_by,
            )
            await repo.save(invoice)
            uow.register(invoice)
            await uow.commit()


class VoidInvoiceHandler:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, cmd: VoidInvoiceCommand) -> None:
        async with self._uow_factory() as uow:
            repo = SqlAlchemyInvoiceRepository(uow.session)
            invoice = await repo.get(cmd.invoice_id)
            invoice.void(reason=cmd.reason, voided_by=cmd.voided_by)
            await repo.save(invoice)
            uow.register(invoice)
            await uow.commit()
