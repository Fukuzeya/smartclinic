"""Unit tests for the in-process ``Mediator``."""

from __future__ import annotations

from typing import Any

import pytest

from shared_kernel.application import Command, Mediator, Query, handles
from shared_kernel.application.mediator import bind_registrations


class _Greet(Command):
    name: str


class _Echo(Query):
    text: str


@handles(_Greet)
async def _greet_handler(cmd: _Greet) -> str:
    return f"hello, {cmd.name}"


@handles(_Echo)
async def _echo_handler(q: _Echo) -> str:
    return q.text


@pytest.fixture
def mediator() -> Mediator:
    m = Mediator()
    bind_registrations(m, [_greet_handler, _echo_handler])
    return m


async def test_dispatches_command(mediator: Mediator) -> None:
    result = await mediator.send(_Greet(name="Shamiso"))
    assert result == "hello, Shamiso"


async def test_dispatches_query(mediator: Mediator) -> None:
    assert await mediator.send(_Echo(text="pong")) == "pong"


async def test_unknown_message_raises(mediator: Mediator) -> None:
    class _Unknown(Command):
        pass

    with pytest.raises(LookupError):
        await mediator.send(_Unknown())


async def test_middleware_runs_in_outermost_first_order() -> None:
    calls: list[str] = []

    async def mw_a(msg: Any, nxt: Any) -> Any:
        calls.append("a_in")
        result = await nxt(msg)
        calls.append("a_out")
        return result

    async def mw_b(msg: Any, nxt: Any) -> Any:
        calls.append("b_in")
        result = await nxt(msg)
        calls.append("b_out")
        return result

    m = Mediator(middlewares=[mw_a, mw_b])
    bind_registrations(m, [_greet_handler])
    await m.send(_Greet(name="x"))
    assert calls == ["a_in", "b_in", "b_out", "a_out"]


async def test_duplicate_handler_rejected() -> None:
    m = Mediator()
    bind_registrations(m, [_greet_handler])
    with pytest.raises(ValueError):
        bind_registrations(m, [_greet_handler])
