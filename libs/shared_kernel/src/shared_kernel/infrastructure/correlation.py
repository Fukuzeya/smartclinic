"""Correlation-ID propagation via ``contextvars``.

When a request arrives at any service it is assigned a correlation_id
(either echoed from ``X-Correlation-Id`` or minted fresh). That id is
pushed into a contextvar so every structlog record, OTel span, and outbox
event emitted during the request carries it — giving us end-to-end
traceability across service boundaries.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_causation_id: ContextVar[str | None] = ContextVar("causation_id", default=None)


def new_correlation_id() -> str:
    """Mint a fresh correlation id. Prefer v4 here (not v7) — no time leak."""
    return str(uuid.uuid4())


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def set_correlation_id(value: str | None) -> None:
    _correlation_id.set(value)


def get_causation_id() -> str | None:
    return _causation_id.get()


def set_causation_id(value: str | None) -> None:
    _causation_id.set(value)


class correlation_scope:  # noqa: N801 — intentional lowercase context-manager name
    """Temporarily bind a correlation id to the current async context."""

    __slots__ = ("_token", "_value")

    def __init__(self, value: str | None = None) -> None:
        self._value = value or new_correlation_id()
        self._token: object | None = None

    def __enter__(self) -> str:
        self._token = _correlation_id.set(self._value)
        return self._value

    def __exit__(self, *_: object) -> None:
        if self._token is not None:
            _correlation_id.reset(self._token)  # type: ignore[arg-type]
