"""Command and query handlers for the Patient Identity context.

Handlers implement the application-layer use cases. They:

1. Validate cross-aggregate invariants not expressible in the domain
   alone (duplicate national ID, etc.).
2. Delegate state change to the aggregate.
3. Persist via the Unit of Work (which also writes the outbox row
   atomically — see ADR 0009).

Handlers MUST NOT commit the UoW themselves; the caller (typically the
router or a test fixture) commits after the handler returns.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared_kernel.domain.exceptions import InvariantViolation, NotFound
from shared_kernel.infrastructure.logging import get_logger
from shared_kernel.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork
from shared_kernel.types.clock import Clock, SystemClock
from shared_kernel.types.contact import Email, PhoneNumber
from shared_kernel.types.identifiers import PatientId
from shared_kernel.types.national_id import ZimbabweanNationalId
from shared_kernel.types.person_name import PersonName

from patient_identity.application.commands import (
    GrantConsent,
    RegisterPatient,
    RevokeConsent,
    UpdateDemographics,
)
from patient_identity.application.queries import (
    FindPatientByNationalId,
    GetPatient,
    SearchPatients,
)
from patient_identity.domain.patient import Patient
from patient_identity.domain.value_objects import (
    Address,
    DateOfBirth,
    NextOfKin,
    Sex,
)
from patient_identity.infrastructure.orm import PatientRow
from patient_identity.infrastructure.repository import SqlAlchemyPatientRepository

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


class RegisterPatientHandler:
    """Handle :class:`RegisterPatient` — creates a new ``Patient`` aggregate."""

    def __init__(
        self,
        uow: SqlAlchemyUnitOfWork,
        clock: Clock | None = None,
    ) -> None:
        self._uow = uow
        self._clock = clock or SystemClock()

    async def __call__(self, cmd: RegisterPatient) -> PatientId:
        async with self._uow:
            repo = SqlAlchemyPatientRepository(self._uow.session)

            national_id = ZimbabweanNationalId(value=cmd.national_id)
            existing = await repo.find_by_national_id(national_id)
            if existing is not None:
                raise InvariantViolation(
                    f"a patient with national ID '{national_id.value}' already exists",
                    code="duplicate_national_id",
                )

            patient = Patient.register(
                patient_id=PatientId(value=cmd.patient_id) if cmd.patient_id else None,
                name=PersonName(
                    given=cmd.given_name,
                    middle=cmd.middle_name,
                    family=cmd.family_name,
                ),
                national_id=national_id,
                date_of_birth=DateOfBirth(value=cmd.date_of_birth),
                sex=Sex(cmd.sex),
                email=Email.of(cmd.email) if cmd.email else None,
                phone=PhoneNumber(value=cmd.phone) if cmd.phone else None,
                registered_by=cmd.registered_by,
                clock=self._clock,
            )
            await repo.add(patient)
            self._uow.register(patient)
            await self._uow.commit()
            log.info(
                "patient.registered",
                patient_id=str(patient.id.value),
                registered_by=cmd.registered_by,
            )
            return patient.id


class UpdateDemographicsHandler:
    """Handle :class:`UpdateDemographics` — patches fields on an existing patient."""

    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow

    async def __call__(self, cmd: UpdateDemographics) -> None:
        async with self._uow:
            repo = SqlAlchemyPatientRepository(self._uow.session)
            patient = await repo.get(PatientId(value=cmd.patient_id))

            name: PersonName | None = None
            if cmd.given_name or cmd.family_name:
                name = PersonName(
                    given=cmd.given_name or patient.name.given,
                    middle=cmd.middle_name if cmd.middle_name is not None else patient.name.middle,
                    family=cmd.family_name or patient.name.family,
                )

            address: Address | None = None
            if cmd.clear_address:
                address = None
            elif any(
                x is not None
                for x in (
                    cmd.address_street,
                    cmd.address_city,
                    cmd.address_province,
                )
            ):
                existing_addr = patient.address
                address = Address(
                    street=cmd.address_street or (existing_addr.street if existing_addr else ""),
                    suburb=cmd.address_suburb if cmd.address_suburb is not None else (existing_addr.suburb if existing_addr else None),
                    city=cmd.address_city or (existing_addr.city if existing_addr else ""),
                    province=cmd.address_province or (existing_addr.province if existing_addr else ""),
                    country=existing_addr.country if existing_addr else "Zimbabwe",
                )

            nok: NextOfKin | None = None
            if cmd.clear_nok:
                nok = None
            elif cmd.nok_family_name or cmd.nok_phone:
                existing_nok = patient.next_of_kin
                nok = NextOfKin(
                    name=PersonName(
                        given=cmd.nok_given_name or (existing_nok.name.given if existing_nok else ""),
                        family=cmd.nok_family_name or (existing_nok.name.family if existing_nok else ""),
                    ),
                    relationship=cmd.nok_relationship or (existing_nok.relationship if existing_nok else ""),
                    phone=PhoneNumber(value=cmd.nok_phone or (existing_nok.phone.value if existing_nok else "")),
                )

            patient.update_demographics(
                name=name,
                email=Email.of(cmd.email) if cmd.email else None,
                phone=PhoneNumber(value=cmd.phone) if cmd.phone else None,
                address=address,
                next_of_kin=nok,
                clear_email=cmd.clear_email,
                clear_phone=cmd.clear_phone,
                updated_by=cmd.updated_by,
            )
            await repo.save(patient)
            self._uow.register(patient)
            await self._uow.commit()


class GrantConsentHandler:
    def __init__(
        self,
        uow: SqlAlchemyUnitOfWork,
        clock: Clock | None = None,
    ) -> None:
        self._uow = uow
        self._clock = clock or SystemClock()

    async def __call__(self, cmd: GrantConsent) -> None:
        async with self._uow:
            repo = SqlAlchemyPatientRepository(self._uow.session)
            patient = await repo.get(PatientId(value=cmd.patient_id))
            patient.grant_consent(
                purpose=cmd.purpose,
                granted_by=cmd.granted_by,
                clock=self._clock,
            )
            await repo.save(patient)
            self._uow.register(patient)
            await self._uow.commit()


class RevokeConsentHandler:
    def __init__(
        self,
        uow: SqlAlchemyUnitOfWork,
        clock: Clock | None = None,
    ) -> None:
        self._uow = uow
        self._clock = clock or SystemClock()

    async def __call__(self, cmd: RevokeConsent) -> None:
        async with self._uow:
            repo = SqlAlchemyPatientRepository(self._uow.session)
            patient = await repo.get(PatientId(value=cmd.patient_id))
            patient.revoke_consent(
                purpose=cmd.purpose,
                revoked_by=cmd.revoked_by,
                clock=self._clock,
            )
            await repo.save(patient)
            self._uow.register(patient)
            await self._uow.commit()


# ---------------------------------------------------------------------------
# Query handlers — read straight from the ORM table; no UoW needed.
# ---------------------------------------------------------------------------


class GetPatientHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __call__(self, query: GetPatient) -> Patient:
        repo = SqlAlchemyPatientRepository(self._session)
        return await repo.get(PatientId(value=query.patient_id))


class FindPatientByNationalIdHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __call__(self, query: FindPatientByNationalId) -> Patient | None:
        repo = SqlAlchemyPatientRepository(self._session)
        return await repo.find_by_national_id(
            ZimbabweanNationalId(value=query.national_id)
        )


class SearchPatientsHandler:
    def __init__(self, session: AsyncSession, max_results: int = 50) -> None:
        self._session = session
        self._max_results = max_results

    async def __call__(self, query: SearchPatients) -> list[Patient]:
        limit = min(query.limit, self._max_results)
        stmt = (
            select(PatientRow)
            .where(PatientRow.family_name.ilike(f"%{query.name_fragment}%"))
            .order_by(PatientRow.family_name, PatientRow.given_name)
            .limit(limit)
            .offset(query.offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        from patient_identity.infrastructure.repository import _to_domain
        return [_to_domain(r) for r in rows]
