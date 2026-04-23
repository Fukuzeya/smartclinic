"""Base settings shared by every service.

Each bounded context extends :class:`SharedSettings` with its own required
fields (e.g. Clinical adds ``CLINICAL_READ_DB_URL``). The base covers every
cross-cutting knob: logging, tracing, messaging, OIDC.

Values are resolved from environment variables and a ``.env`` file. Secrets
must never be defaulted; they are required in production and the app will
refuse to start without them.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    CI = "ci"
    STAGING = "staging"
    PRODUCTION = "production"


class SharedSettings(BaseSettings):
    """Cross-cutting configuration for every SmartClinic service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",  # services add their own fields
        case_sensitive=False,
    )

    # --- runtime ---------------------------------------------------------
    environment: Environment = Environment.LOCAL
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"
    service_name: str = "smartclinic-service"

    # --- messaging -------------------------------------------------------
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/")
    smartclinic_exchange: str = "smartclinic.events"
    smartclinic_dlx: str = "smartclinic.events.dlx"

    # --- observability ---------------------------------------------------
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_otlp_protocol: Literal["grpc", "http/protobuf"] = "grpc"
    otel_service_namespace: str = "smartclinic"
    otel_resource_attributes: str = "deployment.environment=local"

    # --- oidc / keycloak -------------------------------------------------
    oidc_issuer: HttpUrl | None = None
    oidc_jwks_url: HttpUrl | None = None
    oidc_audience: str = "smartclinic-api"
    oidc_client_id: str = "smartclinic-api"
    oidc_client_secret: SecretStr | None = None
    oidc_jwks_cache_ttl_seconds: int = 300

    # --- outbox relay ----------------------------------------------------
    outbox_poll_interval_seconds: float = 2.0
    outbox_batch_size: int = 100
    outbox_max_attempts: int = 12

    # --- development ergonomics -----------------------------------------
    debug_exception_trace: bool = False
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["*"])

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION
