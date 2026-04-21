"""Saga Orchestrator service entry-point.

This service has no write endpoints — it is purely event-driven.
It subscribes to a single RabbitMQ queue (``saga.all.events``) that is
bound in ``ops/rabbitmq/definitions.json`` to receive events from:
  * scheduling.*
  * clinical.*
  * laboratory.*
  * billing.*
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

from saga_orchestrator.api.routes import router
from saga_orchestrator.infrastructure.event_handler import make_event_handler
from saga_orchestrator.infrastructure.orm import Base  # noqa: F401
from saga_orchestrator.infrastructure.settings import SagaSettings

log = get_logger(__name__)
settings = SagaSettings()


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

    # The saga orchestrator also publishes its own domain events so downstream
    # services (e.g. notifications) can react to saga completions.
    publisher = RabbitMQPublisher(url=settings.rabbitmq_url)
    await publisher.connect()

    relay = OutboxRelay(
        session_factory=session_factory,
        publisher=publisher,
        exchange=settings.smartclinic_exchange,
        config=RelayConfig(service_name=settings.service_name),
    )
    relay_task = asyncio.create_task(relay.run_forever())

    handler = make_event_handler(session_factory)
    subscriber = RabbitMQSubscriber(url=settings.rabbitmq_url)
    subscriber.set_service_name(settings.service_name)
    subscriber.subscribe(Subscription(
        queue_name=settings.all_events_queue,
        handler=handler,
    ))
    await subscriber.start()

    log.info("saga_orchestrator.startup_complete")

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
    routers=(router,),
    lifespan_hooks=(_startup_hook,),
    title="Saga Orchestrator",
    version="0.1.0",
)
