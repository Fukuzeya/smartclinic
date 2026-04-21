"""Unit tests for the Specification pattern."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from shared_kernel.domain import Specification
from shared_kernel.domain.specification import (
    AndSpecification,
    NotSpecification,
    OrSpecification,
    SpecificationViolation,
)


@dataclass
class _Patient:
    age: int
    is_pregnant: bool = False


class _AdultSpec(Specification[_Patient]):
    def is_satisfied_by(self, candidate: _Patient) -> bool:
        return candidate.age >= 18

    def reasons_for_failure(self, candidate: _Patient) -> list[str]:
        return [f"patient age {candidate.age} below adult threshold"]


class _NotPregnantSpec(Specification[_Patient]):
    def is_satisfied_by(self, candidate: _Patient) -> bool:
        return not candidate.is_pregnant

    def reasons_for_failure(self, candidate: _Patient) -> list[str]:
        return ["patient is pregnant"]


def test_simple_specification() -> None:
    assert _AdultSpec().is_satisfied_by(_Patient(age=25))
    assert not _AdultSpec().is_satisfied_by(_Patient(age=10))


def test_and_combination() -> None:
    spec = _AdultSpec() & _NotPregnantSpec()
    assert isinstance(spec, AndSpecification)
    assert spec.is_satisfied_by(_Patient(age=25, is_pregnant=False))
    assert not spec.is_satisfied_by(_Patient(age=25, is_pregnant=True))
    assert not spec.is_satisfied_by(_Patient(age=10, is_pregnant=False))


def test_or_combination() -> None:
    spec = _AdultSpec() | _NotPregnantSpec()
    assert isinstance(spec, OrSpecification)
    assert spec.is_satisfied_by(_Patient(age=10, is_pregnant=False))
    assert not spec.is_satisfied_by(_Patient(age=10, is_pregnant=True))


def test_not_combination() -> None:
    spec = ~_AdultSpec()
    assert isinstance(spec, NotSpecification)
    assert spec.is_satisfied_by(_Patient(age=10))
    assert not spec.is_satisfied_by(_Patient(age=25))


def test_assert_satisfied_raises_with_reasons() -> None:
    spec = _AdultSpec() & _NotPregnantSpec()
    with pytest.raises(SpecificationViolation) as exc:
        spec.assert_satisfied_by(_Patient(age=10, is_pregnant=True))
    reasons = exc.value.reasons
    assert any("age" in r for r in reasons)
    assert any("pregnant" in r for r in reasons)
