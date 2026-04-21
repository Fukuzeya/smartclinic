"""Patient Identity service configuration.

Extends the shared ``SharedSettings`` (which already covers RabbitMQ,
OIDC, OTel, outbox polling interval, etc.). Any Patient-Identity-
specific configuration knobs belong here.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from shared_kernel.infrastructure.settings import SharedSettings


class PatientIdentitySettings(SharedSettings):
    """Runtime configuration for the patient_identity service.

    All fields are read from environment variables (case-insensitive) or
    from a ``.env`` file in the working directory. See ``.env.example``
    at the repo root for the full list with documentation.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow",
        env_prefix="",
    )

    # Database (each service has its own Postgres database)
    database_url: str = Field(
        default="postgresql+asyncpg://smartclinic:smartclinic@localhost:5432/patient_identity",
        description="Async SQLAlchemy DSN for the patient_identity Postgres DB.",
    )

    # Service identity (used by OTel, Prometheus labels, and the outbox relay)
    service_name: str = "patient_identity"

    # CORS — tightened per-service from the shared default in production
    cors_allow_origins: list[str] = Field(
        default=["http://localhost:4200"],
        description="Allowed CORS origins. Wildcard only in dev.",
    )

    # Search page size cap — prevents large unbounded reads
    max_search_results: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum rows returned by the patient search endpoint.",
    )
