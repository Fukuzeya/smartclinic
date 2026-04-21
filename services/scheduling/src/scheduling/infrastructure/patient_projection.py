"""Inbox-based projection updater for Patient Identity events.

Subscribes to ``patient.registered.v1`` and ``patient.demographics_updated.v1``
to keep the ``patient_read_model`` table in sync. Uses the
``idempotent_consumer`` context manager from the shared kernel (ADR 0009)
so duplicate deliveries are silently skipped.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from shared_kernel.infrastructure.inbox import idempotent_consumer
from shared_kernel.infrastructure.logging import get_logger

from scheduling.infrastructure.orm import PatientReadModelRow

log = get_logger(__name__)

CONSUMER_NAME = "scheduling.patient_projection"


async def handle_patient_registered(
    session: AsyncSession, payload: dict[str, Any], event_id: uuid.UUID
) -> None:
    async with idempotent_consumer(
        session, event_id=event_id, consumer_name=CONSUMER_NAME
    ) as is_new:
        if not is_new:
            return
        patient_uuid = uuid.UUID(payload["patient_id"])
        existing = await session.get(PatientReadModelRow, patient_uuid)
        if existing is None:
            session.add(
                PatientReadModelRow(
                    patient_id=patient_uuid,
                    display_name=_display_name(payload),
                    date_of_birth=payload["date_of_birth"],
                    email=payload.get("email"),
                    phone=payload.get("phone"),
                )
            )
    log.debug(
        "scheduling.patient_projection.registered",
        patient_id=payload.get("patient_id"),
    )


async def handle_patient_demographics_updated(
    session: AsyncSession, payload: dict[str, Any], event_id: uuid.UUID
) -> None:
    async with idempotent_consumer(
        session, event_id=event_id, consumer_name=CONSUMER_NAME
    ) as is_new:
        if not is_new:
            return
        patient_uuid = uuid.UUID(payload["patient_id"])
        row = await session.get(PatientReadModelRow, patient_uuid)
        if row is None:
            row = PatientReadModelRow(
                patient_id=patient_uuid,
                display_name="",
                date_of_birth=payload.get("date_of_birth", "1900-01-01T00:00:00+00:00"),
            )
            session.add(row)
        row.display_name = _display_name(payload)
        row.email = payload.get("email")
        row.phone = payload.get("phone")


def _display_name(payload: dict[str, Any]) -> str:
    parts = [payload.get("given_name", "")]
    if payload.get("middle_name"):
        parts.append(payload["middle_name"])
    parts.append(payload.get("family_name", ""))
    return " ".join(p for p in parts if p)
