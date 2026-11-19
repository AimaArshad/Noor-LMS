"""``dispatch.enqueue`` — fire-and-forget helper for enqueueing Celery tasks.

Design
------
A missing or unreachable broker must **never** crash a request handler.
``enqueue()`` catches all exceptions from the Celery ``apply_async`` call,
logs them at WARNING level, and returns ``None`` instead of raising.

Usage::

    from app.worker.dispatch import enqueue

    enqueue("system.ping")                       # positional args
    enqueue("some.task", user_id, payload=data)  # kwargs too
"""

from __future__ import annotations

import logging
from typing import Any

from app.worker.celery_app import celery_app

logger = logging.getLogger("educonnect.worker")


def enqueue(task_name: str, *args: Any, **kwargs: Any) -> str | None:
    """Send a task to the Celery broker.

    Returns the task id (a UUID string) on success, or ``None`` when the
    broker is unavailable or any other error occurs.  **Never raises.**

    Args:
        task_name: Registered Celery task name, e.g. ``"system.ping"``.
        *args: Positional arguments forwarded to the task.
        **kwargs: Keyword arguments forwarded to the task.
    """
    try:
        result = celery_app.send_task(task_name, args=args, kwargs=kwargs)
        return result.id
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to enqueue task %r (broker may be unavailable): %s",
            task_name,
            exc,
        )
        return None

