"""Event-sourced repository for the Encounter aggregate.

Responsibilities:
1. **Load** (``get``): query all ``clinical_events`` rows for the given
   ``aggregate_id`` ordered by ``sequence``, deserialise each row back into
   the correct :class:`DomainEvent` subclass, and pass the list to
   :meth:`Encounter.rehydrate`.
2. **Save** (``save`` / ``add``): for each pending event on the aggregate,
   compute the next chain hash and insert a new ``EventStoreRecord`` row.
   No separate state row is written — the event stream *is* the aggregate.

Both operations use the ``AsyncSession`` supplied by the Unit of Work, so they
participate in the surrounding transaction.  The UoW ``commit()`` then drains
the pending events to the outbox for RabbitMQ publishing.

Optimistic concurrency is enforced by the ``UNIQUE(aggregate_id, sequence)``
constraint on ``clinical_events``: a concurrent writer attempting to append
at the same sequence number will receive a ``UniqueViolation`` which the
repository catches and re-raises as :class:`ConcurrencyConflict`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shared_kernel.domain.domain_event import DomainEvent
from shared_kernel.domain.exceptions import ConcurrencyConflict, NotFound
from shared_kernel.types.identifiers import EncounterId

from clinical.domain.encounter import Encounter
from clinical.infrastructure.event_store import GENESIS_HASH, compute_chain_hash
from clinical.infrastructure.orm import EventStoreRecord


class SqlAlchemyEncounterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------ read

    async def get(self, encounter_id: EncounterId) -> Encounter:
        """Rehydrate an Encounter by replaying its full event stream."""
        rows = (
            await self._session.execute(
                select(EventStoreRecord)
                .where(EventStoreRecord.aggregate_id == uuid.UUID(str(encounter_id)))
                .order_by(EventStoreRecord.sequence)
            )
        ).scalars().all()

        if not rows:
            raise NotFound(f"Encounter '{encounter_id}' not found in event store")

        events = [_row_to_domain_event(row) for row in rows]
        return Encounter.rehydrate(encounter_id=encounter_id, events=events)

    # ------------------------------------------------------------------ write

    async def add(self, encounter: Encounter) -> None:
        """Alias for :meth:`save` — used by handlers that create new aggregates."""
        await self.save(encounter)

    async def save(self, encounter: Encounter) -> None:
        """Append pending events to the event stream with hash chaining."""
        new_events = list(encounter.peek_domain_events())
        if not new_events:
            return

        # Retrieve the current tail of the chain for this aggregate.
        tail_row = (
            await self._session.execute(
                select(EventStoreRecord.chain_hash, EventStoreRecord.sequence)
                .where(EventStoreRecord.aggregate_id == uuid.UUID(str(encounter.id)))
                .order_by(EventStoreRecord.sequence.desc())
                .limit(1)
            )
        ).first()

        prev_hash: str = tail_row.chain_hash if tail_row else GENESIS_HASH
        next_seq: int = (tail_row.sequence + 1) if tail_row else 1

        try:
            for event in new_events:
                chain_hash = compute_chain_hash(
                    prev_hash=prev_hash,
                    event_id=str(event.event_id),
                    event_type=event.event_type,
                    payload=event.payload,
                )
                record = EventStoreRecord(
                    id=event.event_id,
                    aggregate_id=uuid.UUID(str(encounter.id)),
                    aggregate_type=event.aggregate_type,
                    event_type=event.event_type,
                    sequence=next_seq,
                    occurred_at=event.occurred_at,
                    payload=event.payload,
                    metadata_={
                        "correlation_id": event.correlation_id,
                        "trace_id": event.trace_id,
                        "causation_id": str(event.causation_id) if event.causation_id else None,
                        "aggregate_version": event.aggregate_version,
                    },
                    chain_hash=chain_hash,
                )
                self._session.add(record)
                prev_hash = chain_hash
                next_seq += 1
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConcurrencyConflict(
                f"Concurrent write conflict on Encounter '{encounter.id}': "
                "another writer appended to the same event stream."
            ) from exc

    # ------------------------------------------------------------------ chain audit

    async def verify_chain(self, encounter_id: EncounterId) -> dict[str, Any]:
        """Load and verify the hash chain for one encounter.  Admin / audit use."""
        from clinical.infrastructure.event_store import verify_chain
        rows = (
            await self._session.execute(
                select(EventStoreRecord)
                .where(EventStoreRecord.aggregate_id == uuid.UUID(str(encounter_id)))
                .order_by(EventStoreRecord.sequence)
            )
        ).scalars().all()
        result = verify_chain(rows)
        return {
            "encounter_id": str(encounter_id),
            "event_count": len(rows),
            "is_valid": result.is_valid,
            "message": result.message,
            "first_broken_sequence": result.first_broken_sequence,
        }


# ---------------------------------------------------------------------------
# Deserialization helpers

def _row_to_domain_event(row: EventStoreRecord) -> DomainEvent:
    """Reconstruct the correct ``DomainEvent`` subclass from a store row."""
    cls = DomainEvent.for_type(row.event_type) or DomainEvent
    meta = row.metadata_ or {}
    return cls.model_validate(
        {
            "event_id": row.id,
            "event_type": row.event_type,
            "occurred_at": row.occurred_at,
            "aggregate_id": str(row.aggregate_id),
            "aggregate_type": row.aggregate_type,
            "aggregate_version": meta.get("aggregate_version", row.sequence),
            "correlation_id": meta.get("correlation_id"),
            "trace_id": meta.get("trace_id"),
            "causation_id": meta.get("causation_id"),
            "payload": row.payload,
        }
    )
