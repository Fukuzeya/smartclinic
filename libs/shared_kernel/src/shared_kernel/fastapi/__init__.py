"""FastAPI integration helpers."""

from shared_kernel.fastapi.app_factory import AppLifespanHook, create_app
from shared_kernel.fastapi.dependencies import (
    get_current_principal,
    require_any_role,
    require_role,
)
from shared_kernel.fastapi.exception_handlers import register_exception_handlers
from shared_kernel.fastapi.health import HealthCheck, HealthStatus, liveness, readiness
from shared_kernel.fastapi.middleware import (
    CorrelationIdMiddleware,
    PrometheusMiddleware,
)

__all__ = [
    "AppLifespanHook",
    "CorrelationIdMiddleware",
    "HealthCheck",
    "HealthStatus",
    "PrometheusMiddleware",
    "create_app",
    "get_current_principal",
    "liveness",
    "readiness",
    "register_exception_handlers",
    "require_any_role",
    "require_role",
]
