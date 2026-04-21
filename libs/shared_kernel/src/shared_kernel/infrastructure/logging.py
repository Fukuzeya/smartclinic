"""Structured JSON logging with ``structlog``.

Every log record automatically carries:

* ``service.name`` — the bounded context that produced the record
* ``correlation_id`` — from the contextvar (see ``correlation.py``)
* ``trace_id``, ``span_id`` — from the active OTel span, if any
* ``timestamp`` — ISO-8601 UTC

Logs are emitted to stdout as JSON in production so the OTel Collector /
Loki agent can scrape them, and as colourful console output in local dev.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from opentelemetry import trace

from shared_kernel.infrastructure.correlation import get_correlation_id


def _inject_correlation(
    _: structlog.typing.WrappedLogger,
    __: str,
    event_dict: structlog.typing.EventDict,
) -> structlog.typing.EventDict:
    cid = get_correlation_id()
    if cid is not None:
        event_dict.setdefault("correlation_id", cid)
    span = trace.get_current_span()
    ctx = span.get_span_context() if span else None
    if ctx is not None and ctx.is_valid:
        event_dict.setdefault("trace_id", format(ctx.trace_id, "032x"))
        event_dict.setdefault("span_id", format(ctx.span_id, "016x"))
    return event_dict


def configure_logging(
    *,
    service_name: str,
    level: str = "INFO",
    fmt: str = "json",
) -> None:
    """Configure stdlib + structlog. Idempotent.

    Call this exactly once per process, during startup. The FastAPI app
    factory does this automatically.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _inject_correlation,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if fmt == "json":
        renderer: structlog.typing.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.WriteLoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )

    # Re-route stdlib logging through structlog so uvicorn / sqlalchemy emit
    # JSON too.
    root = logging.getLogger()
    root.setLevel(log_level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    std_handler = logging.StreamHandler(sys.stdout)
    std_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=renderer,
            foreign_pre_chain=shared_processors,
        )
    )
    root.addHandler(std_handler)

    # Quiet known-chatty libraries unless explicitly DEBUG.
    for noisy in ("uvicorn.access", "aio_pika", "aiormq"):
        logging.getLogger(noisy).setLevel(max(log_level, logging.WARNING))

    structlog.contextvars.bind_contextvars(service_name=service_name)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to ``name`` (module path by default)."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]


async def logging_middleware(
    message: Any,
    next_call: Any,
) -> Any:
    """Mediator middleware that wraps each command/query with log entries."""
    log = get_logger("mediator")
    log.info("message.start", message_type=type(message).__name__)
    try:
        result = await next_call(message)
    except Exception as exc:
        log.error(
            "message.failed",
            message_type=type(message).__name__,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise
    log.info("message.success", message_type=type(message).__name__)
    return result
