"""Version-1 event schemas for the Patient Identity published language.

These are the shapes that appear on the RabbitMQ wire. All fields are
Python primitives or enums — no internal domain types cross this
boundary. Consumers reconstruct the relevant projection from these
fields alone.

IMPORTANT constraints for schema evolution (see ADR 0008):
* Adding a new **optional** field: backward-compatible, no version bump.
* Removing a field or changing its type: requires ``.v2``.
* Renaming a field: treat as remove + add → requires ``.v2``.

Routing keys (= ``event_type`` values):
    patient.registered.v1
    patient.demographics_updated.v1
    patient.consent_granted.v1
    patient.consent_revoked.v1
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _V1Base(BaseModel):
    """Shared config for all v1 wire schemas."""

    model_config = ConfigDict(
        frozen=True,
        extra="allow",  # forward-compat: new optional fields don't break consumers
        populate_by_name=True,
    )

    event_id: str = Field(description="UUID of the emitting event (idempotency key).")
    event_type: str
    occurred_at: datetime
    aggregate_id: str = Field(description="PatientId UUID (string).")
    correlation_id: str | None = None
    trace_id: str | None = None


class PatientRegisteredV1(_V1Base):
    """A new patient was registered.

    Routing key: ``patient.registered.v1``

    Downstream contexts subscribe to this event to bootstrap their
    patient projection (PatientId + display name + DOB for age-range
    queries).
    """

    event_type: Literal["patient.registered.v1"] = "patient.registered.v1"

    patient_id: str = Field(description="Stable UUID-string; never changes.")
    given_name: str
    middle_name: str | None = None
    family_name: str
    display_name: str = Field(
        description="'Given [Middle] Family' — pre-computed for display use."
    )
    date_of_birth: datetime = Field(
        description="ISO-8601 datetime at midnight UTC. Day precision only."
    )
    sex: str = Field(description="'male' | 'female' | 'unknown'")
    email: str | None = None
    phone: str | None = None
    registered_by: str


class PatientDemographicsUpdatedV1(_V1Base):
    """Patient demographic data was updated.

    Routing key: ``patient.demographics_updated.v1``

    Consumers should replace their cached projection values with the
    ones provided. Fields absent from a specific event remain unchanged
    (PATCH semantics). ``email`` and ``phone`` being ``None`` here means
    they were explicitly cleared (see ``clear_email`` / ``clear_phone``
    flags on the command).
    """

    event_type: Literal["patient.demographics_updated.v1"] = (
        "patient.demographics_updated.v1"
    )

    patient_id: str
    given_name: str
    middle_name: str | None = None
    family_name: str
    display_name: str
    email: str | None = None
    phone: str | None = None
    updated_by: str


class PatientConsentGrantedV1(_V1Base):
    """A patient granted data-processing consent for a specific purpose.

    Routing key: ``patient.consent_granted.v1``

    Downstream contexts that gate operations on consent (e.g. Billing
    requiring ``billing`` consent before issuing an invoice) subscribe
    to this to maintain a local consent cache.
    """

    event_type: Literal["patient.consent_granted.v1"] = "patient.consent_granted.v1"

    patient_id: str
    purpose: str = Field(
        description="ConsentPurpose value: treatment | billing | medical_aid_share | research | marketing"
    )
    granted_at: datetime
    granted_by: str


class PatientConsentRevokedV1(_V1Base):
    """A patient revoked data-processing consent for a specific purpose.

    Routing key: ``patient.consent_revoked.v1``

    This is a **Right-to-be-Forgotten trigger** for the ``research``
    and ``marketing`` purposes. The Clinical context listens for
    ``treatment`` revocations and schedules crypto-shredding of that
    patient's event-store key (ADR 0012).
    """

    event_type: Literal["patient.consent_revoked.v1"] = "patient.consent_revoked.v1"

    patient_id: str
    purpose: str
    revoked_at: datetime
    revoked_by: str
