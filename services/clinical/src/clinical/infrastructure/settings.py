from __future__ import annotations

from shared_kernel.infrastructure.settings import SharedSettings


class ClinicalSettings(SharedSettings):
    service_name: str = "clinical"
    database_url: str = "postgresql+asyncpg://clinical:clinical@localhost:5432/clinical_write"
    clinical_events_queue: str = "clinical.events"
    # Optional — when set, AnthropicClinicalCopilot is used instead of MockClinicalCopilot
    anthropic_api_key: str | None = None
