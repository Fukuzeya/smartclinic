"""Shared fixtures for Patient Identity domain unit tests."""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from shared_kernel.types.clock import FrozenClock
from shared_kernel.types.contact import Email, PhoneNumber
from shared_kernel.types.identifiers import PatientId
from shared_kernel.types.national_id import ZimbabweanNationalId
from shared_kernel.types.person_name import PersonName

from patient_identity.domain.patient import Patient
from patient_identity.domain.value_objects import DateOfBirth, Sex


@pytest.fixture()
def frozen_clock() -> FrozenClock:
    return FrozenClock(at=datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC))


@pytest.fixture()
def valid_name() -> PersonName:
    return PersonName(given="Tendai", family="Moyo")


@pytest.fixture()
def valid_national_id() -> ZimbabweanNationalId:
    return ZimbabweanNationalId(value="63-123456A-21")


@pytest.fixture()
def valid_dob() -> DateOfBirth:
    return DateOfBirth(value=date(1990, 6, 15))


@pytest.fixture()
def registered_patient(
    valid_name: PersonName,
    valid_national_id: ZimbabweanNationalId,
    valid_dob: DateOfBirth,
    frozen_clock: FrozenClock,
) -> Patient:
    return Patient.register(
        name=valid_name,
        national_id=valid_national_id,
        date_of_birth=valid_dob,
        sex=Sex.MALE,
        email=Email.of("tendai.moyo@example.com"),
        registered_by="recep-sub-001",
        clock=frozen_clock,
    )
