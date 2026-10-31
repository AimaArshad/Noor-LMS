"""Integration tests for /notifications and the post-commit push (needs the PostgreSQL test DB)."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from httpx import AsyncClient

from app.models import Notification
from app.services.notification_service import stage_notification
from app.websockets.manager import manager
from tests.helpers import API, classroom_context, make_user, user_id
from tests.test_ws_manager import FakeWS

pytestmark = pytest.mark.asyncio

NOTES = f"{API}/notifications"
BASE_TIME = datetime(2030, 1, 1, tzinfo=timezone.utc)


async def seed(session_maker: Any, uid: uuid.UUID, count: int, *, read: int = 0, prefix: str = "N") -> None:  # noqa: ANN401
    """``count`` notifications titled ``{prefix}0..``; the first ``read`` are already read."""
    async with session_maker() as s:
        for i in range(count):
            s.add(
                Notification(
                    user_id=uid,
                    title=f"{prefix}{i}",
                    type="general",
                    is_read=i < read,
                    created_at=BASE_TIME + timedelta(seconds=i),
                )
            )
        await s.commit()


async def two_users(client: AsyncClient, session_maker: Any) -> dict[str, Any]:  # noqa: ANN401
    sam = await make_user(client, "sam@example.com")
    cleo = await make_user(client, "cleo@example.com")
    sam_id, cleo_id = await user_id(client, sam), await user_id(client, cleo)
    await seed(session_maker, sam_id, 5, read=2)  # N0, N1 read; N2..N4 unread
    await seed(session_maker, cleo_id, 3, prefix="C")
    return {"sam": sam, "cleo": cleo, "sam_id": sam_id, "cleo_id": cleo_id}


# --------------------------------------------------------------------- list
async def test_list_is_private_ordered_and_filterable(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    u = await two_users(client, session_maker)

    data = (await client.get(NOTES, headers=u["sam"])).json()
    assert [n["title"] for n in data["items"]] == ["N4", "N3", "N2", "N1", "N0"]
    assert data["total"] == 5 and data["unread_count"] == 3 and data["limit"] == 20

    unread = (await client.get(NOTES, params={"unread_only": True}, headers=u["sam"])).json()
    assert [n["title"] for n in unread["items"]] == ["N4", "N3", "N2"]
    assert unread["total"] == 3 and unread["unread_count"] == 3

    page = (await client.get(NOTES, params={"limit": 2, "offset": 1}, headers=u["sam"])).json()
    assert [n["title"] for n in page["items"]] == ["N3", "N2"]

    cleo = (await client.get(NOTES, headers=u["cleo"])).json()
    assert [n["title"] for n in cleo["items"]] == ["C2", "C1", "C0"]  # only her own

    assert (await client.get(NOTES, params={"limit": 0}, headers=u["sam"])).status_code == 422
    assert (await client.get(NOTES)).status_code == 401


async def test_unread_count(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    u = await two_users(client, session_maker)
    assert (await client.get(f"{NOTES}/unread-count", headers=u["sam"])).json() == {"unread_count": 3}
    assert (await client.get(f"{NOTES}/unread-count", headers=u["cleo"])).json() == {"unread_count": 3}
    assert (await client.get(f"{NOTES}/unread-count")).status_code == 401


# ---------------------------------------------------------------- mark read
async def test_mark_read(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    u = await two_users(client, session_maker)
    newest = (await client.get(NOTES, headers=u["sam"])).json()["items"][0]
    url = f"{NOTES}/{newest['id']}/read"

    assert newest["is_read"] is False
    first = await client.patch(url, headers=u["sam"])
    assert first.status_code == 200 and first.json()["is_read"] is True
    assert (await client.patch(url, headers=u["sam"])).status_code == 200  # idempotent
    assert (await client.get(f"{NOTES}/unread-count", headers=u["sam"])).json() == {"unread_count": 2}

    assert (await client.patch(url, headers=u["cleo"])).status_code == 404  # not hers
    assert (await client.patch(f"{NOTES}/{uuid.uuid4()}/read", headers=u["sam"])).status_code == 404
    assert (await client.patch(f"{NOTES}/not-a-uuid/read", headers=u["sam"])).status_code == 422
    assert (await client.patch(url)).status_code == 401


async def test_read_all(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    u = await two_users(client, session_maker)
    assert (await client.post(f"{NOTES}/read-all", headers=u["sam"])).json() == {"updated": 3}
    assert (await client.post(f"{NOTES}/read-all", headers=u["sam"])).json() == {"updated": 0}
    assert (await client.get(f"{NOTES}/unread-count", headers=u["sam"])).json() == {"unread_count": 0}
    assert (await client.get(f"{NOTES}/unread-count", headers=u["cleo"])).json() == {"unread_count": 3}
    assert (await client.post(f"{NOTES}/read-all")).status_code == 401


# --------------------------------------------------------- end-to-end flow
async def test_submission_flow_creates_notifications_for_both_sides(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    assignment = (
        await client.post(
            f"{API}/classrooms/{ctx['cid']}/assignments",
            json={"title": "HW", "state": "published"},
            headers=ctx["teacher"],
        )
    ).json()
    sub = (
        await client.post(f"{API}/assignments/{assignment['id']}/submit", json={"content": "x"}, headers=ctx["student"])
    ).json()

    teacher_notes = (await client.get(NOTES, headers=ctx["teacher"])).json()
    assert teacher_notes["total"] == 1 and teacher_notes["items"][0]["type"] == "submission_turned_in"
    assert "Sam" in teacher_notes["items"][0]["title"]

    await client.patch(f"{API}/submissions/{sub['id']}/return", headers=ctx["teacher"])
    student_notes = (await client.get(NOTES, headers=ctx["student"])).json()
    assert [n["type"] for n in student_notes["items"]] == ["submission_returned"]


# ------------------------------------------------------- push after commit
async def test_push_happens_only_after_a_successful_commit(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    uid = await user_id(client, await make_user(client, "sam@example.com"))
    socket = FakeWS()
    assert manager.register(uid, socket)  # type: ignore[arg-type]
    try:
        async with session_maker() as s:
            stage_notification(s, user_id=uid, title="rolled back")
            await s.rollback()
        await asyncio.sleep(0.05)
        assert socket.sent == []

        async with session_maker() as s:
            stage_notification(s, user_id=uid, title="kept", type="demo", link="/somewhere")
            assert socket.sent == []  # nothing before the commit
            await s.commit()
        await asyncio.sleep(0.05)
        assert len(socket.sent) == 1
        message = socket.sent[0]
        assert message["type"] == "notification"
        assert message["data"]["title"] == "kept" and message["data"]["type"] == "demo"
        assert message["data"]["link"] == "/somewhere" and message["data"]["is_read"] is False
    finally:
        manager.unregister(uid, socket)  # type: ignore[arg-type]

    listing = (await client.get(NOTES, headers=await _login(client))).json()
    assert [n["title"] for n in listing["items"]] == ["kept"]  # the rolled-back one was never stored


async def _login(client: AsyncClient) -> dict[str, str]:
    from tests.helpers import API as _API, PASSWORD

    resp = await client.post(f"{_API}/auth/login", json={"email": "sam@example.com", "password": PASSWORD})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}