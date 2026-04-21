"""Typed identifiers.

Plain ``UUID``\\ s are hazardous: a handler that accepts ``UUID`` has no way
to prevent a caller passing an ``EncounterId`` where a ``PatientId`` was
expected, and the bug is only caught at runtime via a foreign-key violation.

Typed ids fix this. Each concrete id class is a frozen Pydantic model with a
single ``value: UUID`` field — cheap at runtime, but distinct at the type
system level, so mypy rejects cross-context id mixing at compile time.

UUIDv7 is preferred because it is monotonically-increasing-by-time, which
dramatically improves B-tree index locality on Postgres compared to v4.
Python's stdlib only shipped ``uuid7`` in 3.12+, so we fall back to a small
pure-Python implementation on older interpreters — not expected to ever
trigger given our ``requires-python = ">=3.12"``.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any, ClassVar, Self

from pydantic import ConfigDict, Field, field_validator

from shared_kernel.domain.value_object import ValueObject


def new_uuid7() -> uuid.UUID:
    """Return a fresh UUIDv7 (time-ordered).

    Python 3.12 does not yet ship ``uuid.uuid7`` in the stdlib; we implement
    it per draft-ietf-uuidrev-rfc4122bis section 5.7. The implementation is
    intentionally small and dependency-free.
    """
    # 48 bits of unix_ts_ms
    ts_ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF  # 12 bits
    rand_b = int.from_bytes(os.urandom(8), "big") & 0x3FFFFFFFFFFFFFFF  # 62 bits
    # Layout:
    # unix_ts_ms (48) | ver=7 (4) | rand_a (12) | var=10b (2) | rand_b (62)
    as_int = (
        (ts_ms << 80)
        | (0x7 << 76)
        | (rand_a << 64)
        | (0b10 << 62)
        | rand_b
    )
    return uuid.UUID(int=as_int)


class Identifier(ValueObject):
    """Base class for context-specific typed identifiers.

    Subclasses only need to *exist* — they inherit ``value`` from here. The
    class name alone distinguishes two identifier types at runtime and in
    type-checker output.

    Example::

        class PatientId(Identifier): ...
        class EncounterId(Identifier): ...

        PatientId(value=some_uuid) == EncounterId(value=some_uuid)
        # → False: strict type equality.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        populate_by_name=True,
    )

    # The suffix used in string representation, e.g. "pat_"; overridden by
    # subclasses so ``str(id)`` is self-describing in logs.
    _prefix: ClassVar[str] = "id"

    value: uuid.UUID = Field(default_factory=new_uuid7)

    # Coerce strings/UUID-like inputs into a UUID so commands and events can
    # round-trip through JSON without gymnastics at every call site.
    @field_validator("value", mode="before")
    @classmethod
    def _coerce_value(cls, v: Any) -> uuid.UUID:
        if isinstance(v, uuid.UUID):
            return v
        if isinstance(v, str):
            return uuid.UUID(v)
        if isinstance(v, bytes) and len(v) == 16:
            return uuid.UUID(bytes=v)
        raise TypeError(f"cannot coerce {type(v).__name__} to UUID")

    @classmethod
    def new(cls) -> Self:
        """Mint a fresh identifier. Prefer this over calling the constructor."""
        return cls(value=new_uuid7())

    @classmethod
    def parse(cls, raw: str | uuid.UUID) -> Self:
        """Parse from a string or UUID; raises ``ValueError`` on garbage."""
        return cls(value=raw if isinstance(raw, uuid.UUID) else uuid.UUID(str(raw)))

    def __str__(self) -> str:
        return f"{self._prefix}_{self.value}"

    def __eq__(self, other: object) -> bool:
        # Distinct subclasses are never equal, even if their inner UUIDs match.
        if type(other) is not type(self):
            return NotImplemented
        return self.value == other.value  # type: ignore[attr-defined]

    def __hash__(self) -> int:
        return hash((type(self), self.value))


# --- Concrete identifiers ------------------------------------------------

class PatientId(Identifier):
    _prefix: ClassVar[str] = "pat"


class DoctorId(Identifier):
    _prefix: ClassVar[str] = "doc"


class AppointmentId(Identifier):
    _prefix: ClassVar[str] = "apt"


class EncounterId(Identifier):
    _prefix: ClassVar[str] = "enc"


class PrescriptionId(Identifier):
    _prefix: ClassVar[str] = "rx"


class DispensingId(Identifier):
    _prefix: ClassVar[str] = "dsp"


class LabOrderId(Identifier):
    _prefix: ClassVar[str] = "lab"


class BillId(Identifier):
    _prefix: ClassVar[str] = "bil"
