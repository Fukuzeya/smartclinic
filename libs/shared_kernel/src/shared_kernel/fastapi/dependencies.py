"""FastAPI dependencies for authentication and RBAC.

Usage in a service route::

    @router.post("/encounters")
    async def create_encounter(
        cmd: CreateEncounter,
        principal: Principal = Depends(require_role("doctor")),
        mediator: Mediator = Depends(get_mediator),
    ) -> EncounterResponse:
        return await mediator.send(cmd)

The validator instance is wired into the app via ``app.state.jwt_validator``
inside the app factory — this keeps the dependency callables simple and
avoids a global singleton.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, cast

from fastapi import Depends, Header, HTTPException, Request, status

from shared_kernel.infrastructure.security import (
    KeycloakJwtValidator,
    KeycloakTokenError,
    Principal,
)


def _validator_from_request(request: Request) -> KeycloakJwtValidator:
    validator = cast(Any, request.app.state).jwt_validator
    if validator is None:
        # Dev mode without auth — construct a synthetic anonymous principal.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication not configured",
        )
    return cast(KeycloakJwtValidator, validator)


async def get_current_principal(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    """Decode and validate the ``Authorization: Bearer ...`` header."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or malformed bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        validator = _validator_from_request(request)
        return await validator.validate(token)
    except KeycloakTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_role(role: str) -> Callable[[Principal], Principal]:
    """Return a dependency that allows only callers holding ``role``."""

    def dep(principal: Annotated[Principal, Depends(get_current_principal)]) -> Principal:
        if not principal.has_role(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role '{role}' required",
            )
        return principal

    return dep


def require_any_role(*roles: str) -> Callable[[Principal], Principal]:
    """Return a dependency that allows any caller holding at least one role."""

    def dep(principal: Annotated[Principal, Depends(get_current_principal)]) -> Principal:
        if not principal.has_any_role(*roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"one of {sorted(roles)} required",
            )
        return principal

    return dep
