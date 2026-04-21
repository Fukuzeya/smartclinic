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
GET    /appointments?doctor_id=&date=         list for doctor   [receptionist, doctor]
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request, status

from shared_kernel.fastapi.dependencies import require_any_role, require_role
from shared_kernel.infrastructure.security import Principal
from shared_kernel.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork

from scheduling.api.dtos import (
    AppointmentListResponse,
    AppointmentResponse,
    BookAppointmentRequest,
    BookAppointmentResponse,
    CancelRequest,
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
    GetAppointmentHandler,
    GetAppointmentsForDoctorOnDateHandler,
    GetAppointmentsForPatientHandler,
    MarkNoShowHandler,
    RescheduleAppointmentHandler,
)
from scheduling.application.queries import (
    GetAppointment,
    GetAppointmentsForDoctorOnDate,
    GetAppointmentsForPatient,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])


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
    summary="List appointments (filter by patient_id OR doctor_id+date)",
)
async def list_appointments(
    request: Request,
    principal: Annotated[
        Principal, Depends(require_any_role("receptionist", "doctor"))
    ],
    patient_id: Optional[uuid.UUID] = Query(default=None),
    doctor_id: Optional[uuid.UUID] = Query(default=None),
    on_date: Optional[date] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AppointmentListResponse:
    async with _get_session(request) as session:
        if patient_id is not None:
            appointments = await GetAppointmentsForPatientHandler(session)(
                GetAppointmentsForPatient(
                    patient_id=patient_id, limit=limit, offset=offset
                )
            )
        elif doctor_id is not None and on_date is not None:
            appointments = await GetAppointmentsForDoctorOnDateHandler(session)(
                GetAppointmentsForDoctorOnDate(doctor_id=doctor_id, on_date=on_date)
            )
        else:
            appointments = []
    return AppointmentListResponse(
        items=[AppointmentResponse.from_domain(a) for a in appointments],
        total=len(appointments),
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
