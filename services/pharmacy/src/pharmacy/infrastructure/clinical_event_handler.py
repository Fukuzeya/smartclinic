"""Pharmacy — subscriber that consumes Clinical context events.

This is the integration point that translates Clinical's Published Language
into Pharmacy domain objects (Anti-Corruption Layer responsibility).

Events consumed:
* ``clinical.encounter.prescription_issued.v1`` → creates a ``Prescription``
  aggregate in the Pharmacy context.
* ``patient.consent_granted.v1`` / ``patient.consent_revoked.v1`` →
  updates the local ``patient_consent_projection`` read model so the
  specification can check consent without a synchronous cross-service call.

Each handler is wrapped by the shared kernel's ``idempotent_consumer``
guard to ensure at-least-once delivery does not create duplicate prescriptions.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel.infrastructure.inbox import idempotent_consumer
from shared_kernel.infrastructure.logging import get_logger
from shared_kernel.types.identifiers import PrescriptionId

from pharmacy.domain.prescription import Prescription
from pharmacy.domain.value_objects import PrescriptionLine
from pharmacy.infrastructure.orm import PatientConsentProjectionRow, PrescriptionRow

log = get_logger(__name__)

CONSUMER_NAME = "pharmacy.clinical_prescription_intake"
CONSENT_CONSUMER = "pharmacy.patient_consent_projection"


async def handle_prescription_issued(
    session: AsyncSession,
    payload: dict[str, Any],
    event_id: uuid.UUID,
) -> None:
    """Translate a Clinical prescription event into a Pharmacy Prescription."""
    async with idempotent_consumer(session, event_id=event_id, consumer_name=CONSUMER_NAME) as is_new:
        if not is_new:
            return

        raw_lines: list[dict[str, Any]] = payload.get("lines", [])
        lines = [PrescriptionLine.model_validate(ln) for ln in raw_lines]

        # The prescription_id from Clinical is the canonical cross-context ID.
        prescription_id = PrescriptionId.parse(payload["prescription_id"])
        prescription = Prescription.receive(
            prescription_id=prescription_id,
            patient_id=payload["patient_id"],
            encounter_id=payload.get("encounter_id", ""),
            lines=lines,
            issued_by=payload.get("issued_by", ""),
        )

        # Persist directly as a row (events are drained by the UoW caller)
        row = PrescriptionRow(
            prescription_id=uuid.UUID(str(prescription.id)),
            encounter_id=prescription.encounter_id,
            patient_id=prescription.patient_id,
            issued_by=payload.get("issued_by", ""),
            lines=[ln.model_dump(mode="json") for ln in prescription.lines],
            status=prescription.status.value,
            version=0,
        )
        session.add(row)
        log.info(
            "pharmacy.prescription_received",
            prescription_id=str(prescription_id),
            patient_id=payload.get("patient_id"),
        )


async def handle_consent_granted(
    session: AsyncSession,
    payload: dict[str, Any],
    event_id: uuid.UUID,
) -> None:
    """Update local consent projection when a patient grants TREATMENT consent."""
    purpose = payload.get("purpose", "")
    if purpose != "TREATMENT":
        return  # Only care about treatment consent for dispensing decisions

    async with idempotent_consumer(session, event_id=event_id, consumer_name=CONSENT_CONSUMER) as is_new:
        if not is_new:
            return
        patient_id = payload["patient_id"]
        stmt = pg_insert(PatientConsentProjectionRow).values(
            patient_id=patient_id,
            has_treatment_consent=True,
        ).on_conflict_do_update(
            index_elements=["patient_id"],
            set_={"has_treatment_consent": True},
        )
        await session.execute(stmt)


async def handle_consent_revoked(
    session: AsyncSession,
    payload: dict[str, Any],
    event_id: uuid.UUID,
) -> None:
    """Update local consent projection when TREATMENT consent is revoked."""
    purpose = payload.get("purpose", "")
    if purpose != "TREATMENT":
        return

    async with idempotent_consumer(session, event_id=event_id, consumer_name=CONSENT_CONSUMER + ".revoke") as is_new:
        if not is_new:
            return
        patient_id = payload["patient_id"]
        stmt = pg_insert(PatientConsentProjectionRow).values(
            patient_id=patient_id,
            has_treatment_consent=False,
        ).on_conflict_do_update(
            index_elements=["patient_id"],
            set_={"has_treatment_consent": False},
        )
        await session.execute(stmt)


def make_clinical_event_handler(
    session_factory: async_sessionmaker[AsyncSession],
):
    """Return the dispatcher for all Clinical + Patient Identity events."""
    from shared_kernel.domain.domain_event import DomainEvent

    async def _dispatch(event: DomainEvent, message) -> None:
        async with session_factory() as session:
            async with session.begin():
                etype = event.event_type
                pid = event.event_id
                if etype == "clinical.encounter.prescription_issued.v1":
                    await handle_prescription_issued(session, event.payload, pid)
                elif etype == "patient.consent_granted.v1":
                    await handle_consent_granted(session, event.payload, pid)
                elif etype == "patient.consent_revoked.v1":
                    await handle_consent_revoked(session, event.payload, pid)

    return _dispatch
