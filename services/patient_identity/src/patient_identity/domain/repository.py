"""Repository contract for the Patient aggregate.

The concrete implementation lives in :mod:`patient_identity.infrastructure`
and is swappable — a test can wire in an in-memory fake; a future
read-replica router could wire in a routing decorator — without the
domain or application layer changing.

This Protocol **extends** the generic repository contract from the
shared kernel with one context-specific lookup: by national id. That
lookup is domain-meaningful (national id uniqueness is an invariant)
and belongs on the interface, not on a generic ``QueryService``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from shared_kernel.types.identifiers import PatientId
from shared_kernel.types.national_id import ZimbabweanNationalId

from patient_identity.domain.patient import Patient


@runtime_checkable
class PatientRepository(Protocol):
    """Persistence boundary for :class:`Patient` aggregates.

    Implementations MUST:

    * Use optimistic concurrency — a ``save`` of a stale aggregate must
      raise :class:`shared_kernel.domain.exceptions.ConcurrencyConflict`.
    * Enlist every write on the caller's current transaction (the UoW
      is responsible for committing, not the repository).
    * Treat ``get`` failures as :class:`NotFound` rather than returning
      ``None`` — the type system and the handler logic are both simpler
      when the contract is total.
    """

    async def get(self, patient_id: PatientId) -> Patient: ...

    async def find_by_national_id(
        self, national_id: ZimbabweanNationalId
    ) -> Patient | None: ...

    async def add(self, patient: Patient) -> None: ...

    async def save(self, patient: Patient) -> None: ...
