"""Query / QueryHandler primitives.

A **Query** expresses an *intent to read* — it never mutates state, is safe
to retry, and its handler targets the *read model*, not the write-side
aggregates (this is the whole point of CQRS; see ADR 0004).
"""

from __future__ import annotations

from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict


class Query(BaseModel):
    """Marker base for queries."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        populate_by_name=True,
    )


TQuery = TypeVar("TQuery", bound=Query)
TResult = TypeVar("TResult")


@runtime_checkable
class QueryHandler(Protocol[TQuery, TResult]):
    """Async handler for a single query type."""

    async def __call__(self, query: TQuery) -> TResult: ...


AnyQueryHandler = QueryHandler[Any, Any]
