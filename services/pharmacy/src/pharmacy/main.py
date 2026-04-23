"""Pharmacy service entry-point."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from fastapi import FastAPI

from shared_kernel.fastapi.app_factory import create_app
from shared_kernel.infrastructure.database import create_engine, create_session_factory
from shared_kernel.infrastructure.event_bus import (
    RabbitMQPublisher,
    RabbitMQSubscriber,
    Subscription,
)
from shared_kernel.infrastructure.logging import get_logger
from shared_kernel.infrastructure.outbox import OutboxRelay, RelayConfig
from shared_kernel.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork

from pharmacy.acl.drug_interaction_port import NullDrugInteractionChecker
from pharmacy.acl.rxnav_client import RxNavDrugInteractionChecker
from pharmacy.api.routes import router, stock_router
from pharmacy.application.handlers import DispensePrescriptionHandler
from pharmacy.infrastructure.clinical_event_handler import make_clinical_event_handler
from pharmacy.infrastructure.orm import Base  # noqa: F401
from pharmacy.infrastructure.settings import PharmacySettings

log = get_logger(__name__)
settings = PharmacySettings()


async def _startup_hook(app: FastAPI) -> Callable[[], Awaitable[None]]:
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    from shared_kernel.infrastructure.database import Base as SharedBase
    from shared_kernel.infrastructure.inbox import InboxRecord  # noqa: F401
    from shared_kernel.infrastructure.outbox import OutboxRecord  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(SharedBase.metadata.create_all)
        await conn.run_sync(Base.metadata.create_all)

    app.state.session_factory = session_factory
    app.state.uow_factory = lambda: SqlAlchemyUnitOfWork(session_factory)

    # Wire the ACL: real RxNav or null based on config
    interaction_checker = (
        NullDrugInteractionChecker()
        if settings.rxnav_offline_mode
        else RxNavDrugInteractionChecker(base_url=settings.rxnav_base_url)
    )
    app.state.dispense_handler = DispensePrescriptionHandler(
        uow_factory=app.state.uow_factory,
        interaction_checker=interaction_checker,
    )

    publisher = RabbitMQPublisher(url=settings.rabbitmq_url)
    await publisher.connect()

    relay = OutboxRelay(
        session_factory=session_factory,
        publisher=publisher,
        exchange=settings.smartclinic_exchange,
        config=RelayConfig(service_name=settings.service_name),
    )
    relay_task = asyncio.create_task(relay.run_forever())

    # Subscribe to Clinical prescription events and Patient consent events
    clinical_handler = make_clinical_event_handler(session_factory)
    subscriber = RabbitMQSubscriber(url=settings.rabbitmq_url)
    subscriber.set_service_name(settings.service_name)
    subscriber.subscribe(Subscription(
        queue_name=settings.clinical_events_queue,
        handler=clinical_handler,
    ))
    subscriber.subscribe(Subscription(
        queue_name=settings.patient_events_queue,
        handler=clinical_handler,
    ))
    await subscriber.start()

    log.info("pharmacy.startup_complete")

    async def _shutdown() -> None:
        relay.stop()
        relay_task.cancel()
        await subscriber.stop()
        try:
            await relay_task
        except asyncio.CancelledError:
            pass
        await publisher.close()
        await engine.dispose()

    return _shutdown


app: FastAPI = create_app(
    settings=settings,
    routers=(router, stock_router),
    lifespan_hooks=(_startup_hook,),
    title="Pharmacy",
    version="0.1.0",
)
