from __future__ import annotations

from shared_kernel.infrastructure.settings import SharedSettings


class SagaSettings(SharedSettings):
    service_name: str = "saga_orchestrator"
    database_url: str = "postgresql+asyncpg://saga:saga@localhost:5432/saga"
    # Single queue that receives events from ALL contexts
    all_events_queue: str = "saga.all.events"
