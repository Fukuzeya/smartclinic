from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class LabOrderRow(Base):
    __tablename__ = "lab_orders"
    __table_args__ = (
        Index("ix_lab_orders_patient_id", "patient_id"),
        Index("ix_lab_orders_encounter_id", "encounter_id"),
        Index("ix_lab_orders_status", "status"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    patient_id: Mapped[str] = mapped_column(String(128), nullable=False)
    encounter_id: Mapped[str] = mapped_column(String(128), nullable=False)
    ordered_by: Mapped[str] = mapped_column(String(128), nullable=False)
    lines: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    results: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    sample_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
