from __future__ import annotations

from shared_kernel.infrastructure.settings import SharedSettings


class LaboratorySettings(SharedSettings):
    service_name: str = "laboratory"
    database_url: str = "postgresql+asyncpg://laboratory:laboratory@localhost:5432/laboratory"
    clinical_events_queue: str = "laboratory.clinical.events"
    # Critical-alert notification webhook (optional; empty = disabled)
    critical_alert_webhook_url: str = ""
