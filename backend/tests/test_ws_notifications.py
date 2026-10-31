"""Integration tests for WS /ws/notifications (needs the PostgreSQL test database)."""

import asyncio
from datetime import timedelta
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.core.security import create_access_token
from app.main import app
from app.websockets.manager import manager
from app.websockets.routes import get_session_factory
from tests.helpers import API, classroom_context, make_user, user_id
from tests.ws_client import WSClient

pytestmark = pytest.mark.asyncio

PATH = "/ws/notifications"


@pytest_asyncio.fixture
async def ws_ready(client: AsyncClient, session_maker):  # noqa: ANN001, ANN201
    """The socket endpoint authenticates through the TEST database."""
    app.dependency_overrides[get_session_factory] = lambda: session_maker
    yield
    assert manager.connection_count() == 0, "a test left a WebSocket registered"


def token_of(headers: dict[str, str]) -> str:
    return headers["Authorization"].removeprefix("Bearer ")


async def connect(token: str) -> WSClient:
    return WSClient(app, PATH, query=f"token={token}")


async def expect_connected(ws: WSClient, unread: int = 0) -> None:
    await ws.accepted()
    assert await ws.receive_json() == {"type": "connected", "unread_count": unread}


# ---------------------------------------------------------------- handshake
async def test_connect_with_query_token(client: AsyncClient, ws_ready) -> None:  # noqa: ANN001
    headers = await make_user(client, "sam@example.com")
    uid = await user_id(client, headers)
    async with await connect(token_of(headers)) as ws:
        await expect_connected(ws)
        assert manager.connection_count(uid) == 1
    assert manager.connection_count(uid) == 0  # cleaned up on disconnect


async def test_connect_reports_unread_count(client: AsyncClient, ws_ready, session_maker) -> None:  # noqa: ANN001
    from tests.test_notifications_api import seed

    headers = await make_user(client, "sam@example.com")
    await seed(session_maker, await user_id(client, headers), 4, read=1)
    async with await connect(token_of(headers)) as ws:
        await expect_connected(ws, unread=3)


async def test_first_message_authentication(client: AsyncClient, ws_ready) -> None:  # noqa: ANN001
    headers = await make_user(client, "sam@example.com")
    async with WSClient(app, PATH) as ws:  # no token in the URL
        await ws.accepted()
        ws.send_json({"type": "auth", "token": token_of(headers)})
        assert (await ws.receive_json())["type"] == "connected"


@pytest.mark.parametrize("bad", ["garbage", ""])
async def test_bad_query_token_is_rejected(client: AsyncClient, ws_ready, bad: str) -> None:  # noqa: ANN001
    async with WSClient(app, PATH, query=f"token={bad}") as ws:
        await ws.accepted()
        assert await ws.closed() == 4401
    assert manager.connection_count() == 0


async def test_refresh_token_is_not_accepted(client: AsyncClient, ws_ready) -> None:  # noqa: ANN001
    await make_user(client, "sam@example.com")
    login = await client.post(f"{API}/auth/login", json={"email": "sam@example.com", "password": "Passw0rdX"})
    async with await connect(login.json()["refresh_token"]) as ws:
        await ws.accepted()
        assert await ws.closed() == 4401


async def test_wrong_first_message_and_auth_timeout(
    client: AsyncClient, ws_ready, monkeypatch: pytest.MonkeyPatch  # noqa: ANN001
) -> None:
    async with WSClient(app, PATH) as ws:
        await ws.accepted()
        ws.send_json({"type": "hello"})
        assert await ws.closed() == 4401

    monkeypatch.setattr("app.websockets.routes.AUTH_TIMEOUT_SECONDS", 0.2)
    async with WSClient(app, PATH) as ws:  # says nothing at all
        await ws.accepted()
        assert await ws.closed() == 4401


async def test_deactivated_user_is_rejected(client: AsyncClient, ws_ready, session_maker) -> None:  # noqa: ANN001
    from sqlalchemy import update

    from app.models import User

    headers = await make_user(client, "sam@example.com")
    async with session_maker() as s:
        await s.execute(update(User).where(User.email == "sam@example.com").values(is_active=False))
        await s.commit()
    async with await connect(token_of(headers)) as ws:
        await ws.accepted()
        assert await ws.closed() == 4401


# ------------------------------------------------------------ connection life
async def test_ping_pong_and_unsupported_messages(client: AsyncClient, ws_ready) -> None:  # noqa: ANN001
    headers = await make_user(client, "sam@example.com")
    async with await connect(token_of(headers)) as ws:
        await expect_connected(ws)
        ws.send_json({"type": "ping"})
        assert await ws.receive_json() == {"type": "pong"}
        ws.send_json({"type": "nope"})
        assert (await ws.receive_json())["type"] == "error"
        ws.send_text("not json at all")
        assert (await ws.receive_json())["type"] == "error"
        ws.send_text("x" * 5000)
        assert await ws.closed() == 1009


