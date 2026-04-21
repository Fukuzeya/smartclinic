"""Domain exception hierarchy.

These are the only exceptions that should ever cross the domain→application
boundary. Infrastructure-level errors (connection failures, timeouts) are
translated here or in the application layer — domain code must never catch
or raise infrastructure-specific exceptions.

Mapping to HTTP is done centrally in
``shared_kernel.fastapi.exception_handlers``.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for every domain-defined error.

    Subclasses are deliberately narrow: a reviewer should be able to tell
    from the type alone which HTTP status the handler will emit and whether
    the failure was caller-induced or a concurrent-state conflict.
    """

    default_code: str = "domain_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class InvariantViolation(DomainError):
    """An aggregate's invariant would be broken by the requested change.

    Example: attempting to issue a prescription on an Encounter that has no
    recorded diagnosis violates the Clinical context's invariant that
    ``diagnosis_count >= 1 BEFORE prescription_count >= 1``.
    """

    default_code = "invariant_violation"


class NotFound(DomainError):
    """A referenced aggregate or entity does not exist."""

    default_code = "not_found"


class ConcurrencyConflict(DomainError):
    """Optimistic-concurrency conflict detected on aggregate save.

    Raised by repositories when the aggregate's ``version`` has been
    incremented by a competing writer since it was loaded. Callers should
    retry by reloading the aggregate.
    """

    default_code = "concurrency_conflict"


class Forbidden(DomainError):
    """The caller is not permitted to perform this operation on this aggregate.

    This is a *domain-level* authorisation failure (e.g. a nurse attempting
    to finalise a diagnosis), distinct from coarse route-level RBAC.
    """

    default_code = "forbidden"


class PreconditionFailed(DomainError):
    """A temporal or state precondition is not met for the operation.

    Example: trying to dispense a prescription before the doctor has
    finalised the encounter.
    """

    default_code = "precondition_failed"
