"""Unit tests for ``Email`` and ``PhoneNumber``."""

from __future__ import annotations

import pytest

from shared_kernel.types import Email, PhoneNumber


def test_email_validates_rfc() -> None:
    assert Email.of("doctor@clinic.co.zw").value == "doctor@clinic.co.zw"


def test_email_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        Email.of("not-an-email")


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("0771234567", "+263771234567"),
        ("+263 77-123 4567", "+263771234567"),
        ("263771234567", "+263771234567"),
        ("00263771234567", "+263771234567"),
    ],
)
def test_phone_normalises_to_e164(raw: str, expected: str) -> None:
    assert PhoneNumber(value=raw).value == expected


def test_phone_rejects_malformed() -> None:
    with pytest.raises(ValueError):
        PhoneNumber(value="abc")


def test_phone_country_code_parts() -> None:
    p = PhoneNumber(value="+263771234567")
    assert p.country_code == "263"
    assert p.national_number == "771234567"
