"""Command / CommandHandler primitives.

A **Command** expresses an *intent to change* — it is named in the imperative
mood (``BookAppointment``, ``RecordDiagnosis``) and is validated at the
application boundary. Commands may return a value (typically the identifier
of a newly-created aggregate) but they must never be used to *read* state;
queries exist for that.

Commands are always executed through the :class:`Mediator` so the middleware
pipeline (logging, tracing, UoW scoping, authorisation) applies uniformly.
"""

from __future__ import annotations

from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict


class Command(BaseModel):
    """Marker base for commands.

    Inheriting from ``BaseModel`` gives free validation and a JSON schema
    for OpenAPI. Commands are mutable at rest (they are input DTOs), but we
    forbid extra fields and require strict typing to avoid silent breakage.
    """

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        populate_by_name=True,
        validate_assignment=True,
    )


TCmd = TypeVar("TCmd", bound=Command)
TResult = TypeVar("TResult")


@runtime_checkable
class CommandHandler(Protocol[TCmd, TResult]):
    """Async handler for a single command type.

    Implementations receive a fully-validated command and must return a
    typed result (or raise a ``DomainError`` on rejection). They should
    **not** commit the Unit of Work themselves — that is the mediator's
    responsibility, so a handler composed from several sub-handlers stays
    transactional end-to-end.
    """

    async def __call__(self, command: TCmd) -> TResult: ...


# Type alias so services can declare registries without importing the generic.
AnyCommandHandler = CommandHandler[Any, Any]
