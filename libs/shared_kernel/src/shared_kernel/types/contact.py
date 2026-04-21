"""Contact-information value objects: ``Email`` and ``PhoneNumber``.

``Email`` wraps Pydantic's battle-tested RFC 5322 validation; we keep the
concept as a ValueObject rather than a bare string so that repositories and
events are self-documenting about *what* string is expected.

``PhoneNumber`` normalises to E.164. Zimbabwe is country code 263, with
common prefixes 71/77/78 (mobile) and 242/292 (fixed). The validator accepts
several friendly input forms (``0771234567``, ``+263771234567``,
``263-77-123-4567``) and canonicalises them.
"""

from __future__ import annotations

import re
from typing import Self

from pydantic import EmailStr, Field, field_validator

from shared_kernel.domain.value_object import ValueObject


class Email(ValueObject):
    """An email address validated against RFC 5322 / 6531."""

    value: EmailStr

    @classmethod
    def of(cls, raw: str) -> Self:
        return cls(value=raw.strip())  # type: ignore[arg-type]

    def __str__(self) -> str:  # pragma: no cover
        return str(self.value)


# ---------------------------------------------------------------- phone numbers

_PHONE_STRIP_RE = re.compile(r"[\s\-().]+")
_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")
_ZIMBABWE_LOCAL_RE = re.compile(r"^0(7[1-9]\d{7}|[24-9]\d{7,8})$")
# ^0 + (mobile: 71..79 + 7 digits) | (landline: single digit + 7 or 8 digits)


class PhoneNumber(ValueObject):
    """An E.164-normalised phone number.

    Always stored with a leading ``+``; the country code is preserved. Use
    :meth:`country_code` and :meth:`national_number` for parts.
    """

    value: str = Field(min_length=8, max_length=20)

    @field_validator("value", mode="before")
    @classmethod
    def _normalise(cls, v: str) -> str:
        if not isinstance(v, str):
            raise TypeError("phone number must be a string")
        stripped = _PHONE_STRIP_RE.sub("", v.strip())
        # Convert familiar Zimbabwean local formats (0771234567) to E.164.
        if _ZIMBABWE_LOCAL_RE.match(stripped):
            stripped = "+263" + stripped[1:]
        # Strip leading 00 international prefix → +
        if stripped.startswith("00"):
            stripped = "+" + stripped[2:]
        if not stripped.startswith("+"):
            # Assume Zimbabwe if no country code given at all.
            stripped = "+263" + stripped.lstrip("0")
        if not _E164_RE.match(stripped):
            raise ValueError(f"invalid E.164 phone number: {v!r}")
        return stripped

    @property
    def country_code(self) -> str:
        """Two or three digit country code (digits only, no ``+``)."""
        # Minimal splitter: known ZW/ZA/US single-to-three digit codes are
        # enough for the in-scope dataset; production deployments should use
        # a full NSN/CC library like ``phonenumbers``.
        known_cc = ("263", "27", "1", "44")
        digits = self.value.lstrip("+")
        for cc in known_cc:
            if digits.startswith(cc):
                return cc
        return digits[:3]  # best effort

    @property
    def national_number(self) -> str:
        return self.value.lstrip("+").removeprefix(self.country_code)

    def __str__(self) -> str:  # pragma: no cover
        return self.value
