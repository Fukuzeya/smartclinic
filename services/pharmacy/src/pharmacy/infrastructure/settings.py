from __future__ import annotations

from shared_kernel.infrastructure.settings import SharedSettings


class PharmacySettings(SharedSettings):
    service_name: str = "pharmacy"
    database_url: str = "postgresql+asyncpg://pharmacy:pharmacy@localhost:5432/pharmacy"
    clinical_events_queue: str = "pharmacy.clinical.events"
    patient_events_queue: str = "pharmacy.patient.events"
    # RxNav API base URL — override to a local stub in test environments
    rxnav_base_url: str = "https://rxnav.nlm.nih.gov/REST"
    # When True, uses NullDrugInteractionChecker (e.g. offline deployment)
    rxnav_offline_mode: bool = False
