"""Patient Identity — domain value objects.

These VOs model the *structure* of patient data. They are frozen,
equal-by-value, self-validating Pydantic models (inheriting from
:class:`shared_kernel.domain.value_object.ValueObject`).

Design decisions worth noting for the reviewer:

* ``Address`` uses Zimbabwean administrative terms (province / district).
  A production deployment in another country would subclass or swap via
  a port — same argument as ``ZimbabweanNationalId`` (see ADR 0007).
* ``DateOfBirth`` is a VO, not a raw ``date``, because the *invariant*
  "date of birth must not be in the future" belongs with the value, not
  with every caller.
* ``Consent`` is **event-shaped** — granting/revoking produces a new
  instance rather than mutating an existing one. This maps cleanly to
  the ``patient.consent_granted.v1`` / ``patient.consent_revoked.v1``
  events on the wire (see §4 of ``docs/security-and-compliance.md``).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from shared_kernel.domain.value_object import ValueObject
from shared_kernel.types.contact import Email, PhoneNumber
from shared_kernel.types.person_name import PersonName


class Sex(StrEnum):
    """Biological sex as recorded on clinical intake.

    This is distinct from gender identity — we store sex for its
    clinical relevance (reference ranges, dosing, diagnostic priors).
    ``UNKNOWN`` exists for cases where the patient is unconscious on
    arrival and the record is completed later.
    """

    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class DateOfBirth(ValueObject):
    """A validated date of birth.

    Invariants:

    * Must not be in the future.
    * Must not imply an age > 150 years (guards against typos like
      ``1023-05-14``).
    """

    value: date

    @field_validator("value")
    @classmethod
    def _plausible(cls, v: date) -> date:
        today = datetime.now(UTC).date()
        if v > today:
            raise ValueError("date of birth cannot be in the future")
        if (today.year - v.year) > 150:
            raise ValueError("implausible date of birth (> 150 years)")
        return v

    def age_in_years(self, *, as_of: date | None = None) -> int:
        """Full years of age on ``as_of`` (default: today, UTC)."""
        ref = as_of or datetime.now(UTC).date()
        years = ref.year - self.value.year
        if (ref.month, ref.day) < (self.value.month, self.value.day):
            years -= 1
        return years


class Address(ValueObject):
    """A Zimbabwean postal / residential address.

    Kept intentionally lightweight — we are not a CRM. If a future use
    case demands structured admin-area lookups (district → province), the
    right response is to introduce a reference dataset, not to extend
    this VO.
    """

    street: str = Field(min_length=1, max_length=200)
    suburb: str | None = Field(default=None, max_length=100)
    city: str = Field(min_length=1, max_length=100)
    province: str = Field(min_length=1, max_length=100)
    country: str = Field(default="Zimbabwe", max_length=100)

    @field_validator("street", "suburb", "city", "province", "country", mode="before")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s or None


class NextOfKin(ValueObject):
    """A patient's designated emergency contact.

    Deliberately **not** a separate entity: a next-of-kin has no
    identity independent of the patient record, and giving it one would
    invite a cascade of questions (merge on match? dedupe across
    patients?) that the domain does not ask.
    """

    name: PersonName
    relationship: str = Field(min_length=1, max_length=50)
    phone: PhoneNumber


class ConsentPurpose(StrEnum):
    """The purposes for which a patient may grant data-processing consent.

    Each purpose is a separate consent decision (POPIA §13 and the ZW
    Cyber Act §10): a patient may agree to share data with a medical aid
    but refuse research use. We therefore model consent as a *set* of
    granted purposes, not a single boolean.
    """

    TREATMENT = "treatment"
    BILLING = "billing"
    MEDICAL_AID_SHARE = "medical_aid_share"
    RESEARCH = "research"
    MARKETING = "marketing"


class Consent(ValueObject):
    """A single consent decision for a specific purpose.

    A ``Consent`` is either *granted* (``revoked_at`` is ``None``) or
    *revoked* (``revoked_at`` set). Revocation is a new, immutable
    instance — no field ever mutates.
    """

    purpose: ConsentPurpose
    granted_at: datetime
    granted_by: str = Field(min_length=1, max_length=100)
    revoked_at: datetime | None = None
    revoked_by: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _revocation_is_after_grant(self) -> Self:
        if self.revoked_at is not None:
            if self.revoked_at < self.granted_at:
                raise ValueError("revoked_at cannot predate granted_at")
            if not self.revoked_by:
                raise ValueError("revoked_at requires revoked_by")
        return self

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def revoke(self, *, at: datetime, by: str) -> Consent:
        """Return a revoked copy of this consent.

        Raises ``ValueError`` if the consent is already revoked — the
        domain does not silently no-op destructive state changes.
        """
        if not self.is_active:
            raise ValueError("consent already revoked")
        return self.with_(revoked_at=at, revoked_by=by)
