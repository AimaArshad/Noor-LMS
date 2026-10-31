"""WebSocket endpoint: ``/ws/notifications``.

Authentication (either way):

* ``ws://host/ws/notifications?token=<access JWT>``
* connect without a query string and send ``{"type": "auth", "token": "<JWT>"}`` as the
  first message within 5 seconds (recommended: query strings end up in access logs).

Server -> client messages::

    {"type": "connected", "unread_count": 3}
    {"type": "notification", "data": {...NotificationRead...}}
    {"type": "pong"}
    {"type": "error", "detail": "..."}

Client -> server: ``{"type": "ping"}`` every ~30 s (the server closes idle sockets after 90 s).

Close codes: 4401 unauthorized / token expired (refresh the token, then reconnect),
4408 idle timeout, 4429 too many connections for this user, 1009 message too large.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import TokenError, decode_token, parse_subject
from app.db.session import AsyncSessionLocal
from app.models import Notification, User
from app.websockets.manager import manager

logger = logging.getLogger("educonnect.ws")

router = APIRouter()

WS_UNAUTHORIZED = 4401
WS_IDLE_TIMEOUT = 4408
WS_TOO_MANY = 4429

AUTH_TIMEOUT_SECONDS = 5.0
IDLE_TIMEOUT_SECONDS = 90.0
MAX_MESSAGE_CHARS = 2048

SessionFactory = async_sessionmaker[AsyncSession]


def get_session_factory() -> SessionFactory:
    """Session factory dependency (overridden in tests).

    The endpoint opens a short session just to authenticate. It must NOT use ``get_db``,
    which would pin a pooled connection for the lifetime of the socket.
    """
    return AsyncSessionLocal


async def _safe_close(websocket: WebSocket, code: int, reason: str = "") -> None:
    try:
        await websocket.close(code=code, reason=reason)
    except Exception:  # noqa: BLE001 - the peer may already be gone
        pass


async def _authenticate(
    token: str, session_factory: SessionFactory
) -> tuple[uuid.UUID, int, int] | None:
    """Validate the JWT and the user. Returns ``(user_id, token_exp, unread_count)`` or ``None``."""
    try:
        payload = decode_token(token, expected_type="access")
        user_id = parse_subject(payload)
    except TokenError:
        return None
    async with session_factory() as db:
        user = await db.get(User, user_id)
        if user is None or not user.is_active:
            return None
        unread = (
            await db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            )
            or 0
        )
    return user_id, payload.exp, unread


async def _receive_auth_message(websocket: WebSocket) -> str | None:
    """First-message authentication: ``{"type": "auth", "token": "..."}``."""
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), AUTH_TIMEOUT_SECONDS)
        message = json.loads(raw)
    except (asyncio.TimeoutError, WebSocketDisconnect, ValueError, KeyError):
        return None
    if isinstance(message, dict) and message.get("type") == "auth":
        token = message.get("token")
        if isinstance(token, str):
            return token
    return None


async def _serve(websocket: WebSocket, token_exp: int) -> None:
    """Answer pings; end when the socket is idle too long or the token expires."""
    while True:
        remaining = token_exp - time.time()
        if remaining <= 0:
            await _safe_close(websocket, WS_UNAUTHORIZED, "Token expired")
            return
        try:
            raw = await asyncio.wait_for(
                websocket.receive_text(), timeout=min(IDLE_TIMEOUT_SECONDS, remaining)
            )
        except asyncio.TimeoutError:
            if token_exp - time.time() <= 0:
                await _safe_close(websocket, WS_UNAUTHORIZED, "Token expired")
            else:
                await _safe_close(websocket, WS_IDLE_TIMEOUT, "Idle timeout")
            return
        except KeyError:  # binary frame
            await _safe_close(websocket, 1003, "Text frames only")
            return

        if len(raw) > MAX_MESSAGE_CHARS:
            await _safe_close(websocket, 1009, "Message too large")
            return
        try:
            message = json.loads(raw)
        except ValueError:
            message = None
        kind = message.get("type") if isinstance(message, dict) else None
        if kind == "ping":
            await websocket.send_json({"type": "pong"})
        else:
            await websocket.send_json({"type": "error", "detail": "Unsupported message"})


@router.websocket("/ws/notifications")
async def notifications_ws(
    websocket: WebSocket,
    session_factory: Annotated[SessionFactory, Depends(get_session_factory)],
    token: Annotated[str | None, Query(description="Access JWT (or use first-message auth)")] = None,
) -> None:
    """Live notification stream for the authenticated user."""
    await websocket.accept()

    if token is None:
        token = await _receive_auth_message(websocket)
    try:
        auth = await _authenticate(token, session_factory) if token else None
    except Exception:  # noqa: BLE001 - e.g. database down
        logger.exception("WebSocket authentication failed unexpectedly")
        await _safe_close(websocket, 1011, "Server error")
        return
    if auth is None:
        await _safe_close(websocket, WS_UNAUTHORIZED, "Unauthorized")
        return

    user_id, token_exp, unread = auth
    if not manager.register(user_id, websocket):
        await _safe_close(websocket, WS_TOO_MANY, "Too many connections")
        return
    try:
        await websocket.send_json({"type": "connected", "unread_count": unread})
        await _serve(websocket, token_exp)
    except WebSocketDisconnect:
        pass
    finally:
        manager.unregister(user_id, websocket)