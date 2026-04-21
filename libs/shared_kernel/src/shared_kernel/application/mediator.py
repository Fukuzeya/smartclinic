"""A minimal in-process mediator with a middleware pipeline.

Why not use ``dependency-injector`` or a third-party mediator library?
Because the mediator is trivial and letting it live here keeps the surface
small and auditable — a reviewer can read the whole implementation in one
sitting.

The middleware pipeline is the Onion: each middleware wraps ``call_next``.
Standard middlewares provided by infrastructure:

* :class:`shared_kernel.infrastructure.tracing.TracingMiddleware`
* :class:`shared_kernel.infrastructure.logging.LoggingMiddleware`
* :class:`shared_kernel.infrastructure.metrics.MetricsMiddleware`

Services compose their own authorisation / UoW middlewares on top.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Generic, TypeVar

from shared_kernel.application.command import (
    AnyCommandHandler,
    Command,
    CommandHandler,
)
from shared_kernel.application.query import AnyQueryHandler, Query, QueryHandler

TMessage = TypeVar("TMessage", bound=Command | Query)
TResult = TypeVar("TResult")

# A middleware takes the message and the next-handler callable, and returns
# whatever the chain returns. Middlewares are composed left-to-right.
NextCall = Callable[[Any], Awaitable[Any]]
Middleware = Callable[[Any, NextCall], Awaitable[Any]]


class Mediator:
    """Dispatch commands and queries to their registered handlers.

    Registration happens via direct API calls or the :func:`handles`
    decorator. Handlers are resolved by *exact* type match — no MRO walking
    — so overloads and subclassing don't surprise anyone.
    """

    def __init__(self, middlewares: list[Middleware] | None = None) -> None:
        self._command_handlers: dict[type[Command], AnyCommandHandler] = {}
        self._query_handlers: dict[type[Query], AnyQueryHandler] = {}
        self._middlewares: list[Middleware] = list(middlewares or [])

    # -------------------------------------------------------- registration

    def register_command(
        self,
        command_type: type[Command],
        handler: AnyCommandHandler,
    ) -> None:
        if command_type in self._command_handlers:
            raise ValueError(f"duplicate command handler for {command_type.__name__}")
        self._command_handlers[command_type] = handler

    def register_query(
        self,
        query_type: type[Query],
        handler: AnyQueryHandler,
    ) -> None:
        if query_type in self._query_handlers:
            raise ValueError(f"duplicate query handler for {query_type.__name__}")
        self._query_handlers[query_type] = handler

    def use(self, middleware: Middleware) -> None:
        """Append a middleware to the pipeline (outermost added last)."""
        self._middlewares.append(middleware)

    # -------------------------------------------------------- dispatch

    async def send(self, message: Command | Query) -> Any:
        """Dispatch a command or query through the middleware pipeline."""
        if isinstance(message, Command):
            handler = self._command_handlers.get(type(message))
            kind = "command"
        elif isinstance(message, Query):
            handler = self._query_handlers.get(type(message))
            kind = "query"
        else:
            raise TypeError(f"unsupported message type: {type(message).__name__}")

        if handler is None:
            raise LookupError(
                f"no {kind} handler registered for {type(message).__name__}"
            )

        async def terminal(msg: Any) -> Any:
            return await handler(msg)

        # Compose middlewares from last-to-first so the first-added is outermost.
        chain: NextCall = terminal
        for mw in reversed(self._middlewares):
            chain = _bind(mw, chain)

        return await chain(message)


def _bind(mw: Middleware, next_call: NextCall) -> NextCall:
    async def wrapped(msg: Any) -> Any:
        return await mw(msg, next_call)

    return wrapped


# ---------------------------------------------------------------- decorator

class _Registration(Generic[TMessage, TResult]):
    """Holds a ``(message_type, handler)`` tuple yielded by ``@handles(...)``.

    Infrastructure code (``app_factory`` or a service's ``register_handlers``
    function) collects these and feeds them into the mediator. Keeping the
    indirection means handlers are decoupled from a particular mediator
    instance — important for tests.
    """

    __slots__ = ("message_type", "handler", "kind")

    def __init__(
        self,
        message_type: type[TMessage],
        handler: Callable[[TMessage], Awaitable[TResult]],
    ) -> None:
        self.message_type = message_type
        self.handler = handler
        self.kind: str = "command" if issubclass(message_type, Command) else "query"


def handles(
    message_type: type[TMessage],
) -> Callable[
    [Callable[[TMessage], Awaitable[TResult]]],
    _Registration[TMessage, TResult],
]:
    """Decorator: mark a function as the handler for ``message_type``.

    Usage::

        @handles(BookAppointment)
        async def book(cmd: BookAppointment) -> AppointmentId: ...
    """

    def wrap(
        fn: Callable[[TMessage], Awaitable[TResult]],
    ) -> _Registration[TMessage, TResult]:
        if not (issubclass(message_type, Command) or issubclass(message_type, Query)):
            raise TypeError("@handles(...) requires a Command or Query subclass")
        return _Registration(message_type, fn)

    return wrap


def bind_registrations(
    mediator: Mediator,
    registrations: list[_Registration[Any, Any]],
) -> None:
    """Register every decorated handler into the mediator."""
    for reg in registrations:
        if reg.kind == "command":
            mediator.register_command(reg.message_type, reg.handler)  # type: ignore[arg-type]
        else:
            mediator.register_query(reg.message_type, reg.handler)  # type: ignore[arg-type]
