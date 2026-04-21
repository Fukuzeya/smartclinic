"""Domain-layer building blocks — no infrastructure dependencies allowed.

If a module in this package ever imports from ``shared_kernel.infrastructure``
or ``shared_kernel.fastapi``, the architectural fitness-function test will
fail the CI build (see ``tests/fitness/test_architecture.py``).
"""

from shared_kernel.domain.aggregate_root import AggregateRoot
from shared_kernel.domain.domain_event import DomainEvent
from shared_kernel.domain.entity import Entity
from shared_kernel.domain.exceptions import (
    ConcurrencyConflict,
    DomainError,
    Forbidden,
    InvariantViolation,
    NotFound,
)
from shared_kernel.domain.repository import Repository
from shared_kernel.domain.result import Err, Ok, Result
from shared_kernel.domain.specification import (
    AndSpecification,
    NotSpecification,
    OrSpecification,
    Specification,
    SpecificationViolation,
)
from shared_kernel.domain.value_object import ValueObject

__all__ = [
    "AggregateRoot",
    "AndSpecification",
    "ConcurrencyConflict",
    "DomainError",
    "DomainEvent",
    "Entity",
    "Err",
    "Forbidden",
    "InvariantViolation",
    "NotFound",
    "NotSpecification",
    "Ok",
    "OrSpecification",
    "Repository",
    "Result",
    "Specification",
    "SpecificationViolation",
    "ValueObject",
]
