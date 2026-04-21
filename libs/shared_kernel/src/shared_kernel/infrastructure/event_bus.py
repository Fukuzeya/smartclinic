"""RabbitMQ event bus built on ``aio-pika``.

Two roles:

* **Publisher** — used by the :class:`OutboxRelay` (never by handlers
  directly). Uses publisher confirms so a successful ``publish`` means the
  broker has accepted the message to the durable exchange.
* **Subscriber** — a long-running task per service that consumes its
  queue(s) and dispatches messages to registered handlers.

The bus knows nothing about the :class:`DomainEvent` subclass graph — it
carries raw JSON payloads and routes by the ``event-type`` header.
Deserialisation into a typed event (if a subclass is registered via
:meth:`DomainEvent.for_type`) happens in the subscriber.

Topology (declared by ``ops/rabbitmq/definitions.json``, not here):

* Topic exchange ``smartclinic.events`` (durable)
* Dead-letter exchange ``smartclinic.events.dlx`` (fanout)
* Per-service durable queues bound to context-specific routing keys
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import aio_pika
from aio_pika.abc import (
    AbstractChannel,
    AbstractIncomingMessage,
    AbstractRobustConnection,
    ExchangeType,
)

from shared_kernel.domain.domain_event import DomainEvent
from shared_kernel.infrastructure.correlation import (
    correlation_scope,
    set_causation_id,
)
from shared_kernel.infrastructure.logging import get_logger
from shared_kernel.infrastructure.metrics import EVENT_CONSUMED
from shared_kernel.infrastructure.outbox import EventPublisher

log = get_logger(__name__)


# ---------------------------------------------------------------- publisher

class RabbitMQPublisher(EventPublisher):
    """Concrete :class:`EventPublisher` for use by the outbox relay.

    Maintains a single robust connection and a confirm-select channel.
    ``publish`` awaits the broker confirm, so a successful return means the
    event is durably persisted in RabbitMQ. The relay only marks the
    outbox row published on successful return.
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._conn: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        if self._conn is not None and not self._conn.is_closed:
            return
        async with self._lock:
            if self._conn is None or self._conn.is_closed:
                self._conn = await aio_pika.connect_robust(self._url)
                self._channel = await self._conn.channel(publisher_confirms=True)

    async def close(self) -> None:
        if self._conn is not None and not self._conn.is_closed:
            await self._conn.close()
        self._conn = None
        self._channel = None

    async def publish(
        self,
        *,
        exchange: str,
        routing_key: str,
        body: bytes,
        headers: dict[str, Any],
    ) -> None:
        await self.connect()
        assert self._channel is not None  # noqa: S101 — post-connect invariant
        ex = await self._channel.declare_exchange(
            exchange,
            ExchangeType.TOPIC,
            durable=True,
            passive=True,  # must be pre-declared via rabbitmq definitions.json
        )
        message = aio_pika.Message(
            body=body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            headers={k: v for k, v in headers.items() if v is not None},
            message_id=str(headers.get("event-id", "")) or None,
            type=str(headers.get("event-type", "")) or None,
        )
        await ex.publish(message, routing_key=routing_key)


# ---------------------------------------------------------------- subscriber

EventHandler = Callable[[DomainEvent, AbstractIncomingMessage], Awaitable[None]]


@dataclass(slots=True)
class Subscription:
    """Binds a handler to a queue name.

    The queue must already exist (declared by ``definitions.json``); we
    declare it passively here so the subscriber fails fast if topology is
    missing.
    """

    queue_name: str
    handler: EventHandler
    prefetch: int = 16


class RabbitMQSubscriber:
    """Long-running consumer process for a single service.

    Each subscription consumes from its queue with prefetch-based flow
    control. On success, the message is acked; on handler exception, the
    message is nacked *without* requeue — RabbitMQ will route it to the DLX
    and an operator can decide whether to replay after fixing the bug.
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._conn: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None
        self._subscriptions: list[Subscription] = []
        self._tasks: list[asyncio.Task[None]] = []
        self._stopping = asyncio.Event()
        self._service_name = "unknown"

    def set_service_name(self, name: str) -> None:
        self._service_name = name

    def subscribe(self, subscription: Subscription) -> None:
        self._subscriptions.append(subscription)

    async def start(self) -> None:
        self._conn = await aio_pika.connect_robust(self._url)
        self._channel = await self._conn.channel()
        for sub in self._subscriptions:
            await self._channel.set_qos(prefetch_count=sub.prefetch)
            queue = await self._channel.declare_queue(sub.queue_name, passive=True)
            task = asyncio.create_task(
                self._consume_loop(queue, sub.handler),
                name=f"subscriber:{sub.queue_name}",
            )
            self._tasks.append(task)

    async def stop(self) -> None:
        self._stopping.set()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if self._conn is not None and not self._conn.is_closed:
            await self._conn.close()

    async def _consume_loop(
        self,
        queue: aio_pika.abc.AbstractQueue,
        handler: EventHandler,
    ) -> None:
        async with queue.iterator() as iterator:
            async for message in iterator:
                if self._stopping.is_set():
                    return
                await self._process(message, handler)

    async def _process(
        self,
        message: AbstractIncomingMessage,
        handler: EventHandler,
    ) -> None:
        event_type = str(message.headers.get("event-type", "") or "")
        correlation_id = str(message.headers.get("correlation_id", "") or "") or None
        causation_id = str(message.headers.get("causation_id", "") or "") or None
        try:
            payload = json.loads(message.body)
        except json.JSONDecodeError:
            EVENT_CONSUMED.labels(self._service_name, event_type, "malformed").inc()
            log.error("event_bus.malformed_json", event_type=event_type)
            await message.nack(requeue=False)
            return

        event_cls = DomainEvent.for_type(event_type) or DomainEvent
        try:
            event = event_cls.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            EVENT_CONSUMED.labels(self._service_name, event_type, "invalid").inc()
            log.error(
                "event_bus.invalid_event",
                event_type=event_type,
                error=str(exc),
            )
            await message.nack(requeue=False)
            return

        with correlation_scope(correlation_id):
            set_causation_id(causation_id)
            try:
                await handler(event, message)
            except Exception as exc:  # noqa: BLE001
                EVENT_CONSUMED.labels(self._service_name, event_type, "error").inc()
                log.exception(
                    "event_bus.handler_failed",
                    event_type=event_type,
                    error=str(exc),
                )
                await message.nack(requeue=False)
                return

        EVENT_CONSUMED.labels(self._service_name, event_type, "ok").inc()
        await message.ack()
