"""Clinical service entry-point.

Wires up:
* The hash-chained event store (``clinical_events`` table).
* The CQRS read model (``encounter_summaries`` table, owned by this service).
* The outbox relay for publishing ``clinical.*`` events to RabbitMQ.
* A subscriber for the service's own events to maintain the read-side
  projection (self-subscription pattern — the Clinical service reads its own
  outgoing events to build the summary table without a shared DB join).
"""

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

from shared_kernel.ai.copilot_port import build_copilot

from clinical.api.routes import router
from clinical.infrastructure.orm import AISuggestionRecord, Base, EventStoreRecord, EncounterSummaryRow  # noqa: F401
from clinical.infrastructure.projections import make_projection_handler
from clinical.infrastructure.settings import ClinicalSettings

log = get_logger(__name__)
settings = ClinicalSettings()


async def _startup_hook(app: FastAPI) -> Callable[[], Awaitable[None]]:
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    # Create clinical tables + shared-kernel tables (outbox, inbox)
    from shared_kernel.infrastructure.database import Base as SharedBase
    from shared_kernel.infrastructure.inbox import InboxRecord  # noqa: F401
    from shared_kernel.infrastructure.outbox import OutboxRecord  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(SharedBase.metadata.create_all)
        await conn.run_sync(Base.metadata.create_all)

    app.state.session_factory = session_factory
    app.state.uow_factory = lambda: SqlAlchemyUnitOfWork(session_factory)
    app.state.copilot = build_copilot()

    publisher = RabbitMQPublisher(url=settings.rabbitmq_url)
    await publisher.connect()

    relay = OutboxRelay(
        session_factory=session_factory,
        publisher=publisher,
        exchange=settings.smartclinic_exchange,
        config=RelayConfig(service_name=settings.service_name),
    )
    relay_task = asyncio.create_task(relay.run_forever())

    # Subscribe to clinical.* events published by this service's outbox relay
    # to maintain the encounter_summaries read model.
    projection_handler = make_projection_handler(session_factory)
    subscriber = RabbitMQSubscriber(url=settings.rabbitmq_url)
    subscriber.set_service_name(settings.service_name)
    subscriber.subscribe(
        Subscription(
            queue_name=settings.clinical_events_queue,
            handler=_wrap_projection_handler(projection_handler),
        )
    )
    await subscriber.start()

    log.info("clinical.startup_complete")

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


def _wrap_projection_handler(projection_handler):
    """Adapt the projection handler to the subscriber callback signature."""
    from shared_kernel.domain.domain_event import DomainEvent

    async def _handler(event: DomainEvent, message) -> None:
        # Reconstruct the full message dict the projection expects
        msg = {
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "aggregate_id": event.aggregate_id,
            "aggregate_type": event.aggregate_type,
            "payload": event.payload,
        }
        await projection_handler(msg)

    return _handler


app: FastAPI = create_app(
    settings=settings,
    routers=(router,),
    lifespan_hooks=(_startup_hook,),
    title="Clinical",
    version="0.1.0",
)
