"""Keycloak JWT validation.

The Keycloak realm publishes its JWKS at
``/realms/<realm>/protocol/openid-connect/certs``. We cache the keys with a
TTL and validate every incoming bearer token against:

* Signature (RS256 by default).
* ``iss`` matches the configured issuer.
* ``aud`` contains the configured audience.
* ``exp`` / ``nbf`` are respected (jose handles this automatically).

Roles are extracted from both ``realm_access.roles`` (realm roles) and
``resource_access.<client>.roles`` (client roles). FastAPI route handlers
use ``require_role(...)`` to gate access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
from cachetools import TTLCache
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError

from shared_kernel.domain.exceptions import Forbidden
from shared_kernel.infrastructure.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated caller — a plain value object.

    Services should treat this as opaque: only look at ``sub``, ``roles``,
    and maybe ``email``. Do **not** let Keycloak-specific claim names leak
    into domain code; that is the entire point of this wrapper.
    """

    subject: str
    username: str
    email: str | None
    roles: frozenset[str] = field(default_factory=frozenset)

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_any_role(self, *roles: str) -> bool:
        return bool(self.roles.intersection(roles))


class KeycloakTokenError(Forbidden):
    """Raised when a token is missing, expired, malformed, or fails validation."""

    default_code = "invalid_token"


class KeycloakJwtValidator:
    """Validates JWTs issued by a Keycloak realm against its JWKS."""

    def __init__(
        self,
        *,
        issuer: str,
        jwks_url: str,
        audience: str,
        client_id: str,
        additional_issuers: list[str] | None = None,
        cache_ttl_seconds: int = 300,
        http_timeout_seconds: float = 5.0,
    ) -> None:
        self._issuer = issuer
        # python-jose accepts a str *or* list[str] for the issuer check.
        self._allowed_issuers: str | list[str] = (
            [issuer] + additional_issuers if additional_issuers else issuer
        )
        self._jwks_url = jwks_url
        self._audience = audience
        self._client_id = client_id
        self._http_timeout = http_timeout_seconds
        self._jwks_cache: TTLCache[str, dict[str, Any]] = TTLCache(
            maxsize=1, ttl=cache_ttl_seconds
        )

    async def validate(self, token: str) -> Principal:
        """Verify the token and return the caller's :class:`Principal`."""
        if not token:
            raise KeycloakTokenError("bearer token missing")
        jwks = await self._get_jwks()
        try:
            header = jwt.get_unverified_header(token)
        except JWTError as exc:
            raise KeycloakTokenError(f"malformed token: {exc}") from exc
        kid = header.get("kid")
        key = _find_key(jwks, kid)
        if key is None:
            # The signing key rotated — force a refresh and try once more.
            self._jwks_cache.clear()
            jwks = await self._get_jwks()
            key = _find_key(jwks, kid)
            if key is None:
                raise KeycloakTokenError("no matching signing key")

        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=[header.get("alg", "RS256")],
                audience=self._audience,
                issuer=self._allowed_issuers,
                options={"verify_at_hash": False},
            )
        except ExpiredSignatureError as exc:
            raise KeycloakTokenError("token expired") from exc
        except JWTError as exc:
            raise KeycloakTokenError(f"token rejected: {exc}") from exc

        return _principal_from_claims(claims, self._client_id)

    async def _get_jwks(self) -> dict[str, Any]:
        cached = self._jwks_cache.get("jwks")
        if cached is not None:
            return cached
        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            resp = await client.get(self._jwks_url)
            resp.raise_for_status()
            jwks = resp.json()
        self._jwks_cache["jwks"] = jwks
        log.debug("keycloak.jwks.refreshed", keys=len(jwks.get("keys", [])))
        return jwks


def _find_key(jwks: dict[str, Any], kid: str | None) -> dict[str, Any] | None:
    for k in jwks.get("keys", []):
        if k.get("kid") == kid:
            return k
    return None


def _principal_from_claims(claims: dict[str, Any], client_id: str) -> Principal:
    realm_roles = set(claims.get("realm_access", {}).get("roles", []))
    client_roles = set(
        claims.get("resource_access", {}).get(client_id, {}).get("roles", [])
    )
    return Principal(
        subject=str(claims["sub"]),
        username=str(claims.get("preferred_username") or claims["sub"]),
        email=claims.get("email"),
        roles=frozenset(realm_roles | client_roles),
    )
