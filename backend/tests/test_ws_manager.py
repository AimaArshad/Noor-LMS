"""Unit tests for the ConnectionManager (no database needed)."""

import uuid
from typing import Any

import pytest

from app.websockets.manager import ConnectionManager

pytestmark = pytest.mark.asyncio


class FakeWS:
    """Duck-typed stand-in for a Starlette WebSocket."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[dict[str, Any]] = []
        self.closed_with: int | None = None

    async def send_json(self, data: dict[str, Any]) -> None:
        if self.fail:
            raise RuntimeError("broken pipe")
        self.sent.append(data)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.closed_with = code


async def test_register_send_unregister() -> None:
    manager = ConnectionManager()
    alice, bob = uuid.uuid4(), uuid.uuid4()
    a1, a2, b1 = FakeWS(), FakeWS(), FakeWS()
    for uid, ws in ((alice, a1), (alice, a2), (bob, b1)):
        assert manager.register(uid, ws)  # type: ignore[arg-type]
    assert manager.connection_count(alice) == 2 and manager.connection_count() == 3

    assert await manager.send_to_user(alice, {"hello": 1}) == 2
    assert a1.sent == a2.sent == [{"hello": 1}] and b1.sent == []
    assert await manager.send_to_user(uuid.uuid4(), {"x": 1}) == 0  # nobody connected

    manager.unregister(alice, a1)  # type: ignore[arg-type]
    manager.unregister(alice, a1)  # idempotent  # type: ignore[arg-type]
    assert manager.connection_count(alice) == 1
    manager.unregister(alice, a2)  # type: ignore[arg-type]
    assert manager.connection_count(alice) == 0 and manager.connection_count() == 1


async def test_connection_limit_per_user() -> None:
    manager = ConnectionManager(max_per_user=2)
    uid = uuid.uuid4()
    first, second, third = FakeWS(), FakeWS(), FakeWS()
    assert manager.register(uid, first) and manager.register(uid, second)  # type: ignore[arg-type]
    assert manager.register(uid, first)  # same socket again: no-op  # type: ignore[arg-type]
    assert not manager.register(uid, third)  # type: ignore[arg-type]
    assert manager.register(uuid.uuid4(), third)  # limits are per user  # type: ignore[arg-type]


async def test_dead_sockets_are_dropped_and_closed() -> None:
    manager = ConnectionManager()
    uid = uuid.uuid4()
    good, bad = FakeWS(), FakeWS(fail=True)
    manager.register(uid, good)  # type: ignore[arg-type]
    manager.register(uid, bad)  # type: ignore[arg-type]

    assert await manager.send_to_user(uid, {"n": 1}) == 1
    assert manager.connection_count(uid) == 1 and bad.closed_with == 1011
    assert good.sent == [{"n": 1}]


async def test_close_all() -> None:
    manager = ConnectionManager()
    sockets = [FakeWS(), FakeWS()]
    for ws in sockets:
        manager.register(uuid.uuid4(), ws)  # type: ignore[arg-type]
    await manager.close_all()
    assert manager.connection_count() == 0 and all(ws.closed_with == 1001 for ws in sockets)