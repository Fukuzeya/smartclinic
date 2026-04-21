from __future__ import annotations

from shared_kernel.infrastructure.settings import SharedSettings


class BillingSettings(SharedSettings):
    service_name: str = "billing"
    database_url: str = "postgresql+asyncpg://billing:billing@localhost:5432/billing"
    clinical_events_queue: str = "billing.clinical.events"
    laboratory_events_queue: str = "billing.laboratory.events"
