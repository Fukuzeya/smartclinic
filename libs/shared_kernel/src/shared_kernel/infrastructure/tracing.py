"""OpenTelemetry bootstrap.

Auto-instruments FastAPI, SQLAlchemy, aio-pika, and httpx so spans are
produced without manual instrumentation in the handlers. The OTLP exporter
ships spans to the ``otel-collector`` service which fans out to Jaeger.

Every span carries the resource attributes ``service.name``,
``service.namespace`` (``smartclinic``), and ``deployment.environment``.
"""

from __future__ import annotations

from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as OTLPGrpcExporter,
)
from opentelemetry.instrumentation.aio_pika import AioPikaInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from shared_kernel.infrastructure.settings import SharedSettings


def configure_tracing(settings: SharedSettings) -> None:
    """Configure an OTLP tracer provider. Idempotent; safe on hot-reload."""
    if settings.otel_exporter_otlp_endpoint is None:
        # Tracing disabled (local dev without collector) — install a no-op
        # provider so downstream code can still call ``trace.get_tracer``.
        trace.set_tracer_provider(TracerProvider())
        return

    resource = Resource.create(
        {
            "service.name": settings.service_name,
            "service.namespace": settings.otel_service_namespace,
            **_parse_resource_attributes(settings.otel_resource_attributes),
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPGrpcExporter(endpoint=settings.otel_exporter_otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # SQLAlchemy and httpx need explicit instrumentation; FastAPI is done by
    # the app factory once the app object exists.
    SQLAlchemyInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    AioPikaInstrumentor().instrument()


def _parse_resource_attributes(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        out[k.strip()] = v.strip()
    return out


async def tracing_middleware(message: Any, next_call: Any) -> Any:
    """Mediator middleware that wraps each message in a span."""
    tracer = trace.get_tracer("shared_kernel.mediator")
    with tracer.start_as_current_span(type(message).__name__):
        return await next_call(message)
