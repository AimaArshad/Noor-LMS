"""System / health tasks.

``system.ping``
    Trivial no-op task used to verify that the broker and worker are
    reachable.  Returns the string ``"pong"``.

    Example::

        from app.worker.dispatch import enqueue
        enqueue("system.ping")
"""

from __future__ import annotations

from app.worker.celery_app import celery_app


@celery_app.task(name="system.ping", bind=False)
def ping() -> str:
    """Return 'pong'.  Used to verify the broker + worker are alive."""
    return "pong"

