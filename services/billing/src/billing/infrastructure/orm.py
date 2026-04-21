from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class InvoiceRow(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_invoices_patient_id", "patient_id"),
        Index("ix_invoices_encounter_id", "encounter_id"),
        Index("ix_invoices_status", "status"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    patient_id: Mapped[str] = mapped_column(String(128), nullable=False)
    encounter_id: Mapped[str] = mapped_column(String(128), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    lines: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    payments: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
