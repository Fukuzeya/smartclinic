from __future__ import annotations

from typing import Protocol

from shared_kernel.types.identifiers import EncounterId

from clinical.domain.encounter import Encounter


class EncounterRepository(Protocol):
    """Port for the encounter event store.

    ``get`` replays all events to reconstruct state (read model is separate).
    ``save`` appends new events to the event stream with hash chaining.
    ``add`` is an alias for save used by handlers creating new aggregates.
    """

    async def get(self, encounter_id: EncounterId) -> Encounter: ...
    async def add(self, encounter: Encounter) -> None: ...
    async def save(self, encounter: Encounter) -> None: ...
