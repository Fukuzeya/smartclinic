"""SQLAlchemy-backed implementation of ``PatientRepository``.

Mapping between the ORM rows and the domain aggregate is explicit — we
never let SQLAlchemy instruments touch the aggregate directly, so the
domain model has zero infrastructure imports.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared_kernel.domain.exceptions import ConcurrencyConflict, NotFound
from shared_kernel.types.contact import Email, PhoneNumber
from shared_kernel.types.identifiers import PatientId
from shared_kernel.types.national_id import ZimbabweanNationalId
from shared_kernel.types.person_name import PersonName

from patient_identity.domain.patient import Patient
from patient_identity.domain.repository import PatientRepository as PatientRepositoryPort
from patient_identity.domain.value_objects import (
    Address,
    Consent,
    ConsentPurpose,
    DateOfBirth,
    NextOfKin,
    Sex,
)
from patient_identity.infrastructure.orm import PatientConsentRow, PatientRow


class SqlAlchemyPatientRepository:
    """Concrete repository backed by a single SQLAlchemy ``AsyncSession``.

    The session is injected by the Unit of Work, so *this class never
    commits*. Optimistic concurrency: we compare the loaded row's
    ``version`` against the aggregate's before overwriting.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, patient_id: PatientId) -> Patient:
        row = await self._session.get(
            PatientRow,
            patient_id.value,
            populate_existing=True,
        )
        if row is None:
            raise NotFound(f"patient '{patient_id.value}' not found")
        return _to_domain(row)

    async def find_by_national_id(
        self, national_id: ZimbabweanNationalId
    ) -> Patient | None:
        stmt = (
            select(PatientRow)
            .where(PatientRow.national_id == national_id.value)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def add(self, patient: Patient) -> None:
        row = _to_orm(patient)
        self._session.add(row)

    async def save(self, patient: Patient) -> None:
        row = await self._session.get(PatientRow, patient.id.value)
        if row is None:
            raise NotFound(f"patient '{patient.id.value}' not found for update")
        if row.version != patient.version:
            raise ConcurrencyConflict(
                f"patient '{patient.id.value}' version conflict: "
                f"expected {patient.version}, got {row.version}"
            )
        _update_row(row, patient)
        # Sync consent rows via upsert-by-purpose. We can't delete-then-reinsert
        # because SQLAlchemy orders INSERTs before DELETEs within a single flush,
        # which would violate the (patient_id, purpose) unique constraint when
        # re-granting a previously revoked consent.
        existing_by_purpose = {c.purpose: c for c in row.consents}
        aggregate_purposes = {c.purpose.value for c in patient.consents}
        for purpose, c_row in list(existing_by_purpose.items()):
            if purpose not in aggregate_purposes:
                await self._session.delete(c_row)
        for consent in patient.consents:
            existing = existing_by_purpose.get(consent.purpose.value)
            if existing is None:
                row.consents.append(
                    _consent_to_orm(str(patient.id.value), consent)
                )
            else:
                existing.granted_at = consent.granted_at
                existing.granted_by = consent.granted_by
                existing.revoked_at = consent.revoked_at
                existing.revoked_by = consent.revoked_by


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


def _to_domain(row: PatientRow) -> Patient:
    return Patient.rehydrate(
        id=PatientId(value=row.id),
        version=row.version,
        name=PersonName(
            given=row.given_name,
            middle=row.middle_name,
            family=row.family_name,
        ),
        national_id=ZimbabweanNationalId(value=row.national_id),
        date_of_birth=DateOfBirth(value=row.date_of_birth),
        sex=Sex(row.sex),
        email=Email(value=row.email) if row.email else None,
        phone=PhoneNumber(value=row.phone) if row.phone else None,
        address=_address_from_row(row),
        next_of_kin=_nok_from_row(row),
        consents=tuple(_consent_from_row(c) for c in row.consents),
        registered_at=row.registered_at,
        registered_by=row.registered_by,
    )


def _to_orm(patient: Patient) -> PatientRow:
    # Account for events already queued in this transaction. The UoW calls
    # `_bump_version()` at commit time — once per event — but by then the ORM
    # row has already been added to the session with whatever version we set
    # here. Pre-compute the post-commit version so the persisted row lines up
    # with the aggregate_version stamped on the emitted events.
    final_version = patient.version + len(patient.peek_domain_events())
    row = PatientRow(
        id=patient.id.value,
        version=final_version,
        given_name=patient.name.given,
        middle_name=patient.name.middle,
        family_name=patient.name.family,
        national_id=patient.national_id.value,
        date_of_birth=patient.date_of_birth.value,
        sex=patient.sex.value,
        email=str(patient.email.value) if patient.email else None,
        phone=patient.phone.value if patient.phone else None,
        registered_at=patient.registered_at,
        registered_by=patient.registered_by,
        **_address_to_row_kwargs(patient.address),
        **_nok_to_row_kwargs(patient.next_of_kin),
    )
    for consent in patient.consents:
        row.consents.append(_consent_to_orm(str(patient.id.value), consent))
    return row


def _update_row(row: PatientRow, patient: Patient) -> None:
    row.version = patient.version
    row.given_name = patient.name.given
    row.middle_name = patient.name.middle
    row.family_name = patient.name.family
    row.email = str(patient.email.value) if patient.email else None
    row.phone = patient.phone.value if patient.phone else None
    for k, v in _address_to_row_kwargs(patient.address).items():
        setattr(row, k, v)
    for k, v in _nok_to_row_kwargs(patient.next_of_kin).items():
        setattr(row, k, v)


def _address_from_row(row: PatientRow) -> Address | None:
    if row.address_street is None:
        return None
    return Address(
        street=row.address_street,
        suburb=row.address_suburb,
        city=row.address_city or "",
        province=row.address_province or "",
        country=row.address_country or "Zimbabwe",
    )


def _address_to_row_kwargs(address: Address | None) -> dict[str, str | None]:
    if address is None:
        return {
            "address_street": None,
            "address_suburb": None,
            "address_city": None,
            "address_province": None,
            "address_country": None,
        }
    return {
        "address_street": address.street,
        "address_suburb": address.suburb,
        "address_city": address.city,
        "address_province": address.province,
        "address_country": address.country,
    }


def _nok_from_row(row: PatientRow) -> NextOfKin | None:
    if row.nok_family_name is None:
        return None
    return NextOfKin(
        name=PersonName(
            given=row.nok_given_name or "",
            middle=row.nok_middle_name,
            family=row.nok_family_name,
        ),
        relationship=row.nok_relationship or "",
        phone=PhoneNumber(value=row.nok_phone or ""),
    )


def _nok_to_row_kwargs(nok: NextOfKin | None) -> dict[str, str | None]:
    if nok is None:
        return {
            "nok_given_name": None,
            "nok_middle_name": None,
            "nok_family_name": None,
            "nok_relationship": None,
            "nok_phone": None,
        }
    return {
        "nok_given_name": nok.name.given,
        "nok_middle_name": nok.name.middle,
        "nok_family_name": nok.name.family,
        "nok_relationship": nok.relationship,
        "nok_phone": nok.phone.value,
    }


def _consent_from_row(row: PatientConsentRow) -> Consent:
    return Consent(
        purpose=ConsentPurpose(row.purpose),
        granted_at=row.granted_at,
        granted_by=row.granted_by,
        revoked_at=row.revoked_at,
        revoked_by=row.revoked_by,
    )


def _consent_to_orm(patient_id_str: str, consent: Consent) -> PatientConsentRow:
    import uuid
    return PatientConsentRow(
        id=uuid.uuid4(),
        patient_id=uuid.UUID(patient_id_str),
        purpose=consent.purpose.value,
        granted_at=consent.granted_at,
        granted_by=consent.granted_by,
        revoked_at=consent.revoked_at,
        revoked_by=consent.revoked_by,
    )
