"""Pharmacy infrastructure — repository implementations."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shared_kernel.domain.exceptions import ConcurrencyConflict, NotFound
from shared_kernel.types.identifiers import PrescriptionId

from pharmacy.domain.prescription import Prescription
from pharmacy.domain.value_objects import (
    DispensingStatus,
    PrescriptionLine,
    StockLevel,
)
from pharmacy.infrastructure.orm import DrugStockRow, PatientConsentProjectionRow, PrescriptionRow


class SqlAlchemyPrescriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, prescription_id: PrescriptionId) -> Prescription:
        row = (
            await self._session.execute(
                select(PrescriptionRow).where(
                    PrescriptionRow.prescription_id == prescription_id.value
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFound(f"Prescription {prescription_id} not found")
        return _row_to_aggregate(row)

    async def add(self, prescription: Prescription) -> None:
        # Pre-compute post-commit version — UoW bumps after flush.
        final_version = prescription.version + len(prescription.peek_domain_events())
        row = PrescriptionRow(
            prescription_id=prescription.id.value,
            encounter_id=prescription.encounter_id,
            patient_id=prescription.patient_id,
            issued_by="",  # Set by handler from event
            lines=[ln.model_dump(mode="json") for ln in prescription.lines],
            status=prescription.status.value,
            version=final_version,
        )
        self._session.add(row)
        await self._session.flush()

    async def save(self, prescription: Prescription) -> None:
        row = (
            await self._session.execute(
                select(PrescriptionRow).where(
                    PrescriptionRow.prescription_id == prescription.id.value
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFound(f"Prescription {prescription.id} not found for save")
        if row.version != prescription.version:
            raise ConcurrencyConflict(
                f"Prescription {prescription.id}: version conflict "
                f"(loaded={prescription.version}, current={row.version})"
            )
        row.status = prescription.status.value
        row.version = prescription.version + len(prescription.peek_domain_events())
        if prescription.status == DispensingStatus.DISPENSED:
            from datetime import UTC, datetime
            row.dispensed_at = datetime.now(UTC)
        await self._session.flush()


class SqlAlchemyStockRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_drugs(self, drug_names: list[str]) -> list[StockLevel]:
        upper_names = [n.upper() for n in drug_names]
        rows = (
            await self._session.execute(
                select(DrugStockRow).where(
                    func.upper(DrugStockRow.drug_name).in_(upper_names)
                )
            )
        ).scalars().all()
        return [
            StockLevel(
                drug_name=r.drug_name,
                quantity_on_hand=Decimal(str(r.quantity_on_hand)),
                unit=r.unit,
                reorder_threshold=Decimal(str(r.reorder_threshold)),
            )
            for r in rows
        ]

    async def has_treatment_consent(self, patient_id: str) -> bool:
        row = (
            await self._session.execute(
                select(PatientConsentProjectionRow).where(
                    PatientConsentProjectionRow.patient_id == patient_id
                )
            )
        ).scalar_one_or_none()
        return row.has_treatment_consent if row else False


def _row_to_aggregate(row: PrescriptionRow) -> Prescription:
    lines = [PrescriptionLine.model_validate(ln) for ln in row.lines]
    return Prescription.rehydrate(
        prescription_id=PrescriptionId.parse(str(row.prescription_id)),
        version=row.version,
        patient_id=row.patient_id,
        encounter_id=row.encounter_id,
        lines=lines,
        status=DispensingStatus(row.status),
        received_at=row.received_at,
        dispensed_at=row.dispensed_at,
    )
