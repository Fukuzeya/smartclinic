"""Scheduling service entry-point."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from fastapi import FastAPI

from shared_kernel.fastapi.app_factory import create_app
from shared_kernel.infrastructure.database import Base, create_engine, create_session_factory
from shared_kernel.infrastructure.event_bus import (
    RabbitMQPublisher,
    RabbitMQSubscriber,
    Subscription,
)
from shared_kernel.infrastructure.logging import get_logger
from shared_kernel.infrastructure.outbox import OutboxRelay, RelayConfig
from shared_kernel.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork

from scheduling.api.routes import router
from scheduling.infrastructure.orm import AppointmentRow, PatientReadModelRow  # noqa: F401
from scheduling.infrastructure.patient_projection import (
    handle_patient_demographics_updated,
    handle_patient_registered,
)
from scheduling.infrastructure.settings import SchedulingSettings

log = get_logger(__name__)
settings = SchedulingSettings()


async def _startup_hook(app: FastAPI) -> Callable[[], Awaitable[None]]:
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    from shared_kernel.infrastructure.database import Base
    from shared_kernel.infrastructure.inbox import InboxRecord  # noqa: F401
    from shared_kernel.infrastructure.outbox import OutboxRecord  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app.state.session_factory = session_factory
    app.state.uow_factory = lambda: SqlAlchemyUnitOfWork(session_factory)

    publisher = RabbitMQPublisher(url=settings.rabbitmq_url)
    await publisher.connect()

    relay = OutboxRelay(
        session_factory=session_factory,
        publisher=publisher,
        exchange=settings.smartclinic_exchange,
        config=RelayConfig(service_name=settings.service_name),
    )
    relay_task = asyncio.create_task(relay.run_forever())

    # Subscribe to Patient Identity events to maintain read-model projection
    subscriber = RabbitMQSubscriber(url=settings.rabbitmq_url)
    subscriber.set_service_name(settings.service_name)
    subscriber.subscribe(
        Subscription(
            queue_name=settings.patient_events_queue,
            handler=_make_patient_event_handler(session_factory),
        )
    )
    await subscriber.start()
    sub_task = asyncio.create_task(
        asyncio.sleep(0)  # placeholder — subscriber runs via internal tasks
    )

    log.info("scheduling.startup_complete")

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


def _make_patient_event_handler(session_factory):
    """Return an event handler that updates the patient read-model."""
    from shared_kernel.domain.domain_event import DomainEvent
    import uuid

    async def handler(event: DomainEvent, message) -> None:
        event_id = event.event_id
        async with session_factory() as session:
            async with session.begin():
                if event.event_type == "patient.registered.v1":
                    await handle_patient_registered(
                        session, event.payload, event_id
                    )
                elif event.event_type == "patient.demographics_updated.v1":
                    await handle_patient_demographics_updated(
                        session, event.payload, event_id
                    )

    return handler


app: FastAPI = create_app(
    settings=settings,
    routers=(router,),
    lifespan_hooks=(_startup_hook,),
    title="Scheduling",
    version="0.1.0",
)
