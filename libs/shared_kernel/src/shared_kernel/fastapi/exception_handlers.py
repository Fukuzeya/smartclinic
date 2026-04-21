"""RFC 7807 problem-details mapping for the domain exception hierarchy.

Every ``DomainError`` subtype maps to a predictable HTTP status and a
consistent ``application/problem+json`` body. This is the *only* place
where domain→HTTP translation happens; handlers never ``raise HTTPException``
directly because that would couple the domain to FastAPI.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from shared_kernel.domain.exceptions import (
    ConcurrencyConflict,
    DomainError,
    Forbidden,
    InvariantViolation,
    NotFound,
    PreconditionFailed,
)
from shared_kernel.domain.specification import SpecificationViolation
from shared_kernel.infrastructure.correlation import get_correlation_id
from shared_kernel.infrastructure.logging import get_logger

log = get_logger(__name__)

_STATUS_BY_EXCEPTION: dict[type[DomainError], int] = {
    NotFound: status.HTTP_404_NOT_FOUND,
    Forbidden: status.HTTP_403_FORBIDDEN,
    InvariantViolation: status.HTTP_422_UNPROCESSABLE_ENTITY,
    SpecificationViolation: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ConcurrencyConflict: status.HTTP_409_CONFLICT,
    PreconditionFailed: status.HTTP_412_PRECONDITION_FAILED,
}


def _status_for(exc: DomainError) -> int:
    for cls, code in _STATUS_BY_EXCEPTION.items():
        if isinstance(exc, cls):
            return code
    return status.HTTP_400_BAD_REQUEST


def register_exception_handlers(app: FastAPI, *, include_debug_trace: bool = False) -> None:
    """Register handlers for the whole :class:`DomainError` hierarchy."""

    @app.exception_handler(DomainError)
    async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        http_status = _status_for(exc)
        body: dict[str, Any] = {
            "type": f"urn:smartclinic:error:{exc.code}",
            "title": type(exc).__name__,
            "status": http_status,
            "detail": exc.message,
            "code": exc.code,
            "instance": str(request.url),
            "correlation_id": get_correlation_id(),
        }
        if isinstance(exc, SpecificationViolation):
            body["reasons"] = list(exc.reasons)
        if include_debug_trace:
            import traceback

            body["_trace"] = traceback.format_exc()
        log.warning(
            "http.domain_error",
            code=exc.code,
            status=http_status,
            error_type=type(exc).__name__,
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=http_status,
            content=body,
            media_type="application/problem+json",
        )

    @app.exception_handler(Exception)
    async def _handle_unknown(request: Request, exc: Exception) -> JSONResponse:
        log.exception(
            "http.unhandled_error",
            error_type=type(exc).__name__,
            path=str(request.url.path),
        )
        body: dict[str, Any] = {
            "type": "urn:smartclinic:error:internal",
            "title": "InternalServerError",
            "status": 500,
            "detail": "An unexpected error occurred.",
            "correlation_id": get_correlation_id(),
        }
        if include_debug_trace:
            import traceback

            body["_trace"] = traceback.format_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=body,
            media_type="application/problem+json",
        )
