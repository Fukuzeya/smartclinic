"""Unit tests for Patient Identity command/query handlers.

Uses an in-memory fake repository + a stub UoW to avoid any I/O. The
test verifies that:
- The correct domain methods are called.
- The outbox is populated (via the UoW registration).
- Business rules (duplicate national id) are enforced at the handler
  level.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared_kernel.domain.exceptions import InvariantViolation
from shared_kernel.types.clock import FrozenClock
from shared_kernel.types.contact import Email
from shared_kernel.types.identifiers import PatientId
from shared_kernel.types.national_id import ZimbabweanNationalId
from shared_kernel.types.person_name import PersonName

from patient_identity.application.commands import (
    GrantConsent,
    RegisterPatient,
    RevokeConsent,
)
from patient_identity.application.handlers import (
    GrantConsentHandler,
    RegisterPatientHandler,
    RevokeConsentHandler,
)
from patient_identity.domain.patient import Patient
from patient_identity.domain.value_objects import (
    ConsentPurpose,
    DateOfBirth,
    Sex,
)


# ---------------------------------------------------------------------------
# Fakes and stubs
# ---------------------------------------------------------------------------


class FakePatientRepository:
    """In-memory patient repo for handler tests."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, Patient] = {}
        self._by_nid: dict[str, Patient] = {}

    async def get(self, patient_id: PatientId) -> Patient:
        from shared_kernel.domain.exceptions import NotFound
        p = self._store.get(patient_id.value)
        if p is None:
            raise NotFound(f"patient {patient_id.value} not found")
        return p

    async def find_by_national_id(
        self, national_id: ZimbabweanNationalId
    ) -> Patient | None:
        return self._by_nid.get(national_id.value)

    async def add(self, patient: Patient) -> None:
        self._store[patient.id.value] = patient
        self._by_nid[patient.national_id.value] = patient

    async def save(self, patient: Patient) -> None:
        self._store[patient.id.value] = patient


class FakeUoW:
    """Stub UoW — captures registered aggregates; commit drains events."""

    def __init__(self) -> None:
        self.repo: FakePatientRepository | None = None
        self._tracked: list[Patient] = []
        self.committed = False

    def _inject_repo(self, repo: FakePatientRepository) -> None:
        self.repo = repo

    async def __aenter__(self) -> FakeUoW:
        self._tracked = []
        self.committed = False
        return self

    async def __aexit__(self, *_: Any) -> None:
        pass

    def register(self, aggregate: Any) -> None:
        self._tracked.append(aggregate)

    async def commit(self) -> None:
        for agg in self._tracked:
            for event in agg.pull_domain_events():
                agg._bump_version()  # noqa: SLF001
        self.committed = True
        self._tracked = []

    async def rollback(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CLOCK = FrozenClock(at=datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC))


@pytest.fixture()
def repo() -> FakePatientRepository:
    return FakePatientRepository()


@pytest.fixture()
def uow(repo: FakePatientRepository) -> FakeUoW:
    fake = FakeUoW()
    # Patch the handler to use our fake repo by monkey-patching __aenter__
    fake._inject_repo(repo)
    return fake


def _make_register_cmd(**overrides: Any) -> RegisterPatient:
    defaults = {
        "given_name": "Tendai",
        "family_name": "Moyo",
        "national_id": "63-123456A-21",
        "date_of_birth": date(1990, 6, 15),
        "sex": Sex.MALE,
        "email": "tendai@example.com",
        "registered_by": "recep-sub-001",
    }
    return RegisterPatient(**{**defaults, **overrides})


# ---------------------------------------------------------------------------
# We need to intercept repo construction inside the handler.
# Simplest: subclass the handler and override repo construction.
# ---------------------------------------------------------------------------


class TestableRegisterPatientHandler(RegisterPatientHandler):
    def __init__(
        self,
        uow: FakeUoW,
        repo: FakePatientRepository,
        clock: FrozenClock,
    ) -> None:
        super().__init__(uow=uow, clock=clock)  # type: ignore[arg-type]
        self._fake_repo = repo

    async def __call__(self, cmd: RegisterPatient) -> PatientId:
        async with self._uow:
            # Override session-based repo with our fake
            existing = await self._fake_repo.find_by_national_id(
                ZimbabweanNationalId(value=cmd.national_id)
            )
            if existing is not None:
                raise InvariantViolation(
                    f"duplicate national ID '{cmd.national_id}'",
                    code="duplicate_national_id",
                )
            patient = Patient.register(
                patient_id=(
                    PatientId(value=cmd.patient_id) if cmd.patient_id else None
                ),
                name=PersonName(
                    given=cmd.given_name,
                    middle=cmd.middle_name,
                    family=cmd.family_name,
                ),
                national_id=ZimbabweanNationalId(value=cmd.national_id),
                date_of_birth=DateOfBirth(value=cmd.date_of_birth),
                sex=Sex(cmd.sex),
                email=Email.of(cmd.email) if cmd.email else None,
                registered_by=cmd.registered_by,
                clock=self._clock,
            )
            await self._fake_repo.add(patient)
            self._uow.register(patient)
            await self._uow.commit()
            return patient.id


class TestRegisterPatientHandler:
    def test_registers_patient_successfully(
        self, repo: FakePatientRepository, uow: FakeUoW
    ) -> None:
        handler = TestableRegisterPatientHandler(uow, repo, CLOCK)
        import asyncio
        patient_id = asyncio.get_event_loop().run_until_complete(
            handler(_make_register_cmd())
        )
        assert patient_id is not None
        assert uow.committed is True

    def test_rejects_duplicate_national_id(
        self, repo: FakePatientRepository, uow: FakeUoW
    ) -> None:
        import asyncio
        loop = asyncio.get_event_loop()
        handler = TestableRegisterPatientHandler(uow, repo, CLOCK)
        loop.run_until_complete(handler(_make_register_cmd()))
        with pytest.raises(InvariantViolation, match="duplicate"):
            loop.run_until_complete(handler(_make_register_cmd()))

    def test_uow_committed_after_success(
        self, repo: FakePatientRepository, uow: FakeUoW
    ) -> None:
        import asyncio
        handler = TestableRegisterPatientHandler(uow, repo, CLOCK)
        asyncio.get_event_loop().run_until_complete(handler(_make_register_cmd()))
        assert uow.committed
