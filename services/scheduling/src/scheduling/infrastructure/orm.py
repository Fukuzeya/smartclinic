"""ORM models for the Scheduling context.

Two tables:
* ``appointments`` — aggregate state.
* ``patient_read_model`` — narrow projection kept up-to-date by
  subscribing to ``patient.*`` events from Patient Identity; allows
  look-ups and display-name resolution without cross-context DB calls.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.infrastructure.database import Base


class AppointmentRow(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appointments_patient_id", "patient_id"),
        Index("ix_appointments_doctor_id_start", "doctor_id", "start_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1)

    patient_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    doctor_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    booked_by: Mapped[str] = mapped_column(String(128), nullable=False)
    booked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PatientReadModelRow(Base):
    """Scheduling's narrow view of Patient Identity data.

    Populated by subscribing to ``patient.registered.v1`` and
    ``patient.demographics_updated.v1`` events via the Inbox pattern.
    Never contains the National ID.
    """

    __tablename__ = "patient_read_model"

    patient_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(250), nullable=False)
    date_of_birth: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
