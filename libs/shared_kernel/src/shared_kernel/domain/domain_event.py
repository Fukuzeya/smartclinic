"""Domain events — the Published Language across bounded contexts.

A domain event is an **immutable fact** about something that happened in the
past tense (``EncounterDiagnosed``, ``PrescriptionIssued``). Once emitted, it
cannot be undone; compensation is modelled as a *new* event, not a mutation.

Events carry the minimum payload needed by downstream contexts — they are
**not** a universal read-model and **not** a serialisation of the aggregate.
Treat the event schema as a public API and version it explicitly when it
must change (see ADR 0008).

Every event is signed with causation / correlation / trace identifiers so a
distributed trace can be reconstructed from the event log alone — critical
for medico-legal audit (see ADR 0012).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticUndefined


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DomainEvent(BaseModel):
    """Immutable fact emitted by an aggregate.

    Subclasses should set :attr:`event_type` to a stable, dot-namespaced
    identifier (``"clinical.encounter.diagnosed.v1"``). The ``.v1`` suffix
    is mandatory for cross-context events and lets subscribers run multiple
    schema versions side-by-side during migrations.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        populate_by_name=True,
    )

    # Registry of subclass → canonical event_type, populated by
    # ``__init_subclass__``. Used by the event bus for deserialisation.
    _REGISTRY: ClassVar[dict[str, type[DomainEvent]]] = {}

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: str
    occurred_at: datetime = Field(default_factory=_utcnow)

    # Identity of the aggregate that produced the event. ``str`` (not a typed
    # id) because events are consumed across contexts that don't share each
    # other's id types.
    aggregate_id: str
    aggregate_type: str
    aggregate_version: int = Field(ge=1)

    # Distributed-tracing correlation fields. ``trace_id`` / ``correlation_id``
    # are propagated from the HTTP request; ``causation_id`` is the event that
    # directly caused this one (for saga reconstruction).
    trace_id: str | None = None
    correlation_id: str | None = None
    causation_id: uuid.UUID | None = None

    # Free-form domain payload. Kept as a typed Pydantic model in subclasses
    # — this base-level field only exists so the event bus can deserialise
    # without the concrete class in scope.
    payload: dict[str, Any] = Field(default_factory=dict)

    # Strict mode rejects string→UUID / string→datetime coercion, but the
    # event bus delivers JSON-encoded messages where both arrive as strings.
    # These ``mode="before"`` validators accept the wire format without
    # loosening strictness for any other field.
    @field_validator("event_id", "causation_id", mode="before")
    @classmethod
    def _coerce_uuid(cls, v: Any) -> Any:
        if isinstance(v, str):
            return uuid.UUID(v)
        return v

    @field_validator("occurred_at", mode="before")
    @classmethod
    def _coerce_datetime(cls, v: Any) -> Any:
        if isinstance(v, str):
            return datetime.fromisoformat(v)
        return v

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        # Pydantic v2 calls this *after* ``model_fields`` is populated, unlike
        # the plain ``__init_subclass__`` hook which fires before field
        # processing and therefore sees PydanticUndefined defaults.
        super().__pydantic_init_subclass__(**kwargs)
        field = cls.model_fields.get("event_type")
        if field is None:
            return
        default = field.default
        if default is PydanticUndefined or default in (None, ""):
            return
        DomainEvent._REGISTRY[str(default)] = cls

    @classmethod
    def for_type(cls, event_type: str) -> type[DomainEvent] | None:
        """Resolve a registered subclass from its ``event_type`` string.

        Returns ``None`` if no subclass is registered; the event bus then
        falls back to the base :class:`DomainEvent` so the consumer can
        inspect the payload manually.
        """
        return cls._REGISTRY.get(event_type)
