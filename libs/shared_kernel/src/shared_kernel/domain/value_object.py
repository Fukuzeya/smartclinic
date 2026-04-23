"""Base class for all Value Objects.

A Value Object is:

* **Immutable** — once created, its field values never change.
* **Equal-by-value** — two VOs are equal iff all their fields are equal.
* **Self-validating** — construction fails fast on invalid input.
* **Replace-not-mutate** — "changes" return a new instance.

We layer these properties on top of Pydantic v2 ``BaseModel`` because
Pydantic gives us free validation, JSON (de)serialisation, and schema
generation — all essential for turning domain events into wire payloads
without infrastructure concerns leaking into domain code.
"""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict


class ValueObject(BaseModel):
    """Frozen, validated, equal-by-value Pydantic model.

    Subclass example::

        class Dosage(ValueObject):
            amount_mg: PositiveInt
            frequency_per_day: PositiveInt

    The subclass inherits ``frozen``, hashability, and the
    :meth:`with_` helper for non-mutating updates.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        # Strict mode globally would break JSON round-tripping of domain-event
        # payloads (StrEnum → string, Decimal → string) — field-level validators
        # remain the canonical enforcement point for invariants.
        validate_assignment=True,  # harmless with frozen, informative with mypy
        populate_by_name=True,
    )

    def with_(self, **updates: Any) -> Self:
        """Return a copy with ``updates`` applied. Preserves immutability.

        Pydantic's built-in ``model_copy(update=...)`` skips validation, which
        is unsafe for a domain VO. We round-trip through ``model_validate``
        so every "change" is re-checked against the invariants.
        """
        data = self.model_dump(mode="python") | updates
        return type(self).model_validate(data)

    def __hash__(self) -> int:
        # Hash by the tuple of field values — consistent with BaseModel's
        # frozen equality semantics and stable across processes.
        return hash((type(self), tuple(self.__dict__.items())))
