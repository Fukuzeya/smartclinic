"""Kubernetes-style liveness + readiness probes.

Liveness: is the process up? (trivial — always 200).
Readiness: can this service accept traffic right now?
           → deep-check registered dependencies (DB ping, RabbitMQ channel).

Services add readiness checks at startup, e.g.:

    health.register("postgres", check_db(engine))
    health.register("rabbitmq", check_rabbitmq(subscriber))
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, Response, status


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


HealthCheck = Callable[[], Awaitable[bool]]


@dataclass(slots=True)
class _Registration:
    name: str
    check: HealthCheck
    critical: bool


class HealthRegistry:
    """Holds the service's readiness probes."""

    def __init__(self) -> None:
        self._checks: list[_Registration] = []

    def register(self, name: str, check: HealthCheck, *, critical: bool = True) -> None:
        self._checks.append(_Registration(name=name, check=check, critical=critical))

    async def evaluate(self) -> tuple[HealthStatus, dict[str, Any]]:
        results: dict[str, Any] = {}
        overall = HealthStatus.HEALTHY
        for reg in self._checks:
            try:
                ok = await asyncio.wait_for(reg.check(), timeout=3.0)
            except Exception as exc:  # noqa: BLE001
                ok = False
                results[reg.name] = {"ok": False, "error": str(exc)}
            else:
                results[reg.name] = {"ok": ok}
            if not ok:
                overall = (
                    HealthStatus.UNHEALTHY if reg.critical else HealthStatus.DEGRADED
                )
        return overall, results


_GLOBAL_REGISTRY = HealthRegistry()


def get_registry() -> HealthRegistry:
    """Return the per-process registry. Services should add checks at startup."""
    return _GLOBAL_REGISTRY


def make_router(*, service_name: str) -> APIRouter:
    """Build a FastAPI router with ``/health/live`` and ``/health/ready``."""
    router = APIRouter(tags=["health"])

    @router.get("/health/live", status_code=status.HTTP_200_OK)
    async def liveness_route() -> dict[str, str]:  # type: ignore[return]
        return {"service": service_name, "status": HealthStatus.HEALTHY.value}

    @router.get("/health/ready")
    async def readiness_route(response: Response) -> dict[str, Any]:
        overall, detail = await _GLOBAL_REGISTRY.evaluate()
        response.status_code = (
            status.HTTP_200_OK
            if overall == HealthStatus.HEALTHY
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return {
            "service": service_name,
            "status": overall.value,
            "checks": detail,
        }

    return router


# Convenience factories for common dependency checks.

def liveness() -> bool:
    return True


async def readiness() -> tuple[HealthStatus, dict[str, Any]]:
    return await _GLOBAL_REGISTRY.evaluate()
