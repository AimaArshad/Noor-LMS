"""Minimal in-process ASGI WebSocket client for tests.

httpx cannot speak WebSocket and Starlette's TestClient runs the app in another thread
(which clashes with the async test database), so this drives the ASGI app directly
inside the test's own event loop.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any


class WSClient:
    """``async with WSClient(app, "/ws/notifications", query="token=...") as ws: ...``"""

    def __init__(self, app: Any, path: str, *, query: str = "") -> None:  # noqa: ANN401
        self.app = app
        self.scope: dict[str, Any] = {
            "type": "websocket",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "scheme": "ws",
            "path": path,
            "raw_path": path.encode(),
            "root_path": "",
            "query_string": query.encode(),
            "headers": [(b"host", b"test")],
            "client": ("127.0.0.1", 12345),
            "server": ("test", 80),
            "subprotocols": [],
        }
        self._inbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()  # client -> app
        self._outbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()  # app -> client
        self._task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> "WSClient":
        self._inbox.put_nowait({"type": "websocket.connect"})
        self._task = asyncio.create_task(self.app(self.scope, self._inbox.get, self._outbox.put))
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        assert self._task is not None
        self._inbox.put_nowait({"type": "websocket.disconnect", "code": 1000})
        try:
            await asyncio.wait_for(self._task, timeout=3)  # re-raises endpoint errors
        except asyncio.TimeoutError:
            self._task.cancel()
            raise AssertionError("the WebSocket endpoint did not finish after disconnect") from None

    async def event(self, timeout: float = 3.0) -> dict[str, Any]:
        """Next raw ASGI event sent by the app (accept / send / close)."""
        return await asyncio.wait_for(self._outbox.get(), timeout)

    async def accepted(self) -> None:
        event = await self.event()
        assert event["type"] == "websocket.accept", event

    async def receive_json(self, timeout: float = 3.0) -> dict[str, Any]:
        event = await self.event(timeout)
        assert event["type"] == "websocket.send", event
        return json.loads(event["text"])

    async def closed(self, timeout: float = 3.0) -> int:
        """Wait for the server to close the socket; return the close code."""
        event = await self.event(timeout)
        assert event["type"] == "websocket.close", event
        return int(event["code"])

    def send_json(self, data: Any) -> None:  # noqa: ANN401
        self._inbox.put_nowait({"type": "websocket.receive", "text": json.dumps(data)})

    def send_text(self, text: str) -> None:
        self._inbox.put_nowait({"type": "websocket.receive", "text": text})