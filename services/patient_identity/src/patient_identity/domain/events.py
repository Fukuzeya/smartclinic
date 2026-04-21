"""Domain events emitted by the Patient aggregate.

The **wire shape** of these events is our contract with every
downstream context (Scheduling, Clinical, Billing, …). Rules of thumb
that govern every field here:

1. **Version the event name, not the schema.** The trailing ``.v1`` is
   part of the contract; adding a new field is a *minor* change, but
   removing or repurposing a field requires ``.v2`` with both versions
   live during the migration window (see ADR 0008).
2. **Never include full PII** — downstream contexts hold narrow
   read-models (``PatientId`` + display name + relevant demographics).
   The National ID never leaves this context; see §4 of
   ``docs/security-and-compliance.md``.
3. **Past tense, immutable.** Events are facts about the past, not
   commands. Compensation is a new event.

Every payload is a typed Pydantic model so subscribers can validate on
receive without reaching for this package — they reconstruct the shape
from the published-language module instead.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from shared_kernel.domain.domain_event import DomainEvent
from shared_kernel.types.contact import Email, PhoneNumber
from shared_kernel.types.person_name import PersonName

from patient_identity.domain.value_objects import Address, ConsentPurpose, Sex


# ---------------------------------------------------------------------------
# Payload models — one per event. These carry the *minimum* fields that
# downstream consumers need; they are NOT a mirror of the Patient row.
# ---------------------------------------------------------------------------


class _PayloadBase(BaseModel):
    """Shared Pydantic configuration for every payload type."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        populate_by_name=True,
    )


class PatientRegisteredPayload(_PayloadBase):
    patient_id: str
    name: PersonName
    date_of_birth: datetime  # serialised as ISO-8601 date-time for Avro/JSON symmetry
    sex: Sex
    email: Email | None = None
    phone: PhoneNumber | None = None
    # National ID is NEVER placed on the wire. See §4 of security-and-compliance.md.
    registered_by: str


class DemographicsUpdatedPayload(_PayloadBase):
    patient_id: str
    name: PersonName
    email: Email | None = None
    phone: PhoneNumber | None = None
    address: Address | None = None
    updated_by: str


class ConsentGrantedPayload(_PayloadBase):
    patient_id: str
    purpose: ConsentPurpose
    granted_at: datetime
    granted_by: str


class ConsentRevokedPayload(_PayloadBase):
    patient_id: str
    purpose: ConsentPurpose
    revoked_at: datetime
    revoked_by: str


# ---------------------------------------------------------------------------
# Event classes — each subclass sets a stable ``event_type`` string that
# becomes the RabbitMQ routing key. The registry on ``DomainEvent`` picks
# the class up automatically via ``__init_subclass__``.
# ---------------------------------------------------------------------------


class PatientEvent(DomainEvent):
    """Shared base: every Patient aggregate event has ``aggregate_type="Patient"``."""

    aggregate_type: str = "Patient"


class PatientRegistered(PatientEvent):
    event_type: str = "patient.registered.v1"

    @classmethod
    def build(
        cls,
        *,
        aggregate_id: str,
        aggregate_version: int,
        data: PatientRegisteredPayload,
    ) -> PatientRegistered:
        return cls(
            aggregate_id=aggregate_id,
            aggregate_version=aggregate_version,
            payload=data.model_dump(mode="json"),
        )


class DemographicsUpdated(PatientEvent):
    event_type: str = "patient.demographics_updated.v1"

    @classmethod
    def build(
        cls,
        *,
        aggregate_id: str,
        aggregate_version: int,
        data: DemographicsUpdatedPayload,
    ) -> DemographicsUpdated:
        return cls(
            aggregate_id=aggregate_id,
            aggregate_version=aggregate_version,
            payload=data.model_dump(mode="json"),
        )


class ConsentGranted(PatientEvent):
    event_type: str = "patient.consent_granted.v1"

    @classmethod
    def build(
        cls,
        *,
        aggregate_id: str,
        aggregate_version: int,
        data: ConsentGrantedPayload,
    ) -> ConsentGranted:
        return cls(
            aggregate_id=aggregate_id,
            aggregate_version=aggregate_version,
            payload=data.model_dump(mode="json"),
        )


class ConsentRevoked(PatientEvent):
    event_type: str = "patient.consent_revoked.v1"

    @classmethod
    def build(
        cls,
        *,
        aggregate_id: str,
        aggregate_version: int,
        data: ConsentRevokedPayload,
    ) -> ConsentRevoked:
        return cls(
            aggregate_id=aggregate_id,
            aggregate_version=aggregate_version,
            payload=data.model_dump(mode="json"),
        )


__all__ = [
    "ConsentGranted",
    "ConsentGrantedPayload",
    "ConsentRevoked",
    "ConsentRevokedPayload",
    "DemographicsUpdated",
    "DemographicsUpdatedPayload",
    "PatientEvent",
    "PatientRegistered",
    "PatientRegisteredPayload",
]
