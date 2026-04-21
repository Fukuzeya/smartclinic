"""``PersonName`` — a value object for patient and staff names.

Deliberately culture-agnostic: we store given/family/full separately, do
**not** enforce a middle name, and allow Unicode characters. The only
invariants are that (a) something must be present, (b) leading/trailing
whitespace is stripped, and (c) internal whitespace is collapsed.
"""

from __future__ import annotations

import re
from typing import Self

from pydantic import Field, field_validator, model_validator

from shared_kernel.domain.value_object import ValueObject

_WHITESPACE_RE = re.compile(r"\s+")


class PersonName(ValueObject):
    """A person's name, split into given and family components."""

    given: str = Field(min_length=1, max_length=100)
    family: str = Field(min_length=1, max_length=100)
    middle: str | None = Field(default=None, max_length=100)

    @field_validator("given", "family", "middle", mode="before")
    @classmethod
    def _normalise(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = _WHITESPACE_RE.sub(" ", str(v)).strip()
        return s or None

    @model_validator(mode="after")
    def _reject_empty(self) -> Self:
        if not self.given or not self.family:
            raise ValueError("PersonName requires both given and family components")
        return self

    @property
    def full(self) -> str:
        """Return the full name in 'Given [Middle] Family' order."""
        parts = [self.given]
        if self.middle:
            parts.append(self.middle)
        parts.append(self.family)
        return " ".join(parts)

    def __str__(self) -> str:  # pragma: no cover
        return self.full
