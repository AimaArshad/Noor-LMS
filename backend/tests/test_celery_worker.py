"""Unit tests for the Celery worker: celery_app config, dispatch helper, tasks.

No broker is required: tests call task functions directly or patch send_task.

Covers:
- celery_app configuration (serializer, acks_late, prefetch)
- system.ping task returns "pong" (called directly, no broker)
- dispatch.enqueue returns a task id on success (patched send_task)
- dispatch.enqueue returns None and does NOT raise when the broker is unreachable
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# Env setup before any app import
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-1234567890")


# ---------------------------------------------------------------------------
# celery_app config
# ---------------------------------------------------------------------------

class TestCeleryAppConfig:
    def test_json_serializer(self) -> None:
        from app.worker.celery_app import celery_app

        assert celery_app.conf.task_serializer == "json"
        assert "json" in celery_app.conf.accept_content

    def test_acks_late(self) -> None:
        from app.worker.celery_app import celery_app

        assert celery_app.conf.task_acks_late is True

    def test_prefetch_one(self) -> None:
        from app.worker.celery_app import celery_app

        assert celery_app.conf.worker_prefetch_multiplier == 1

    def test_time_limits(self) -> None:
        from app.worker.celery_app import celery_app

        assert celery_app.conf.task_soft_time_limit > 0
        assert celery_app.conf.task_time_limit > celery_app.conf.task_soft_time_limit

    def test_registered_tasks_include_system_ping(self) -> None:
        """system.ping must be registered after the tasks module is imported."""
        from app.worker.celery_app import celery_app
        import app.worker.tasks.system  # noqa: F401 — registers the task

        assert "system.ping" in celery_app.tasks


# ---------------------------------------------------------------------------
# system.ping task — called directly (no broker)
# ---------------------------------------------------------------------------

class TestSystemPingTask:
    def test_ping_callable_directly(self) -> None:
        from app.worker.tasks.system import ping

        assert ping() == "pong"

    def test_ping_via_apply(self) -> None:
        """apply() runs the task synchronously in-process without a broker."""
        from app.worker.tasks.system import ping

        result = ping.apply()
        assert result.get() == "pong"


# ---------------------------------------------------------------------------
# dispatch.enqueue
# ---------------------------------------------------------------------------

class TestDispatchEnqueue:
    def test_enqueue_returns_task_id_on_success(self) -> None:
        """When send_task succeeds, enqueue returns the task id string."""
        fake_result = MagicMock()
        fake_result.id = "fake-uuid-1234"

        with patch("app.worker.dispatch.celery_app.send_task", return_value=fake_result):
            from app.worker.dispatch import enqueue

            task_id = enqueue("system.ping")

        assert task_id == "fake-uuid-1234"

    def test_enqueue_returns_none_when_broker_unreachable(self) -> None:
        """enqueue must NOT raise even when send_task throws."""
        from app.worker.dispatch import enqueue

        with patch("app.worker.dispatch.celery_app.send_task", side_effect=Exception("no broker")):
            result = enqueue("system.ping")

        assert result is None

    def test_enqueue_logs_warning_on_error(self, caplog) -> None:
        import logging

        from app.worker.dispatch import enqueue

        with patch("app.worker.dispatch.celery_app.send_task", side_effect=OSError("refused")):
            with caplog.at_level(logging.WARNING, logger="educonnect.worker"):
                enqueue("system.ping")

        assert any("system.ping" in r.message for r in caplog.records)
