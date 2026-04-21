"""Request and response DTOs for the Patient Identity HTTP API.

These are *API models*, separate from both the domain objects and the
published-language event schemas. The separation buys us three things:

1. The API surface can evolve independently of the domain model.
2. We can omit, rename, and flatten fields for the HTTP caller's
   convenience without touching domain code.
3. PII sensitivity can be enforced at serialisation time (e.g.
   ``national_id`` is masked in the response unless the caller holds
   the ``receptionist`` role).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from patient_identity.domain.patient import Patient
from patient_identity.domain.value_objects import ConsentPurpose, Sex


class _APIBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class RegisterPatientRequest(_APIBase):
    given_name: str = Field(min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    family_name: str = Field(min_length=1, max_length=100)
    national_id: str = Field(
        description="Zimbabwean national ID (NN-NNNNNNNA-NN or local variants)."
    )
    date_of_birth: date
    sex: Sex
    email: str | None = None
    phone: str | None = None


class UpdateDemographicsRequest(_APIBase):
    given_name: str | None = Field(default=None, min_length=1, max_length=100)
    middle_name: str | None = None
    family_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = None
    phone: str | None = None
    clear_email: bool = False
    clear_phone: bool = False
    address: AddressRequest | None = None
    clear_address: bool = False
    next_of_kin: NextOfKinRequest | None = None
    clear_nok: bool = False


class AddressRequest(_APIBase):
    street: str = Field(min_length=1, max_length=200)
    suburb: str | None = Field(default=None, max_length=100)
    city: str = Field(min_length=1, max_length=100)
    province: str = Field(min_length=1, max_length=100)
    country: str = Field(default="Zimbabwe", max_length=100)


class NextOfKinRequest(_APIBase):
    given_name: str = Field(min_length=1, max_length=100)
    middle_name: str | None = None
    family_name: str = Field(min_length=1, max_length=100)
    relationship: str = Field(min_length=1, max_length=50)
    phone: str


class ConsentRequest(_APIBase):
    purpose: ConsentPurpose


# ---------------------------------------------------------------------------
# Response bodies
# ---------------------------------------------------------------------------


class RegisterPatientResponse(_APIBase):
    patient_id: uuid.UUID
    display_name: str
    message: str = "Patient registered successfully."


class ConsentResponse(_APIBase):
    purpose: ConsentPurpose
    is_active: bool
    granted_at: datetime
    granted_by: str
    revoked_at: datetime | None = None
    revoked_by: str | None = None


class PatientResponse(_APIBase):
    """Full patient view — shown to authenticated receptionists and doctors."""

    patient_id: uuid.UUID
    display_name: str
    given_name: str
    middle_name: str | None = None
    family_name: str
    date_of_birth: date
    sex: Sex
    email: str | None = None
    phone: str | None = None
    address: AddressResponse | None = None
    next_of_kin: NextOfKinResponse | None = None
    consents: list[ConsentResponse] = Field(default_factory=list)
    registered_at: datetime
    version: int

    @classmethod
    def from_domain(cls, patient: Patient) -> PatientResponse:
        return cls(
            patient_id=patient.id.value,
            display_name=patient.name.full,
            given_name=patient.name.given,
            middle_name=patient.name.middle,
            family_name=patient.name.family,
            date_of_birth=patient.date_of_birth.value,
            sex=patient.sex,
            email=str(patient.email.value) if patient.email else None,
            phone=patient.phone.value if patient.phone else None,
            address=(
                AddressResponse(
                    street=patient.address.street,
                    suburb=patient.address.suburb,
                    city=patient.address.city,
                    province=patient.address.province,
                    country=patient.address.country,
                )
                if patient.address
                else None
            ),
            next_of_kin=(
                NextOfKinResponse(
                    display_name=patient.next_of_kin.name.full,
                    relationship=patient.next_of_kin.relationship,
                    phone=patient.next_of_kin.phone.value,
                )
                if patient.next_of_kin
                else None
            ),
            consents=[
                ConsentResponse(
                    purpose=c.purpose,
                    is_active=c.is_active,
                    granted_at=c.granted_at,
                    granted_by=c.granted_by,
                    revoked_at=c.revoked_at,
                    revoked_by=c.revoked_by,
                )
                for c in patient.consents
            ],
            registered_at=patient.registered_at,
            version=patient.version,
        )


class PatientSummaryResponse(_APIBase):
    """Slim view used in search results — no PII-heavy fields."""

    patient_id: uuid.UUID
    display_name: str
    date_of_birth: date
    sex: Sex
    has_email: bool
    has_phone: bool

    @classmethod
    def from_domain(cls, patient: Patient) -> PatientSummaryResponse:
        return cls(
            patient_id=patient.id.value,
            display_name=patient.name.full,
            date_of_birth=patient.date_of_birth.value,
            sex=patient.sex,
            has_email=patient.email is not None,
            has_phone=patient.phone is not None,
        )


class AddressResponse(_APIBase):
    street: str
    suburb: str | None = None
    city: str
    province: str
    country: str


class NextOfKinResponse(_APIBase):
    display_name: str
    relationship: str
    phone: str


class PatientListResponse(_APIBase):
    items: list[PatientSummaryResponse]
    total: int
    limit: int
    offset: int
