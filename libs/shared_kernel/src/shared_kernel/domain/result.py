"""A lightweight ``Result`` type for handler return values.

Command handlers frequently have two failure modes: domain-level rejection
(e.g. invariant violation) and infrastructure-level failure (e.g. the DB is
down). The latter always becomes an exception; the former is sometimes
better modelled as a typed value so callers can pattern-match rather than
try/except.

Keep this minimal — we are not trying to reinvent ``returns`` or Rust's
``Result``, just to have a single conventional helper used consistently
across handlers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeAlias, TypeVar, Union

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    """Successful result wrapping a value."""

    value: T


@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    """Failure result wrapping an error (usually a domain exception subtype)."""

    error: E


Result: TypeAlias = Union[Ok[T], Err[E]]
"""Alias: ``Result[T, E]`` is ``Ok[T] | Err[E]``."""
