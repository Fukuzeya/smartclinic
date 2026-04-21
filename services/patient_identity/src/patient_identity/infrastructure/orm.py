"""SQLAlchemy ORM mappings for the Patient Identity context.

Two tables:

* ``patients`` — the aggregate state row.  One row per patient.
* ``patient_consents`` — one row per consent decision (grant or revoke).

We do **not** store the national ID in any shared table or event payload
(see ADR 0002 and ``docs/security-and-compliance.md`` §4). It is held
only here, encrypted at the column level in production deployments.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared_kernel.infrastructure.database import Base


class PatientRow(Base):
    """Persistent state for one Patient aggregate."""

    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("national_id", name="uq_patients_national_id"),
        Index("ix_patients_family_name", "family_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Demographics
    given_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    family_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # National ID — never exposed on the bus; keep here only.
    # In production this column should be encrypted (e.g. pgcrypto).
    national_id: Mapped[str] = mapped_column(String(32), nullable=False)

    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[str] = mapped_column(String(16), nullable=False)

    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Address (flat — avoids a pointless join for such a small record)
    address_street: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_suburb: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Next of kin (flat — same reasoning)
    nok_given_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nok_middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nok_family_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nok_relationship: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nok_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    registered_by: Mapped[str] = mapped_column(String(128), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    consents: Mapped[list[PatientConsentRow]] = relationship(
        "PatientConsentRow",
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PatientConsentRow(Base):
    """One consent decision for one purpose for one patient."""

    __tablename__ = "patient_consents"
    __table_args__ = (
        UniqueConstraint(
            "patient_id", "purpose", name="uq_patient_consents_patient_purpose"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    granted_by: Mapped[str] = mapped_column(String(128), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    patient: Mapped[PatientRow] = relationship("PatientRow", back_populates="consents")
