"""``push_notification``: the helper services use to reach live sockets."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.websockets.manager import manager

logger = logging.getLogger("educonnect.ws")


async def push_notification(user_id: uuid.UUID, payload: dict[str, Any]) -> int:
    """Push ``payload`` to all open sockets of ``user_id``.

    The client receives ``{"type": "notification", "data": payload}``. ``payload`` must be
    JSON-serialisable (use ``NotificationRead(...).model_dump(mode="json")``).

    Best-effort: never raises. Returns the number of sockets that received it.

    Services should not call this before committing. Use
    :func:`app.services.notification_service.stage_notification`, which pushes after
    the commit succeeded.
    """
    try:
        return await manager.send_to_user(user_id, {"type": "notification", "data": payload})
    except Exception:  # noqa: BLE001
        logger.exception("push_notification failed for user %s", user_id)
        return 0