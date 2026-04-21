"""HTTP middlewares: correlation ID propagation and Prometheus metrics."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from shared_kernel.infrastructure.correlation import (
    new_correlation_id,
    set_correlation_id,
)
from shared_kernel.infrastructure.metrics import HTTP_DURATION, HTTP_REQUESTS

_CORRELATION_HEADER = "X-Correlation-Id"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Read/emit ``X-Correlation-Id`` and bind it to the contextvar.

    If the client supplies the header we echo it back; otherwise we mint a
    fresh v4 UUID. Either way, every log line and outgoing event emitted
    during the request carries the same id.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        cid = request.headers.get(_CORRELATION_HEADER) or new_correlation_id()
        set_correlation_id(cid)
        response = await call_next(request)
        response.headers[_CORRELATION_HEADER] = cid
        return response


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Record RED metrics (requests, errors, duration) per HTTP request."""

    def __init__(self, app: Callable[..., Awaitable[object]], *, service_name: str) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._service = service_name

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Use the route template when available to keep cardinality bounded.
        path_template = getattr(
            request.scope.get("route"), "path", request.url.path
        )
        method = request.method
        start = time.perf_counter()
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            HTTP_REQUESTS.labels(self._service, method, path_template, "500").inc()
            HTTP_DURATION.labels(self._service, method, path_template).observe(
                time.perf_counter() - start
            )
            raise
        HTTP_REQUESTS.labels(self._service, method, path_template, str(status)).inc()
        HTTP_DURATION.labels(self._service, method, path_template).observe(
            time.perf_counter() - start
        )
        return response
