"""Write-side commands for the Patient Identity context.

Commands are validated, named intents to change state. They are the
*only* entry point for mutations — nothing changes a ``Patient`` outside
of a command handler.

Naming convention: imperative verb + noun, no suffix.
"""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import Field

from shared_kernel.application.command import Command

from patient_identity.domain.value_objects import ConsentPurpose, Sex


class RegisterPatient(Command):
    """Register a new patient with the clinic."""

    given_name: str = Field(min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    family_name: str = Field(min_length=1, max_length=100)
    national_id: str = Field(
        min_length=11,
        max_length=16,
        description="Zimbabwean national ID in canonical format (NN-NNNNNNNA-NN).",
    )
    date_of_birth: date
    sex: Sex
    email: str | None = Field(default=None, description="Must be RFC-5322 compliant.")
    phone: str | None = Field(
        default=None, description="E.164 or Zimbabwean local format."
    )
    # Caller-supplied id — useful for idempotent re-registration retries.
    patient_id: uuid.UUID | None = Field(
        default=None,
        description="If provided, used as the new patient's id. Must be globally unique.",
    )
    registered_by: str = Field(
        min_length=1,
        max_length=128,
        description="Subject claim (sub) of the calling Keycloak principal.",
    )


class UpdateDemographics(Command):
    """Patch one or more demographic fields on an existing patient."""

    patient_id: uuid.UUID
    given_name: str | None = Field(default=None, min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    family_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = None
    phone: str | None = None
    clear_email: bool = False
    clear_phone: bool = False
    # Address fields — all optional; omitting leaves the existing value.
    address_street: str | None = None
    address_suburb: str | None = None
    address_city: str | None = None
    address_province: str | None = None
    address_country: str | None = None
    clear_address: bool = False
    # Next of kin
    nok_given_name: str | None = None
    nok_family_name: str | None = None
    nok_relationship: str | None = None
    nok_phone: str | None = None
    clear_nok: bool = False
    updated_by: str = Field(min_length=1, max_length=128)


class GrantConsent(Command):
    """Record that a patient has granted consent for a processing purpose."""

    patient_id: uuid.UUID
    purpose: ConsentPurpose
    granted_by: str = Field(min_length=1, max_length=128)


class RevokeConsent(Command):
    """Record that a patient has revoked consent for a processing purpose."""

    patient_id: uuid.UUID
    purpose: ConsentPurpose
    revoked_by: str = Field(min_length=1, max_length=128)
