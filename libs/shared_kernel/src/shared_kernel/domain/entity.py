"""The ``Entity`` base class.

An Entity has a *thread of continuity* — a persistent identity that distinguishes
it from other entities even when all of its attribute values are equal. In
SmartClinic, two ``Patient`` aggregates with identical names and dates of birth
are still distinct patients because their ``PatientId``\\ s differ.

Contrast with ``ValueObject``, which is equal-by-value.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

TId = TypeVar("TId")


class Entity(Generic[TId]):
    """An object whose identity is preserved across state changes.

    Subclasses must either:

    * pass the identity as the first argument of their ``__init__`` and call
      ``super().__init__(id=...)``, or
    * provide the identity via a dataclass/``__init__`` that sets ``_id``
      before any equality check is attempted.

    Equality and hashing are based on *type + identity*, never on attribute
    values. This prevents accidental collisions between (say) a ``Patient``
    and a ``Doctor`` that happen to share a UUID.
    """

    __slots__ = ("_id",)

    def __init__(self, *, id: TId) -> None:
        if id is None:
            raise ValueError("Entity identity must not be None")
        self._id: TId = id

    @property
    def id(self) -> TId:
        """The persistent identity of this entity."""
        return self._id

    def __eq__(self, other: object) -> bool:
        if other is self:
            return True
        if type(other) is not type(self):  # strict — subclass != parent
            return False
        return self._id == other._id  # type: ignore[attr-defined]

    def __hash__(self) -> int:
        return hash((type(self), self._id))

    def __repr__(self) -> str:  # pragma: no cover — trivial
        return f"{type(self).__name__}(id={self._id!r})"

    def _validate_identity_matches(self, other_id: Any) -> None:
        """Defensive helper: assert another object claims the same identity.

        Used by repositories to detect programmer errors where a command
        targets aggregate X but the handler inadvertently mutates aggregate Y.
        """
        if other_id != self._id:
            raise ValueError(
                f"Identity mismatch: expected {self._id!r}, got {other_id!r}"
            )
