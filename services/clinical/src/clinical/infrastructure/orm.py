"""Clinical ORM models.

Two tables:
* ``clinical_events`` — the hash-chained event store.  This is the write-side
  source of truth; there is no separate ``encounters`` aggregate-state table.
* ``encounter_summaries`` — the CQRS read model, populated by
  :mod:`clinical.infrastructure.projections` via event subscription.
"""

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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EventStoreRecord(Base):
    """One event in the hash-chained clinical event store (ADR 0012).

    ``chain_hash`` ties each record to the one before it:

        chain_hash[n] = SHA-256(chain_hash[n-1] | event_id | event_type | canonical_payload)

    For the first event of an aggregate, ``chain_hash[0]`` uses the sentinel
    ``GENESIS_HASH`` as the previous value.  This means any silent modification
    of any field in any historical event invalidates all subsequent hashes —
    providing medico-legal tamper evidence without a separate blockchain.

    ``sequence`` is a per-aggregate monotonically increasing counter and,
    together with ``aggregate_id``, forms the optimistic-concurrency check:
    a concurrent writer attempting to insert a duplicate ``(aggregate_id,
    sequence)`` pair will receive a ``UniqueConstraint`` violation which the
    repository maps to :class:`ConcurrencyConflict`.
    """

    __tablename__ = "clinical_events"
    __table_args__ = (
        UniqueConstraint("aggregate_id", "sequence", name="uq_clinical_events_agg_seq"),
        Index("ix_clinical_events_aggregate_id", "aggregate_id"),
        Index("ix_clinical_events_event_type", "event_type"),
        Index("ix_clinical_events_occurred_at", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(256), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    chain_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class AISuggestionRecord(Base):
    """Audit log for AI-generated clinical suggestions (ADR 0013).

    Kept separate from ``clinical_events`` so that AI suggestions are never
    part of the medico-legal event chain.  Each row records who requested the
    suggestion, which model produced it, and whether the clinician accepted or
    discarded it.
    """

    __tablename__ = "ai_suggestions"
    __table_args__ = (
        Index("ix_ai_suggestions_encounter_id", "encounter_id"),
        Index("ix_ai_suggestions_requested_by", "requested_by"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    encounter_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    suggestion_type: Mapped[str] = mapped_column(String(64), nullable=False)  # soap_draft | drug_safety
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_summary: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion_text: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decision: Mapped[str | None] = mapped_column(String(16), nullable=True)   # accepted | discarded
    decided_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EncounterSummaryRow(Base):
    """CQRS read model — denormalised projection of all encounter events.

    Populated by the projection subscriber (see ``projections.py``).
    Queried directly by the read-side API endpoints.
    Never updated by direct mutation — only via event application.
    """

    __tablename__ = "encounter_summaries"
    __table_args__ = (
        Index("ix_encounter_summaries_patient_id", "patient_id"),
        Index("ix_encounter_summaries_doctor_id", "doctor_id"),
        Index("ix_encounter_summaries_status", "status"),
        Index("ix_encounter_summaries_started_at", "started_at"),
    )

    encounter_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    patient_id: Mapped[str] = mapped_column(String(128), nullable=False)
    doctor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    appointment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    primary_icd10: Mapped[str | None] = mapped_column(String(16), nullable=True)
    has_prescription: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_lab_order: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    vital_signs_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    diagnoses_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
