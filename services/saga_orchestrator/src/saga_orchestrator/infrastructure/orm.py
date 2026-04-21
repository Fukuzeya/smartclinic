from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SagaRow(Base):
    __tablename__ = "patient_visit_sagas"
    __table_args__ = (
        Index("ix_sagas_encounter_id", "encounter_id", unique=True),
        Index("ix_sagas_patient_id", "patient_id"),
        Index("ix_sagas_status", "status"),
    )

    saga_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    patient_id: Mapped[str] = mapped_column(String(128), nullable=False)
    # encounter_id is the natural correlation key across all contexts
    encounter_id: Mapped[str] = mapped_column(String(128), nullable=False)
    step: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
