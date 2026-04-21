"""FastAPI router — Patient Identity HTTP API.

Endpoint summary
----------------
POST   /patients                         register a patient            [receptionist]
GET    /patients/{patient_id}            get one patient               [receptionist, doctor]
PATCH  /patients/{patient_id}            update demographics           [receptionist, doctor]
GET    /patients                         search by name                [receptionist, doctor]
POST   /patients/{patient_id}/consents   grant consent                 [receptionist]
DELETE /patients/{patient_id}/consents/{purpose}  revoke consent       [receptionist]
GET    /patients/{patient_id}/consents   list consent decisions        [receptionist, doctor]

All mutations return a ``204 No Content`` (except registration which returns
``201 Created`` + the new patient_id) to reflect that the HTTP layer is an
entry-point for commands, not a mirror of aggregate state. Clients that need
the updated view issue a subsequent GET.

IDOR (see threat model §2.2): access scope is intentionally coarse for Phase 2
— any authenticated user with the right *role* can read any patient. Phase 3+
will add appointment-based scoping once the Scheduling context is live.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from shared_kernel.fastapi.dependencies import require_any_role, require_role
from shared_kernel.infrastructure.security import Principal
from shared_kernel.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork

from patient_identity.application.commands import (
    GrantConsent,
    RegisterPatient,
    RevokeConsent,
    UpdateDemographics,
)
from patient_identity.application.handlers import (
    FindPatientByNationalIdHandler,
    GetPatientHandler,
    GrantConsentHandler,
    RegisterPatientHandler,
    RevokeConsentHandler,
    SearchPatientsHandler,
    UpdateDemographicsHandler,
)
from patient_identity.application.queries import GetPatient, SearchPatients
from patient_identity.api.dtos import (
    ConsentRequest,
    PatientListResponse,
    PatientResponse,
    PatientSummaryResponse,
    RegisterPatientRequest,
    RegisterPatientResponse,
    UpdateDemographicsRequest,
)
from patient_identity.domain.value_objects import ConsentPurpose

router = APIRouter(prefix="/patients", tags=["patients"])

# --------------------------------------------------------------------------
# Dependency helpers — wired via request.app.state (set in main.py)
# --------------------------------------------------------------------------


def _get_uow(request: Request) -> SqlAlchemyUnitOfWork:
    return request.app.state.uow_factory()


def _get_session(request: Request):  # noqa: ANN202
    return request.app.state.session_factory()


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterPatientResponse,
    summary="Register a new patient",
)
async def register_patient(
    body: RegisterPatientRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require_role("receptionist"))],
) -> RegisterPatientResponse:
    handler = RegisterPatientHandler(uow=_get_uow(request))
    patient_id = await handler(
        RegisterPatient(
            given_name=body.given_name,
            middle_name=body.middle_name,
            family_name=body.family_name,
            national_id=body.national_id,
            date_of_birth=body.date_of_birth,
            sex=body.sex,
            email=body.email,
            phone=body.phone,
            registered_by=principal.subject,
        )
    )
    return RegisterPatientResponse(
        patient_id=patient_id.value,
        display_name=f"{body.given_name} {body.family_name}",
    )


@router.get(
    "",
    response_model=PatientListResponse,
    summary="Search patients by family name",
)
async def search_patients(
    name_fragment: str,
    request: Request,
    principal: Annotated[
        Principal, Depends(require_any_role("receptionist", "doctor"))
    ],
    limit: int = 20,
    offset: int = 0,
) -> PatientListResponse:
    async with _get_session(request) as session:
        handler = SearchPatientsHandler(
            session, max_results=request.app.state.settings.max_search_results
        )
        patients = await handler(
            SearchPatients(
                name_fragment=name_fragment,
                limit=limit,
                offset=offset,
            )
        )
    return PatientListResponse(
        items=[PatientSummaryResponse.from_domain(p) for p in patients],
        total=len(patients),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Get a single patient",
)
async def get_patient(
    patient_id: uuid.UUID,
    request: Request,
    principal: Annotated[
        Principal, Depends(require_any_role("receptionist", "doctor"))
    ],
) -> PatientResponse:
    async with _get_session(request) as session:
        handler = GetPatientHandler(session)
        patient = await handler(GetPatient(patient_id=patient_id))
    return PatientResponse.from_domain(patient)


@router.patch(
    "/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Update patient demographics (PATCH)",
)
async def update_demographics(
    patient_id: uuid.UUID,
    body: UpdateDemographicsRequest,
    request: Request,
    principal: Annotated[
        Principal, Depends(require_any_role("receptionist", "doctor"))
    ],
) -> None:
    handler = UpdateDemographicsHandler(uow=_get_uow(request))

    # Flatten nested address / nok into the command
    addr = body.address
    nok = body.next_of_kin
    await handler(
        UpdateDemographics(
            patient_id=patient_id,
            given_name=body.given_name,
            middle_name=body.middle_name,
            family_name=body.family_name,
            email=body.email,
            phone=body.phone,
            clear_email=body.clear_email,
            clear_phone=body.clear_phone,
            address_street=addr.street if addr else None,
            address_suburb=addr.suburb if addr else None,
            address_city=addr.city if addr else None,
            address_province=addr.province if addr else None,
            address_country=addr.country if addr else None,
            clear_address=body.clear_address,
            nok_given_name=nok.given_name if nok else None,
            nok_family_name=nok.family_name if nok else None,
            nok_relationship=nok.relationship if nok else None,
            nok_phone=nok.phone if nok else None,
            clear_nok=body.clear_nok,
            updated_by=principal.subject,
        )
    )


@router.get(
    "/{patient_id}/consents",
    summary="List all consent decisions for a patient",
)
async def list_consents(
    patient_id: uuid.UUID,
    request: Request,
    principal: Annotated[
        Principal, Depends(require_any_role("receptionist", "doctor"))
    ],
) -> list[dict]:
    async with _get_session(request) as session:
        handler = GetPatientHandler(session)
        patient = await handler(GetPatient(patient_id=patient_id))
    return [
        {
            "purpose": c.purpose.value,
            "is_active": c.is_active,
            "granted_at": c.granted_at.isoformat(),
            "granted_by": c.granted_by,
            "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
            "revoked_by": c.revoked_by,
        }
        for c in patient.consents
    ]


@router.post(
    "/{patient_id}/consents",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Grant consent for a processing purpose",
)
async def grant_consent(
    patient_id: uuid.UUID,
    body: ConsentRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require_role("receptionist"))],
) -> None:
    handler = GrantConsentHandler(uow=_get_uow(request))
    await handler(
        GrantConsent(
            patient_id=patient_id,
            purpose=body.purpose,
            granted_by=principal.subject,
        )
    )


@router.delete(
    "/{patient_id}/consents/{purpose}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke consent for a processing purpose",
)
async def revoke_consent(
    patient_id: uuid.UUID,
    purpose: ConsentPurpose,
    request: Request,
    principal: Annotated[Principal, Depends(require_role("receptionist"))],
) -> None:
    handler = RevokeConsentHandler(uow=_get_uow(request))
    await handler(
        RevokeConsent(
            patient_id=patient_id,
            purpose=purpose,
            revoked_by=principal.subject,
        )
    )
