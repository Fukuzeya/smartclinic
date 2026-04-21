"""Unit tests for typed identifiers."""

from __future__ import annotations

import uuid

import pytest

from shared_kernel.types import DoctorId, EncounterId, PatientId, new_uuid7


def test_uuid7_is_well_formed_and_time_ordered() -> None:
    a = new_uuid7()
    b = new_uuid7()
    assert a.version == 7
    assert b.version == 7
    assert a != b
    assert a.int < b.int, "UUIDv7 must be monotonically increasing"


def test_identifier_new_mints_unique_id() -> None:
    assert PatientId.new() != PatientId.new()


def test_identifier_equality_is_strict_by_type() -> None:
    same = new_uuid7()
    # PatientId and DoctorId both wrap a UUID but must never be equal.
    assert PatientId(value=same) != DoctorId(value=same)


def test_identifier_parse_round_trips() -> None:
    original = PatientId.new()
    parsed = PatientId.parse(str(original.value))
    assert parsed == original


def test_identifier_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        PatientId.parse("not-a-uuid")


def test_identifier_repr_is_prefixed() -> None:
    pid = PatientId(value=uuid.UUID("00000000-0000-7000-8000-000000000000"))
    assert str(pid).startswith("pat_")
    did = DoctorId(value=uuid.UUID("00000000-0000-7000-8000-000000000000"))
    assert str(did).startswith("doc_")


def test_encounter_id_is_its_own_type() -> None:
    eid = EncounterId.new()
    assert str(eid).startswith("enc_")
