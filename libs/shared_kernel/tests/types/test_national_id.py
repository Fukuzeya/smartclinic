"""Unit tests for ``ZimbabweanNationalId``."""

from __future__ import annotations

import pytest

from shared_kernel.types import ZimbabweanNationalId


@pytest.mark.parametrize(
    "raw, canonical",
    [
        ("63-1234567A63", "63-1234567A-63"),
        ("63 1234567 A 63", "63-1234567A-63"),
        ("63-1234567-A-63", "63-1234567A-63"),
        ("08-123456-Z-32", "08-123456Z-32"),
    ],
)
def test_canonicalises_various_forms(raw: str, canonical: str) -> None:
    assert ZimbabweanNationalId(value=raw).value == canonical


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "63-123-A-63",            # core too short
        "63-1234567-AB-63",       # check letter too long
        "abc",
        "63-1234567A-6",          # province too short
    ],
)
def test_rejects_invalid_forms(raw: str) -> None:
    with pytest.raises(ValueError):
        ZimbabweanNationalId(value=raw)


def test_exposes_district_and_province() -> None:
    nid = ZimbabweanNationalId(value="63-1234567A63")
    assert nid.district_code == "63"
    assert nid.province_code == "63"
