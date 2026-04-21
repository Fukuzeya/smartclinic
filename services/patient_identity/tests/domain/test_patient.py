"""Unit tests for the Patient aggregate.

Covers every invariant, every event emission, and the key no-op guards.
No database, no bus, no I/O — pure domain logic.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from shared_kernel.domain.exceptions import InvariantViolation, PreconditionFailed
from shared_kernel.types.clock import FrozenClock
from shared_kernel.types.contact import Email, PhoneNumber
from shared_kernel.types.identifiers import PatientId
from shared_kernel.types.national_id import ZimbabweanNationalId
from shared_kernel.types.person_name import PersonName

from patient_identity.domain.events import (
    ConsentGranted,
    ConsentRevoked,
    DemographicsUpdated,
    PatientRegistered,
)
from patient_identity.domain.patient import Patient
from patient_identity.domain.value_objects import (
    Address,
    ConsentPurpose,
    DateOfBirth,
    Sex,
)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegister:
    def test_emits_registered_event(self, registered_patient: Patient) -> None:
        events = registered_patient.peek_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], PatientRegistered)

    def test_event_carries_correct_payload(self, registered_patient: Patient) -> None:
        event = registered_patient.peek_domain_events()[0]
        assert event.payload["patient_id"] == str(registered_patient.id.value)
        assert event.payload["sex"] == "male"
        assert event.payload["registered_by"] == "recep-sub-001"
        # National ID MUST NOT appear in any event payload
        assert "national_id" not in event.payload

    def test_event_version_is_one(self, registered_patient: Patient) -> None:
        event = registered_patient.peek_domain_events()[0]
        assert event.aggregate_version == 1

    def test_aggregate_version_still_zero_before_commit(
        self, registered_patient: Patient
    ) -> None:
        # The UoW bumps version on commit; the aggregate itself starts at 0.
        assert registered_patient.version == 0

    def test_requires_at_least_one_contact(
        self,
        valid_name: PersonName,
        valid_national_id: ZimbabweanNationalId,
        valid_dob: DateOfBirth,
        frozen_clock: FrozenClock,
    ) -> None:
        with pytest.raises(InvariantViolation, match="contact"):
            Patient.register(
                name=valid_name,
                national_id=valid_national_id,
                date_of_birth=valid_dob,
                sex=Sex.FEMALE,
                registered_by="recep-sub-001",
                clock=frozen_clock,
            )

    def test_rejects_empty_registered_by(
        self,
        valid_name: PersonName,
        valid_national_id: ZimbabweanNationalId,
        valid_dob: DateOfBirth,
        frozen_clock: FrozenClock,
    ) -> None:
        with pytest.raises(InvariantViolation, match="registered_by"):
            Patient.register(
                name=valid_name,
                national_id=valid_national_id,
                date_of_birth=valid_dob,
                sex=Sex.MALE,
                phone=PhoneNumber(value="+263771234567"),
                registered_by="   ",
                clock=frozen_clock,
            )

    def test_caller_supplied_patient_id_is_used(
        self,
        valid_name: PersonName,
        valid_national_id: ZimbabweanNationalId,
        valid_dob: DateOfBirth,
        frozen_clock: FrozenClock,
    ) -> None:
        fixed_id = PatientId.new()
        patient = Patient.register(
            patient_id=fixed_id,
            name=valid_name,
            national_id=valid_national_id,
            date_of_birth=valid_dob,
            sex=Sex.MALE,
            email=Email.of("x@example.com"),
            registered_by="recep-sub-001",
            clock=frozen_clock,
        )
        assert patient.id == fixed_id


# ---------------------------------------------------------------------------
# Demographics update
# ---------------------------------------------------------------------------


class TestUpdateDemographics:
    def test_emits_updated_event(self, registered_patient: Patient) -> None:
        registered_patient.pull_domain_events()  # drain registration event
        registered_patient.update_demographics(
            family_name=PersonName(given="Tendai", family="Chigumba").family,
            updated_by="doctor-sub-001",
        )
        events = registered_patient.peek_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], DemographicsUpdated)

    def test_no_op_when_nothing_changes(self, registered_patient: Patient) -> None:
        registered_patient.pull_domain_events()
        registered_patient.update_demographics(updated_by="recep-sub-001")
        assert not registered_patient.has_pending_events()

    def test_clears_email(self, registered_patient: Patient) -> None:
        # Patient has email but no phone — clearing email would break invariant
        with pytest.raises(InvariantViolation, match="contact"):
            registered_patient.update_demographics(
                clear_email=True, updated_by="recep-sub-001"
            )

    def test_address_is_set(self, registered_patient: Patient) -> None:
        registered_patient.pull_domain_events()
        addr = Address(street="12 Borrowdale Rd", city="Harare", province="Harare")
        registered_patient.update_demographics(
            address=addr, updated_by="recep-sub-001"
        )
        assert registered_patient.address == addr

    def test_version_bump_on_event_reflects_pending_count(
        self, registered_patient: Patient
    ) -> None:
        registered_patient.pull_domain_events()
        registered_patient.update_demographics(
            family_name="Mutasa", updated_by="doc-sub"
        )
        event = registered_patient.peek_domain_events()[0]
        # version=0 (never committed), 0 pending before record → next=1
        assert event.aggregate_version == 1


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------


class TestConsent:
    def test_grant_consent_emits_event(
        self, registered_patient: Patient, frozen_clock: FrozenClock
    ) -> None:
        registered_patient.pull_domain_events()
        registered_patient.grant_consent(
            purpose=ConsentPurpose.TREATMENT,
            granted_by="recep-sub-001",
            clock=frozen_clock,
        )
        events = registered_patient.peek_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], ConsentGranted)

    def test_grant_is_idempotent(
        self, registered_patient: Patient, frozen_clock: FrozenClock
    ) -> None:
        registered_patient.grant_consent(
            purpose=ConsentPurpose.TREATMENT,
            granted_by="recep-sub-001",
            clock=frozen_clock,
        )
        registered_patient.pull_domain_events()
        # Second grant on an already-active consent: no event
        registered_patient.grant_consent(
            purpose=ConsentPurpose.TREATMENT,
            granted_by="recep-sub-001",
            clock=frozen_clock,
        )
        assert not registered_patient.has_pending_events()

    def test_revoke_consent(
        self, registered_patient: Patient, frozen_clock: FrozenClock
    ) -> None:
        registered_patient.grant_consent(
            purpose=ConsentPurpose.RESEARCH,
            granted_by="recep-sub-001",
            clock=frozen_clock,
        )
        registered_patient.pull_domain_events()
        registered_patient.revoke_consent(
            purpose=ConsentPurpose.RESEARCH,
            revoked_by="recep-sub-001",
            clock=frozen_clock,
        )
        events = registered_patient.peek_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], ConsentRevoked)
        assert not registered_patient.has_active_consent(ConsentPurpose.RESEARCH)

    def test_revoke_non_existent_consent_raises(
        self, registered_patient: Patient, frozen_clock: FrozenClock
    ) -> None:
        with pytest.raises(PreconditionFailed, match="no active consent"):
            registered_patient.revoke_consent(
                purpose=ConsentPurpose.MARKETING,
                revoked_by="recep-sub-001",
                clock=frozen_clock,
            )

    def test_re_grant_after_revoke(
        self, registered_patient: Patient, frozen_clock: FrozenClock
    ) -> None:
        registered_patient.grant_consent(
            purpose=ConsentPurpose.RESEARCH,
            granted_by="recep-001",
            clock=frozen_clock,
        )
        registered_patient.revoke_consent(
            purpose=ConsentPurpose.RESEARCH,
            revoked_by="recep-001",
            clock=frozen_clock,
        )
        # Re-grant after revocation must succeed
        registered_patient.grant_consent(
            purpose=ConsentPurpose.RESEARCH,
            granted_by="recep-001",
            clock=frozen_clock,
        )
        assert registered_patient.has_active_consent(ConsentPurpose.RESEARCH)

    def test_consent_event_versioning_within_same_transaction(
        self, registered_patient: Patient, frozen_clock: FrozenClock
    ) -> None:
        registered_patient.pull_domain_events()
        registered_patient.grant_consent(
            purpose=ConsentPurpose.TREATMENT,
            granted_by="recep-001",
            clock=frozen_clock,
        )
        registered_patient.grant_consent(
            purpose=ConsentPurpose.BILLING,
            granted_by="recep-001",
            clock=frozen_clock,
        )
        events = registered_patient.peek_domain_events()
        assert len(events) == 2
        # Versions are consecutive even before the UoW commits.
        assert events[0].aggregate_version == 1
        assert events[1].aggregate_version == 2


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


class TestDateOfBirth:
    def test_rejects_future_date(self) -> None:
        future = datetime.now(UTC).date() + timedelta(days=1)
        with pytest.raises(ValueError, match="future"):
            DateOfBirth(value=future)

    def test_rejects_implausible_date(self) -> None:
        with pytest.raises(ValueError, match="implausible"):
            DateOfBirth(value=date(1800, 1, 1))

    def test_age_calculation(self) -> None:
        dob = DateOfBirth(value=date(2000, 1, 1))
        assert dob.age_in_years(as_of=date(2026, 1, 1)) == 26
        assert dob.age_in_years(as_of=date(2025, 12, 31)) == 25


class TestZimbabweanNationalId:
    def test_canonical_format(self) -> None:
        nid = ZimbabweanNationalId(value="63-1234567A-21")
        assert nid.value == "63-1234567A-21"
        assert nid.district_code == "63"
        assert nid.province_code == "21"

    def test_normalises_spaces(self) -> None:
        nid = ZimbabweanNationalId(value="63 123456A 21")
        assert nid.value == "63-123456A-21"

    def test_rejects_invalid(self) -> None:
        with pytest.raises(ValueError, match="invalid Zimbabwean"):
            ZimbabweanNationalId(value="INVALID")
