"""The Specification Pattern.

A ``Specification`` encapsulates a *composable* business rule — an object
answering the question "does this candidate satisfy my rule?". Two wins over
scattering ``if`` statements through services:

1. **Composability** — rules combine via ``&`` (and), ``|`` (or), ``~`` (not)
   without any prose-level glue.
2. **Explainability** — ``explain()`` yields human-readable reasons for
   failure, so the UI can surface *"cannot prescribe: warfarin + aspirin
   severe bleeding-risk interaction"* rather than a boolean.

Used heavily in the Pharmacy context for drug-drug-interaction checks and
in Scheduling for appointment-conflict detection.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Generic, TypeVar

from shared_kernel.domain.exceptions import DomainError

T = TypeVar("T")


class SpecificationViolation(DomainError):
    """Raised by ``Specification.assert_satisfied_by`` when the rule fails.

    Carries the list of violation reasons so callers can expose them to the
    UI verbatim.
    """

    default_code = "specification_violation"

    def __init__(self, reasons: Iterable[str]) -> None:
        reasons_list = list(reasons)
        message = "; ".join(reasons_list) or "specification violated"
        super().__init__(message)
        self.reasons = reasons_list


class Specification(ABC, Generic[T]):
    """Abstract base class for a composable business rule.

    Subclasses implement :meth:`is_satisfied_by`. Override
    :meth:`reasons_for_failure` when the rule has a useful explanation —
    otherwise the class name is used as a fallback.
    """

    @abstractmethod
    def is_satisfied_by(self, candidate: T) -> bool:
        """Return True iff ``candidate`` satisfies this specification."""

    def reasons_for_failure(self, candidate: T) -> list[str]:
        """Describe *why* ``candidate`` fails this spec.

        Called only when :meth:`is_satisfied_by` returns False. Default
        implementation returns the class name; override for informative
        errors.
        """
        return [f"{type(self).__name__} not satisfied"]

    def assert_satisfied_by(self, candidate: T) -> None:
        """Raise :class:`SpecificationViolation` if the rule fails.

        Intended for use inside aggregate methods:

        .. code-block:: python

            NoSevereDrugInteraction(self.current_prescriptions).assert_satisfied_by(new_rx)
        """
        if not self.is_satisfied_by(candidate):
            raise SpecificationViolation(self.reasons_for_failure(candidate))

    # ----------------------------------------------------------- composition

    def __and__(self, other: Specification[T]) -> AndSpecification[T]:
        return AndSpecification(self, other)

    def __or__(self, other: Specification[T]) -> OrSpecification[T]:
        return OrSpecification(self, other)

    def __invert__(self) -> NotSpecification[T]:
        return NotSpecification(self)


class AndSpecification(Specification[T]):
    """Logical AND of two specifications."""

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self.left.is_satisfied_by(candidate) and self.right.is_satisfied_by(candidate)

    def reasons_for_failure(self, candidate: T) -> list[str]:
        failures: list[str] = []
        if not self.left.is_satisfied_by(candidate):
            failures.extend(self.left.reasons_for_failure(candidate))
        if not self.right.is_satisfied_by(candidate):
            failures.extend(self.right.reasons_for_failure(candidate))
        return failures


class OrSpecification(Specification[T]):
    """Logical OR of two specifications."""

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self.left.is_satisfied_by(candidate) or self.right.is_satisfied_by(candidate)

    def reasons_for_failure(self, candidate: T) -> list[str]:
        return [
            *self.left.reasons_for_failure(candidate),
            *self.right.reasons_for_failure(candidate),
        ]


class NotSpecification(Specification[T]):
    """Logical NOT — inverts an inner specification."""

    def __init__(self, inner: Specification[T]) -> None:
        self.inner = inner

    def is_satisfied_by(self, candidate: T) -> bool:
        return not self.inner.is_satisfied_by(candidate)

    def reasons_for_failure(self, candidate: T) -> list[str]:
        return [f"negation of {type(self.inner).__name__} not satisfied"]
