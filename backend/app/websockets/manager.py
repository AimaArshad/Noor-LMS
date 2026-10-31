"""In-process registry of open WebSocket connections (user id -> set of sockets)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("educonnect.ws")

#: A client that cannot take a message within this time is dropped.
SEND_TIMEOUT_SECONDS = 5.0


class ConnectionManager:
    """Tracks the *accepted* sockets of every connected user.

    The registry lives in this process only. With several uvicorn workers a message
    pushed in worker A does not reach sockets held by worker B; add Redis pub/sub in
    ``notifier.push_notification`` before scaling out.
    """

    def __init__(self, max_per_user: int = 5) -> None:
        self.max_per_user = max_per_user
        self._connections: dict[uuid.UUID, set[WebSocket]] = {}

    # ------------------------------------------------------------------ #
    def register(self, user_id: uuid.UUID, websocket: WebSocket) -> bool:
        """Add an accepted socket. Returns ``False`` when the user is at the connection limit."""
        sockets = self._connections.setdefault(user_id, set())
        if websocket in sockets:
            return True
        if len(sockets) >= self.max_per_user:
            if not sockets:
                del self._connections[user_id]
            return False
        sockets.add(websocket)
        return True

    def unregister(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        """Remove a socket (safe to call twice)."""
        sockets = self._connections.get(user_id)
        if sockets is None:
            return
        sockets.discard(websocket)
        if not sockets:
            del self._connections[user_id]

    def connection_count(self, user_id: uuid.UUID | None = None) -> int:
        """Open sockets of one user, or of everybody when ``user_id`` is ``None``."""
        if user_id is not None:
            return len(self._connections.get(user_id, ()))
        return sum(len(s) for s in self._connections.values())

    # ------------------------------------------------------------------ #
    async def send_to_user(self, user_id: uuid.UUID, message: dict[str, Any]) -> int:
        """Send a JSON message to every socket of ``user_id``; return how many received it.

        Sockets that fail or time out are removed and closed.
        """
        sockets = list(self._connections.get(user_id, ()))  # copy: we mutate while iterating
        if not sockets:
            return 0
        results = await asyncio.gather(*(self._send(ws, message) for ws in sockets))
        delivered = 0
        for websocket, ok in zip(sockets, results, strict=True):
            if ok:
                delivered += 1
            else:
                self.unregister(user_id, websocket)
                await self._close_quietly(websocket, 1011)
        return delivered

    async def close_all(self, code: int = 1001) -> None:
        """Close every socket (application shutdown)."""
        sockets = [ws for group in self._connections.values() for ws in group]
        self._connections.clear()
        await asyncio.gather(*(self._close_quietly(ws, code) for ws in sockets))

    # ------------------------------------------------------------------ #
    @staticmethod
    async def _send(websocket: WebSocket, message: dict[str, Any]) -> bool:
        try:
            await asyncio.wait_for(websocket.send_json(message), SEND_TIMEOUT_SECONDS)
        except Exception:  # noqa: BLE001 - any failure means the socket is unusable
            logger.debug("WebSocket send failed", exc_info=True)
            return False
        return True

    @staticmethod
    async def _close_quietly(websocket: WebSocket, code: int) -> None:
        try:
            await asyncio.wait_for(websocket.close(code=code), 2.0)
        except Exception:  # noqa: BLE001
            pass


#: Process-wide instance.
manager = ConnectionManager()