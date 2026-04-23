"""Scheduling HTTP API router.

Endpoints
---------
POST   /appointments                          book              [receptionist]
GET    /appointments/{id}                     get one           [receptionist, doctor]
POST   /appointments/{id}/check-in            check in          [receptionist]
POST   /appointments/{id}/cancel              cancel            [receptionist]
POST   /appointments/{id}/no-show             mark no-show      [receptionist]
PATCH  /appointments/{id}/reschedule          reschedule        [receptionist]
GET    /appointments?patient_id=              list for patient  [receptionist, doctor]
GET    /appointments?doctor_id=&on_date=      list for doctor   [receptionist, doctor]
GET    /appointments?on_date=&status=         list all          [receptionist]
GET    /staff/doctors?q=                      search doctors    [receptionist]
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
import uuid
from datetime import date, timedelta, datetime, timezone
from typing import Annotated, Optional

from sqlalchemy import and_, func, select as sa_select

from fastapi import APIRouter, Depends, Query, Request, status

from shared_kernel.fastapi.dependencies import require_any_role, require_role
from shared_kernel.infrastructure.security import Principal
from shared_kernel.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork

from scheduling.infrastructure.orm import AppointmentRow
from scheduling.api.dtos import (
    AppointmentListResponse,
    AppointmentResponse,
    BookAppointmentRequest,
    BookAppointmentResponse,
    CancelRequest,
    DoctorSummary,
    DoctorListResponse,
    RescheduleRequest,
)
from scheduling.application.commands import (
    BookAppointment,
    CancelAppointment,
    CheckInAppointment,
    MarkNoShow,
    RescheduleAppointment,
)
from scheduling.application.handlers import (
    BookAppointmentHandler,
    CancelAppointmentHandler,
    CheckInAppointmentHandler,
    GetAllAppointmentsHandler,
    GetAppointmentHandler,
    GetAppointmentsForDoctorOnDateHandler,
    GetAppointmentsForPatientHandler,
    MarkNoShowHandler,
    RescheduleAppointmentHandler,
)
from scheduling.application.queries import (
    GetAllAppointments,
    GetAppointment,
    GetAppointmentsForDoctorOnDate,
    GetAppointmentsForPatient,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])
staff_router = APIRouter(prefix="/staff", tags=["staff"])


def _get_uow(request: Request) -> SqlAlchemyUnitOfWork:
    return request.app.state.uow_factory()


def _get_session(request: Request):  # noqa: ANN202
    return request.app.state.session_factory()


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=BookAppointmentResponse,
    summary="Book a new appointment",
)
async def book_appointment(
    body: BookAppointmentRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require_role("receptionist"))],
) -> BookAppointmentResponse:
    handler = BookAppointmentHandler(uow=_get_uow(request))
    appt_id = await handler(
        BookAppointment(
            patient_id=body.patient_id,
            doctor_id=body.doctor_id,
            start_at=body.start_at,
            end_at=body.end_at,
            reason=body.reason,
            booked_by=principal.subject,
        )
    )
    return BookAppointmentResponse(appointment_id=appt_id.value)


@router.get(
    "",
    response_model=AppointmentListResponse,
    summary="List appointments — filter by patient_id, doctor_id+on_date, or all with optional on_date/status",
)
async def list_appointments(
    request: Request,
    principal: Annotated[
        Principal, Depends(require_any_role("receptionist", "doctor"))
    ],
    patient_id: Optional[uuid.UUID] = Query(default=None),
    doctor_id: Optional[uuid.UUID] = Query(default=None),
    on_date: Optional[date] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AppointmentListResponse:
    async with _get_session(request) as session:
        if patient_id is not None:
            appointments = await GetAppointmentsForPatientHandler(session)(
                GetAppointmentsForPatient(
                    patient_id=patient_id, limit=limit, offset=offset
                )
            )
            count_stmt = (
                sa_select(func.count())
                .select_from(AppointmentRow)
                .where(AppointmentRow.patient_id == patient_id)
            )
        elif doctor_id is not None and on_date is not None:
            appointments = await GetAppointmentsForDoctorOnDateHandler(session)(
                GetAppointmentsForDoctorOnDate(doctor_id=doctor_id, on_date=on_date)
            )
            day_start = datetime(on_date.year, on_date.month, on_date.day, tzinfo=timezone.utc)
            day_end = day_start + timedelta(days=1)
            count_stmt = (
                sa_select(func.count())
                .select_from(AppointmentRow)
                .where(and_(
                    AppointmentRow.doctor_id == doctor_id,
                    AppointmentRow.start_at >= day_start,
                    AppointmentRow.start_at < day_end,
                ))
            )
        else:
            appointments = await GetAllAppointmentsHandler(session)(
                GetAllAppointments(
                    on_date=on_date, status=status, limit=limit, offset=offset
                )
            )
            filters = []
            if on_date is not None:
                day_start = datetime(on_date.year, on_date.month, on_date.day, tzinfo=timezone.utc)
                day_end = day_start + timedelta(days=1)
                filters.append(AppointmentRow.start_at >= day_start)
                filters.append(AppointmentRow.start_at < day_end)
            if status is not None:
                filters.append(AppointmentRow.status == status)
            count_stmt = sa_select(func.count()).select_from(AppointmentRow)
            if filters:
                count_stmt = count_stmt.where(and_(*filters))
        total: int = (await session.execute(count_stmt)).scalar_one()
    return AppointmentListResponse(
        items=[AppointmentResponse.from_domain(a) for a in appointments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Get a single appointment",
)
async def get_appointment(
    appointment_id: uuid.UUID,
    request: Request,
    principal: Annotated[
        Principal, Depends(require_any_role("receptionist", "doctor"))
    ],
) -> AppointmentResponse:
    async with _get_session(request) as session:
        appt = await GetAppointmentHandler(session)(
            GetAppointment(appointment_id=appointment_id)
        )
    return AppointmentResponse.from_domain(appt)


@router.post(
    "/{appointment_id}/check-in",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Check a patient in to their appointment",
)
async def check_in(
    appointment_id: uuid.UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require_role("receptionist"))],
) -> None:
    await CheckInAppointmentHandler(uow=_get_uow(request))(
        CheckInAppointment(
            appointment_id=appointment_id, checked_in_by=principal.subject
        )
    )


@router.post(
    "/{appointment_id}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel an appointment",
)
async def cancel_appointment(
    appointment_id: uuid.UUID,
    body: CancelRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require_role("receptionist"))],
) -> None:
    await CancelAppointmentHandler(uow=_get_uow(request))(
        CancelAppointment(
            appointment_id=appointment_id,
            reason=body.reason,
            cancelled_by=principal.subject,
        )
    )


@router.post(
    "/{appointment_id}/no-show",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark appointment as no-show",
)
async def no_show(
    appointment_id: uuid.UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require_role("receptionist"))],
) -> None:
    await MarkNoShowHandler(uow=_get_uow(request))(
        MarkNoShow(appointment_id=appointment_id, marked_by=principal.subject)
    )


@router.patch(
    "/{appointment_id}/reschedule",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reschedule an appointment to a new slot",
)
async def reschedule(
    appointment_id: uuid.UUID,
    body: RescheduleRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require_role("receptionist"))],
) -> None:
    await RescheduleAppointmentHandler(uow=_get_uow(request))(
        RescheduleAppointment(
            appointment_id=appointment_id,
            new_start_at=body.new_start_at,
            new_end_at=body.new_end_at,
            rescheduled_by=principal.subject,
        )
    )


def _keycloak_admin_token(base_url: str) -> str:
    """Obtain a short-lived Keycloak admin token using admin credentials."""
    data = urllib.parse.urlencode({
        "client_id": "admin-cli",
        "username": "admin",
        "password": "admin",
        "grant_type": "password",
    }).encode()
    req = urllib.request.Request(
        f"{base_url}/realms/master/protocol/openid-connect/token",
        data=data,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())["access_token"]


def _keycloak_doctors(base_url: str, realm: str, q: str) -> list[dict]:
    """Query Keycloak admin REST API for users with the 'doctor' role."""
    token = _keycloak_admin_token(base_url)
    # Get users assigned to the 'doctor' realm role
    url = f"{base_url}/admin/realms/{realm}/roles/doctor/users?max=100"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        users: list[dict] = json.loads(resp.read())
    if q:
        q_lower = q.lower()
        users = [
            u for u in users
            if q_lower in (u.get("firstName", "") + " " + u.get("lastName", "")).lower()
            or q_lower in u.get("username", "").lower()
        ]
    return users


@staff_router.get(
    "/doctors",
    response_model=DoctorListResponse,
    summary="Search doctors by name (proxies Keycloak admin API)",
)
async def search_doctors(
    request: Request,
    principal: Annotated[Principal, Depends(require_any_role("receptionist", "doctor", "pharmacist", "lab_technician", "accounts"))],
    q: str = Query(default="", description="Name or username fragment"),
) -> DoctorListResponse:
    settings = request.app.state.settings
    base_url: str = getattr(settings, "keycloak_base_url", "http://keycloak:8080")
    realm: str = getattr(settings, "keycloak_realm", "smartclinic")
    try:
        users = _keycloak_doctors(base_url, realm, q)
    except Exception:
        users = []
    items = [
        DoctorSummary(
            doctor_id=u["id"],
            display_name=f"{u.get('firstName', '')} {u.get('lastName', '')}".strip() or u.get("username", ""),
            username=u.get("username", ""),
            email=u.get("email"),
        )
        for u in users
    ]
    return DoctorListResponse(items=items, total=len(items))
