"""Celery application factory for EduConnect background workers.

Design decisions
----------------
* JSON serializer — no pickle: safe, human-readable, language-agnostic.
* ``acks_late=True`` — the task is acknowledged *after* it finishes; a
  worker crash re-queues the task rather than silently dropping it.
* ``worker_prefetch_multiplier=1`` — one task at a time per worker process;
  avoids head-of-line blocking when a slow task is in-flight.
* Soft + hard time limits — tasks must not run forever.
* The broker URL defaults to ``REDIS_URL`` (same Redis, different DB) so the
  dev setup requires no extra services.

Import path
-----------
Run the worker from the ``backend/`` directory::

    celery -A app.worker.celery_app worker --loglevel=info

Auto-discovery imports ``app.worker.tasks.*`` so all ``@celery_app.task``
decorated functions in that package are registered automatically.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "educonnect",
    broker=settings.CELERY_BROKER_URL,
    # Result backend is not used yet; set to None to avoid unnecessary Redis
    # round-trips.  Enable when task results are needed.
    backend=None,
    include=[
        "app.worker.tasks.system",
        "app.worker.audiobook_tasks",
    ],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Reliability
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Time limits (seconds): soft sends SIGTERM so the task can clean up;
    # hard sends SIGKILL after an additional 30 s.
    task_soft_time_limit=300,   # 5 minutes
    task_time_limit=330,        # 5 minutes + 30 s grace
    # Timezone
    timezone="UTC",
    enable_utc=True,
)

