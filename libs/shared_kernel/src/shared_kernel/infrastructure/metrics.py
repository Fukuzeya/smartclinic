"""Prometheus metrics helpers.

We expose a small curated set of RED metrics that every service reports
uniformly — ``http_requests_total``, ``http_request_duration_seconds``,
``message_processed_total``, ``outbox_relay_lag_seconds``. Service-specific
business metrics (e.g. ``prescriptions_issued_total``) should be defined in
the service's own infrastructure package using the same convention.

The ``/metrics`` endpoint is mounted by the FastAPI app factory.
"""

from __future__ import annotations

import time
from typing import Any

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# One global registry per process — services add their own collectors to it.
REGISTRY = CollectorRegistry(auto_describe=True)

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests processed, labelled by method and status.",
    labelnames=("service", "method", "path", "status"),
    registry=REGISTRY,
)

HTTP_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    labelnames=("service", "method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)

MESSAGE_TOTAL = Counter(
    "message_processed_total",
    "Commands / queries dispatched through the mediator.",
    labelnames=("service", "message_type", "kind", "status"),
    registry=REGISTRY,
)

MESSAGE_DURATION = Histogram(
    "message_duration_seconds",
    "Mediator message dispatch duration in seconds.",
    labelnames=("service", "message_type"),
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=REGISTRY,
)

OUTBOX_LAG = Gauge(
    "outbox_relay_lag_seconds",
    "Age of the oldest unpublished outbox record, in seconds.",
    labelnames=("service",),
    registry=REGISTRY,
)

OUTBOX_PENDING = Gauge(
    "outbox_pending_records",
    "Number of outbox records awaiting publication.",
    labelnames=("service",),
    registry=REGISTRY,
)

EVENT_PUBLISHED = Counter(
    "events_published_total",
    "Domain events successfully published to the bus.",
    labelnames=("service", "event_type"),
    registry=REGISTRY,
)

EVENT_CONSUMED = Counter(
    "events_consumed_total",
    "Domain events consumed from the bus.",
    labelnames=("service", "event_type", "status"),
    registry=REGISTRY,
)


def render_metrics() -> tuple[bytes, str]:
    """Return (body, content-type) for the Prometheus ``/metrics`` endpoint."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def metrics_middleware_for(service_name: str) -> Any:
    """Return a mediator middleware that records message metrics."""

    async def middleware(message: Any, next_call: Any) -> Any:
        message_type = type(message).__name__
        kind = "query" if "Query" in message_type else "command"
        start = time.perf_counter()
        try:
            result = await next_call(message)
        except Exception:
            MESSAGE_TOTAL.labels(service_name, message_type, kind, "error").inc()
            raise
        else:
            MESSAGE_TOTAL.labels(service_name, message_type, kind, "ok").inc()
            return result
        finally:
            MESSAGE_DURATION.labels(service_name, message_type).observe(
                time.perf_counter() - start
            )

    return middleware
