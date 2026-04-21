"""Patient Identity service entry-point.

This module:
1. Creates the FastAPI app via the shared ``create_app`` factory.
2. Wires the database engine, session factory, and UoW into
   ``app.state`` so route handlers can pull them as dependencies.
3. Starts / stops the ``OutboxRelay`` background task via a lifespan
   hook.

Run in development::

    uv run uvicorn patient_identity.main:app --reload --host 0.0.0.0 --port 8001

Or via Docker Compose (preferred for the full stack).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI

from shared_kernel.fastapi.app_factory import create_app
from shared_kernel.infrastructure.database import create_engine, create_session_factory
from shared_kernel.infrastructure.event_bus import RabbitMQPublisher
from shared_kernel.infrastructure.logging import get_logger
from shared_kernel.infrastructure.outbox import OutboxRelay, RelayConfig
from shared_kernel.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork

from patient_identity.infrastructure.settings import PatientIdentitySettings

log = get_logger(__name__)
settings = PatientIdentitySettings()


async def _startup_hook(app: FastAPI) -> Callable[[], Awaitable[None]]:
    """Called by the shared app factory at startup.

    Sets up the database, outbox relay, and event bus. Returns a
    shutdown callable that the factory will call in reverse order.
    """
    # --- Database --------------------------------------------------------
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    # Ensure tables exist (dev convenience — production uses Alembic).
    from shared_kernel.infrastructure.database import Base
    from patient_identity.infrastructure.orm import (  # noqa: F401
        PatientConsentRow,
        PatientRow,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # UoW factory: each request or command gets a fresh UoW.
    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    app.state.session_factory = session_factory
    app.state.uow_factory = uow_factory

    # --- Outbox relay ----------------------------------------------------
    event_bus = RabbitMQPublisher(url=settings.rabbitmq_url)
    await event_bus.connect()

    relay = OutboxRelay(
        session_factory=session_factory,
        publisher=event_bus,
        exchange=settings.smartclinic_exchange,
        config=RelayConfig(
            service_name=settings.service_name,
            poll_interval_seconds=settings.outbox_poll_interval_seconds,
        ),
    )
    relay_task = asyncio.create_task(relay.run_forever())
    log.info("patient_identity.startup_complete")

    async def _shutdown() -> None:
        relay.stop()
        relay_task.cancel()
        try:
            await relay_task
        except asyncio.CancelledError:
            pass
        await event_bus.close()
        await engine.dispose()
        log.info("patient_identity.shutdown_complete")

    return _shutdown


from patient_identity.api.routes import router  # noqa: E402 — after settings init

app: FastAPI = create_app(
    settings=settings,
    routers=(router,),
    lifespan_hooks=(_startup_hook,),
    title="Patient Identity",
    version="0.1.0",
)
