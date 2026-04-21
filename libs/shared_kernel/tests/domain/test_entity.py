"""Unit tests for ``Entity``."""

from __future__ import annotations

import uuid

import pytest

from shared_kernel.domain import Entity


class _Patient(Entity[uuid.UUID]):
    pass


class _Doctor(Entity[uuid.UUID]):
    pass


def test_entity_requires_identity() -> None:
    with pytest.raises(ValueError):
        _Patient(id=None)  # type: ignore[arg-type]


def test_entity_equality_is_identity_and_type_based() -> None:
    same = uuid.uuid4()
    p1 = _Patient(id=same)
    p2 = _Patient(id=same)
    assert p1 == p2
    assert hash(p1) == hash(p2)


def test_entity_of_different_subclass_is_never_equal() -> None:
    same = uuid.uuid4()
    assert _Patient(id=same) != _Doctor(id=same)


def test_entity_equality_ignores_attribute_values() -> None:
    # Even with different "state" the identity wins — that's the whole point.
    a = _Patient(id=uuid.uuid4())
    b = _Patient(id=a.id)
    assert a == b