async def test_connection_limit(client: AsyncClient, ws_ready, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    headers = await make_user(client, "sam@example.com")
    uid = await user_id(client, headers)
    monkeypatch.setattr(manager, "max_per_user", 1)
    async with await connect(token_of(headers)) as first:
        await expect_connected(first)
        async with await connect(token_of(headers)) as second:
            await second.accepted()
            assert await second.closed() == 4429
        assert manager.connection_count(uid) == 1  # the first one is untouched
        first.send_json({"type": "ping"})
        assert await first.receive_json() == {"type": "pong"}


async def test_idle_sockets_are_closed(
    client: AsyncClient, ws_ready, monkeypatch: pytest.MonkeyPatch  # noqa: ANN001
) -> None:
    headers = await make_user(client, "sam@example.com")
    monkeypatch.setattr("app.websockets.routes.IDLE_TIMEOUT_SECONDS", 0.3)
    async with await connect(token_of(headers)) as ws:
        await expect_connected(ws)
        assert await ws.closed() == 4408


async def test_socket_closes_when_the_token_expires(client: AsyncClient, ws_ready) -> None:  # noqa: ANN001
    headers = await make_user(client, "sam@example.com")
    short_lived = create_access_token(await user_id(client, headers), expires_delta=timedelta(seconds=2))
    async with await connect(short_lived) as ws:
        await expect_connected(ws)
        assert await ws.closed(timeout=5) == 4401  # the client must refresh and reconnect


# -------------------------------------------------------------- live pushes
async def test_submission_is_pushed_to_the_teacher_only(client: AsyncClient, ws_ready) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    assignment = (
        await client.post(
            f"{API}/classrooms/{ctx['cid']}/assignments",
            json={"title": "HW 1", "state": "published"},
            headers=ctx["teacher"],
        )
    ).json()

    async with (
        await connect(token_of(ctx["teacher"])) as teacher_ws,
        await connect(token_of(ctx["student"])) as student_ws,
        await connect(token_of(ctx["outsider"])) as outsider_ws,
    ):
        for ws in (teacher_ws, student_ws, outsider_ws):
            await expect_connected(ws)

        resp = await client.post(
            f"{API}/assignments/{assignment['id']}/submit", json={"content": "my work"}, headers=ctx["student"]
        )
        assert resp.status_code == 200, resp.text
        submission_id = resp.json()["id"]

        message = await teacher_ws.receive_json()
        assert message["type"] == "notification"
        data: dict[str, Any] = message["data"]
        assert data["type"] == "submission_turned_in" and "Sam" in data["title"] and "HW 1" in data["title"]
        assert data["is_read"] is False
        assert data["link"] == f"/classrooms/{ctx['cid']}/assignments/{assignment['id']}"

        # the pushed payload is exactly what REST returns
        listing = (await client.get(f"{API}/notifications", headers=ctx["teacher"])).json()
        assert listing["items"][0] == data

        # returning the work notifies the student, not the teacher
        assert (
            await client.patch(f"{API}/submissions/{submission_id}/return", headers=ctx["teacher"])
        ).status_code == 200
        returned = await student_ws.receive_json()
        assert returned["data"]["type"] == "submission_returned"

        for quiet in (outsider_ws, teacher_ws):
            with pytest.raises(asyncio.TimeoutError):
                await quiet.event(timeout=0.3)


async def test_new_material_is_pushed_to_students(client: AsyncClient, ws_ready) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    async with await connect(token_of(ctx["student"])) as student_ws, await connect(
        token_of(ctx["classmate"])
    ) as classmate_ws:
        await expect_connected(student_ws)
        await expect_connected(classmate_ws)
        resp = await client.post(
            f"{API}/classrooms/{ctx['cid']}/materials", json={"title": "Syllabus"}, headers=ctx["teacher"]
        )
        assert resp.status_code == 201
        for ws in (student_ws, classmate_ws):
            data = (await ws.receive_json())["data"]
            assert data["type"] == "material_posted" and data["title"] == "New material: Syllabus"


async def test_every_open_tab_receives_the_push(client: AsyncClient, ws_ready) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    async with await connect(token_of(ctx["student"])) as tab1, await connect(token_of(ctx["student"])) as tab2:
        await expect_connected(tab1)
        await expect_connected(tab2)
        await client.post(
            f"{API}/classrooms/{ctx['cid']}/materials", json={"title": "Notes"}, headers=ctx["teacher"]
        )
        first, second = await tab1.receive_json(), await tab2.receive_json()
        assert first == second and first["data"]["type"] == "material_posted"