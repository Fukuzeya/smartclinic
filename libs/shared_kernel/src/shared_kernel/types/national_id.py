"""``ZimbabweanNationalId`` — canonical format validator.

The Zimbabwean national ID has the canonical form::

    NN-NNNNNNNA NN

That is: a two-digit district code, a dash, 6 or 7 digits, a single check
letter, and a two-digit province suffix (sometimes separated by a space).
Hyphens and spaces vary in the wild, so we normalise to
``NN-NNNNNNNA-NN`` on construction and surface the components as properties
for downstream use (e.g. the district maps to a catchment clinic).

This value object is Zimbabwe-specific on purpose. If the system ever
operates cross-border, the right abstraction is a ``NationalId`` interface
with per-country implementations behind an ACL — not a generic regex soup.
"""

from __future__ import annotations

import re

from pydantic import Field, field_validator

from shared_kernel.domain.value_object import ValueObject

# District (2 digits) - core (6 or 7 digits) check letter (A-Z) province (2 digits)
_ZW_ID_RAW_RE = re.compile(
    r"""
    ^
    (?P<district>\d{2})        # district
    [-\s]*
    (?P<core>\d{6,7})          # core number
    [-\s]*
    (?P<check>[A-Z])           # single check letter
    [-\s]*
    (?P<province>\d{2})        # province
    $
    """,
    re.VERBOSE,
)


class ZimbabweanNationalId(ValueObject):
    """A validated, canonicalised Zimbabwean national identity number."""

    value: str = Field(min_length=11, max_length=16)

    @field_validator("value", mode="before")
    @classmethod
    def _canonicalise(cls, v: str) -> str:
        if not isinstance(v, str):
            raise TypeError("national id must be a string")
        stripped = v.strip().upper()
        m = _ZW_ID_RAW_RE.match(stripped)
        if not m:
            raise ValueError(
                "invalid Zimbabwean national id (expected NN-NNNNNNNA-NN)"
            )
        return f"{m['district']}-{m['core']}{m['check']}-{m['province']}"

    @property
    def district_code(self) -> str:
        return self.value.split("-", 1)[0]

    @property
    def province_code(self) -> str:
        return self.value.rsplit("-", 1)[1]

    def __str__(self) -> str:  # pragma: no cover
        return self.value
