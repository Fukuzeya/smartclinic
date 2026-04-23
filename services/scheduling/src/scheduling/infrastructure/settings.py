"""Scheduling service configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from shared_kernel.infrastructure.settings import SharedSettings


class SchedulingSettings(SharedSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="allow", env_prefix="")

    database_url: str = Field(
        default="postgresql+asyncpg://scheduling:scheduling@localhost:5432/scheduling"
    )
    service_name: str = "scheduling"
    cors_allow_origins: list[str] = Field(default=["http://localhost:4200"])
    max_search_results: int = Field(default=50, ge=1, le=200)
    # Queue from which this service consumes patient events
    patient_events_queue: str = "scheduling.patient.events"
    keycloak_base_url: str = Field(default="http://keycloak:8080")
    keycloak_realm: str = Field(default="smartclinic")
