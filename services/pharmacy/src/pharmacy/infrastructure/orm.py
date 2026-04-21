"""Pharmacy ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PrescriptionRow(Base):
    """Pharmacy prescription state table.

    Note: this is a *state-based* aggregate — not event sourced.
    The event store lives in the Clinical context; Pharmacy only
    maintains its own dispensing view.
    """

    __tablename__ = "prescriptions"
    __table_args__ = (
        Index("ix_prescriptions_patient_id", "patient_id"),
        Index("ix_prescriptions_encounter_id", "encounter_id"),
        Index("ix_prescriptions_status", "status"),
    )

    prescription_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    encounter_id: Mapped[str] = mapped_column(String(128), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(128), nullable=False)
    issued_by: Mapped[str] = mapped_column(String(128), nullable=False)
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    dispensed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DrugStockRow(Base):
    """Drug inventory — updated by the dispensary management workflow."""

    __tablename__ = "drug_stock"
    __table_args__ = (
        Index("ix_drug_stock_drug_name", "drug_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    drug_name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    quantity_on_hand: Mapped[float] = mapped_column(nullable=False, default=0.0)
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="tablets")
    reorder_threshold: Mapped[float] = mapped_column(nullable=False, default=50.0)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PatientConsentProjectionRow(Base):
    """Local projection of patient consent from Patient Identity events.

    The Pharmacy service subscribes to ``patient.consent_granted.v1`` and
    ``patient.consent_revoked.v1`` to maintain a local read of TREATMENT
    consent per patient.  This avoids a synchronous call to the Patient
    Identity service on every dispensing decision.
    """

    __tablename__ = "patient_consent_projection"

    patient_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    has_treatment_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
