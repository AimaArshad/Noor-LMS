"""Integration tests for /classrooms/{id}/announcements (needs the PostgreSQL test database)."""

import uuid
from datetime import datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models import Comment
from tests.helpers import API, add_teacher, classroom_context, make_user, promote_to_admin, user_id

pytestmark = pytest.mark.asyncio


def base(ctx: dict[str, Any]) -> str:
    return f"{API}/classrooms/{ctx['cid']}/announcements"


async def post_announcement(
    client: AsyncClient, ctx: dict[str, Any], content: str = "Welcome!", who: str = "teacher"
) -> dict[str, Any]:
    resp = await client.post(base(ctx), json={"content": content}, headers=ctx[who])
    assert resp.status_code == 201, resp.text
    return resp.json()


# ------------------------------------------------------------ create + read
async def test_teacher_posts_and_members_read(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    resp = await client.post(base(ctx), json={"content": "  Welcome to class!  "}, headers=ctx["teacher"])
    assert resp.status_code == 201, resp.text
    ann = resp.json()
    assert ann["content"] == "Welcome to class!"
    assert ann["classroom_id"] == str(ctx["cid"])
    assert ann["author"]["full_name"] == "Tina" and "email" not in ann["author"]

    for who in ("teacher", "student", "classmate"):
        listing = await client.get(base(ctx), headers=ctx[who])
        assert listing.status_code == 200, who
        data = listing.json()
        assert data["total"] == 1 and data["items"][0]["id"] == ann["id"]
        one = await client.get(f"{base(ctx)}/{ann['id']}", headers=ctx[who])
        assert one.status_code == 200 and one.json()["content"] == "Welcome to class!"


async def test_permissions(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    ann = await post_announcement(client, ctx)
    item = f"{base(ctx)}/{ann['id']}"

    # students may read but not write
    assert (await client.post(base(ctx), json={"content": "x"}, headers=ctx["student"])).status_code == 403
    assert (await client.patch(item, json={"content": "x"}, headers=ctx["student"])).status_code == 403
    assert (await client.delete(item, headers=ctx["student"])).status_code == 403

    # outsiders cannot even tell the classroom exists
    assert (await client.get(base(ctx), headers=ctx["outsider"])).status_code == 404
    assert (await client.get(item, headers=ctx["outsider"])).status_code == 404
    assert (await client.post(base(ctx), json={"content": "x"}, headers=ctx["outsider"])).status_code == 404

    # anonymous / unknown ids
    assert (await client.get(base(ctx))).status_code == 401
    assert (await client.post(base(ctx), json={"content": "x"})).status_code == 401
    unknown = f"{API}/classrooms/{uuid.uuid4()}/announcements"
    assert (await client.get(unknown, headers=ctx["teacher"])).status_code == 404
    assert (await client.get(f"{base(ctx)}/{uuid.uuid4()}", headers=ctx["teacher"])).status_code == 404
    assert (await client.get(f"{base(ctx)}/not-a-uuid", headers=ctx["teacher"])).status_code == 422


async def test_validation(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    ann = await post_announcement(client, ctx)
    item = f"{base(ctx)}/{ann['id']}"
    teacher = ctx["teacher"]

    assert (await client.post(base(ctx), json={"content": "   "}, headers=teacher)).status_code == 422
    assert (await client.post(base(ctx), json={}, headers=teacher)).status_code == 422
    assert (await client.post(base(ctx), json={"content": "x" * 10_001}, headers=teacher)).status_code == 422
    forged = {"content": "x", "author_id": str(uuid.uuid4())}
    assert (await client.post(base(ctx), json=forged, headers=teacher)).status_code == 422
    assert (await client.patch(item, json={}, headers=teacher)).status_code == 422
    assert (await client.patch(item, json={"content": None}, headers=teacher)).status_code == 422


# ------------------------------------------------------------------ listing
async def test_list_is_newest_first_and_paginated(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    for text in ("one", "two", "three"):
        await post_announcement(client, ctx, text)

    full = (await client.get(base(ctx), headers=ctx["student"])).json()
    assert [a["content"] for a in full["items"]] == ["three", "two", "one"]
    assert full["total"] == 3 and full["limit"] == 20 and full["offset"] == 0

    page = (await client.get(base(ctx), params={"limit": 2, "offset": 1}, headers=ctx["student"])).json()
    assert [a["content"] for a in page["items"]] == ["two", "one"] and page["total"] == 3

    assert (await client.get(base(ctx), params={"limit": 0}, headers=ctx["student"])).status_code == 422
    assert (await client.get(base(ctx), params={"limit": 101}, headers=ctx["student"])).status_code == 422
    assert (await client.get(base(ctx), params={"offset": -1}, headers=ctx["student"])).status_code == 422


async def test_announcement_is_scoped_to_its_classroom(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    ann = await post_announcement(client, ctx)
    other = (await client.post(f"{API}/classrooms", json={"name": "Other"}, headers=ctx["teacher"])).json()
    wrong = f"{API}/classrooms/{other['id']}/announcements/{ann['id']}"

    assert (await client.get(wrong, headers=ctx["teacher"])).status_code == 404
    assert (await client.patch(wrong, json={"content": "x"}, headers=ctx["teacher"])).status_code == 404
    assert (await client.delete(wrong, headers=ctx["teacher"])).status_code == 404
    assert (await client.get(f"{base(ctx)}/{ann['id']}", headers=ctx["teacher"])).status_code == 200


# ------------------------------------------------------------------- update
async def test_update(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    ann = await post_announcement(client, ctx, "Original")
    resp = await client.patch(
        f"{base(ctx)}/{ann['id']}", json={"content": " Edited "}, headers=ctx["teacher"]
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["content"] == "Edited" and body["author"]["full_name"] == "Tina"
    assert datetime.fromisoformat(body["updated_at"]) >= datetime.fromisoformat(body["created_at"])

    seen = (await client.get(f"{base(ctx)}/{ann['id']}", headers=ctx["student"])).json()
    assert seen["content"] == "Edited"


async def test_co_teacher_can_edit_and_delete(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    carl = await make_user(client, "carl@example.com", "teacher")
    await add_teacher(session_maker, ctx["cid"], await user_id(client, carl))
    ann = await post_announcement(client, ctx)
    item = f"{base(ctx)}/{ann['id']}"

    assert (await client.patch(item, json={"content": "By Carl"}, headers=carl)).status_code == 200
    assert (await client.delete(item, headers=carl)).status_code == 204


# ------------------------------------------------------------------- delete
async def test_delete_removes_announcement_and_its_comments(
    client: AsyncClient, session_maker  # noqa: ANN001
) -> None:
    ctx = await classroom_context(client)
    ann = await post_announcement(client, ctx)
    for who in ("student", "teacher"):
        resp = await client.post(
            f"{API}/comments",
            json={"target_type": "announcement", "target_id": ann["id"], "body": "hi"},
            headers=ctx[who],
        )
        assert resp.status_code == 201, resp.text

    async with session_maker() as s:
        assert await s.scalar(select(func.count()).select_from(Comment)) == 2

    item = f"{base(ctx)}/{ann['id']}"
    assert (await client.delete(item, headers=ctx["teacher"])).status_code == 204
    assert (await client.get(item, headers=ctx["teacher"])).status_code == 404
    assert (await client.delete(item, headers=ctx["teacher"])).status_code == 404

    async with session_maker() as s:
        assert await s.scalar(select(func.count()).select_from(Comment)) == 0


# ----------------------------------------------------------------- archived
async def test_archived_classroom_is_read_only(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    ann = await post_announcement(client, ctx)
    item = f"{base(ctx)}/{ann['id']}"
    classroom_url = f"{API}/classrooms/{ctx['cid']}"

    await client.patch(classroom_url, json={"is_archived": True}, headers=ctx["teacher"])
    assert (await client.post(base(ctx), json={"content": "x"}, headers=ctx["teacher"])).status_code == 403
    assert (await client.patch(item, json={"content": "x"}, headers=ctx["teacher"])).status_code == 403
    assert (await client.delete(item, headers=ctx["teacher"])).status_code == 403
    assert (await client.get(base(ctx), headers=ctx["student"])).status_code == 200  # reading still works
    assert (await client.get(item, headers=ctx["student"])).status_code == 200

    await client.patch(classroom_url, json={"is_archived": False}, headers=ctx["teacher"])
    assert (await client.post(base(ctx), json={"content": "back"}, headers=ctx["teacher"])).status_code == 201


# -------------------------------------------------------------------- admin
async def test_admin_can_post_without_being_a_member(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    admin = await make_user(client, "root@example.com")
    await promote_to_admin(session_maker, "root@example.com")

    resp = await client.post(base(ctx), json={"content": "From admin"}, headers=admin)
    assert resp.status_code == 201, resp.text
    assert resp.json()["author"]["full_name"] == "Root"
    assert (await client.get(base(ctx), headers=admin)).json()["total"] == 1