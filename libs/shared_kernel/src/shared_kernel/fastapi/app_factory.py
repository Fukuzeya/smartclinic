"""The FastAPI application factory.

Every bounded context's ``main.py`` is a 10-line file that calls
:func:`create_app` with its settings, router list, and optional lifespan
hooks. The factory wires in:

* Structured logging (``structlog`` JSON)
* OpenTelemetry tracing (OTLP exporter, FastAPI auto-instrumentation)
* Prometheus ``/metrics`` endpoint + middleware
* Correlation-ID middleware
* RFC 7807 exception handlers for the domain exception hierarchy
* Liveness / readiness health probes
* CORS
* Keycloak JWT validator wired into ``app.state``

Lifespan hooks let each service start and stop the outbox relay and event
subscriber without re-implementing startup/shutdown management.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from shared_kernel.fastapi.exception_handlers import register_exception_handlers
from shared_kernel.fastapi.health import make_router as make_health_router
from shared_kernel.fastapi.middleware import (
    CorrelationIdMiddleware,
    PrometheusMiddleware,
)
from shared_kernel.infrastructure.logging import configure_logging, get_logger
from shared_kernel.infrastructure.metrics import render_metrics
from shared_kernel.infrastructure.security import KeycloakJwtValidator
from shared_kernel.infrastructure.settings import SharedSettings
from shared_kernel.infrastructure.tracing import configure_tracing

AppLifespanHook = Callable[[FastAPI], Awaitable[Callable[[], Awaitable[None]] | None]]
"""An async callable invoked at startup. It may return another callable to be awaited at shutdown."""


def create_app(
    *,
    settings: SharedSettings,
    routers: Iterable[APIRouter] = (),
    lifespan_hooks: Iterable[AppLifespanHook] = (),
    title: str | None = None,
    version: str = "0.1.0",
) -> FastAPI:
    """Build a configured FastAPI app for a SmartClinic bounded context."""
    configure_logging(
        service_name=settings.service_name,
        level=settings.log_level,
        fmt=settings.log_format,
    )
    configure_tracing(settings)
    log = get_logger(f"app.{settings.service_name}")

    jwt_validator = _build_jwt_validator(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.jwt_validator = jwt_validator
        app.state.settings = settings
        shutdowns: list[Callable[[], Awaitable[None]]] = []
        for hook in lifespan_hooks:
            result = await hook(app)
            if result is not None:
                shutdowns.append(result)
        log.info("app.started", service=settings.service_name)
        try:
            yield
        finally:
            for shutdown in reversed(shutdowns):
                try:
                    await shutdown()
                except Exception:  # noqa: BLE001
                    log.exception("app.shutdown_hook_failed")
            log.info("app.stopped", service=settings.service_name)

    app = FastAPI(
        title=title or settings.service_name,
        version=version,
        lifespan=lifespan,
        default_response_class=JSONResponse,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Middleware — outermost added last so it runs first.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-Id"],
    )
    app.add_middleware(PrometheusMiddleware, service_name=settings.service_name)
    app.add_middleware(CorrelationIdMiddleware)

    register_exception_handlers(
        app,
        include_debug_trace=settings.debug_exception_trace or not settings.is_production,
    )

    # Routers: health + metrics + service-specific.
    app.include_router(make_health_router(service_name=settings.service_name))

    @app.get("/metrics", include_in_schema=False)
    def metrics_endpoint() -> Response:
        body, ctype = render_metrics()
        return Response(content=body, media_type=ctype)

    for router in routers:
        app.include_router(router)

    # FastAPI auto-instrumentation for OTel (must come after all middlewares).
    try:
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="health/live,health/ready,metrics",
        )
    except Exception:  # noqa: BLE001
        log.warning("app.fastapi_otel_instrumentation_failed", exc_info=True)

    return app


def _build_jwt_validator(settings: SharedSettings) -> KeycloakJwtValidator | None:
    if settings.oidc_issuer is None or settings.oidc_jwks_url is None:
        return None
    return KeycloakJwtValidator(
        issuer=str(settings.oidc_issuer),
        jwks_url=str(settings.oidc_jwks_url),
        audience=settings.oidc_audience,
        client_id=settings.oidc_client_id,
        cache_ttl_seconds=settings.oidc_jwks_cache_ttl_seconds,
    )
