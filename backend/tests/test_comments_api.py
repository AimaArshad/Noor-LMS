"""Integration tests for /comments (needs the PostgreSQL test database)."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select

from app.models import Assignment, AssignmentState, Comment
from tests.helpers import API, classroom_context, make_user, promote_to_admin

pytestmark = pytest.mark.asyncio

COMMENTS = f"{API}/comments"


# ------------------------------------------------------------------ helpers
async def new_announcement(client: AsyncClient, ctx: dict[str, Any]) -> str:
    resp = await client.post(
        f"{API}/classrooms/{ctx['cid']}/announcements",
        json={"content": "Hello class"},
        headers=ctx["teacher"],
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def seed_assignment(
    session_maker, cid: uuid.UUID, state: AssignmentState = AssignmentState.PUBLISHED  # noqa: ANN001
) -> str:
    async with session_maker() as s:
        assignment = Assignment(classroom_id=cid, title="HW", state=state)
        s.add(assignment)
        await s.commit()
        return str(assignment.id)


async def add_comment(
    client: AsyncClient,
    headers: dict[str, str],
    target_type: str,
    target_id: str,
    body: str = "Thanks!",
) -> Response:
    return await client.post(
        COMMENTS,
        json={"target_type": target_type, "target_id": target_id, "body": body},
        headers=headers,
    )


async def list_comments(
    client: AsyncClient,
    headers: dict[str, str],
    target_type: str,
    target_id: str,
    **params: Any,
) -> Response:
    return await client.get(
        COMMENTS, params={"target_type": target_type, "target_id": target_id, **params}, headers=headers
    )


# ------------------------------------------------------------------- create
async def test_comment_thread_on_announcement(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    aid = await new_announcement(client, ctx)

    first = await add_comment(client, ctx["student"], "announcement", aid, "  Thanks!  ")
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["body"] == "Thanks!"
    assert body["target_type"] == "announcement" and body["target_id"] == aid
    assert body["author"]["full_name"] == "Sam" and "email" not in body["author"]

    assert (await add_comment(client, ctx["teacher"], "announcement", aid, "You're welcome")).status_code == 201

    for who in ("student", "classmate", "teacher"):
        resp = await list_comments(client, ctx[who], "announcement", aid)
        assert resp.status_code == 200, who
        data = resp.json()
        assert data["total"] == 2
        assert [c["author"]["full_name"] for c in data["items"]] == ["Sam", "Tina"]  # oldest first


async def test_assignment_comments_respect_draft_state(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    published = await seed_assignment(session_maker, ctx["cid"], AssignmentState.PUBLISHED)
    draft = await seed_assignment(session_maker, ctx["cid"], AssignmentState.DRAFT)

    assert (await add_comment(client, ctx["student"], "assignment", published)).status_code == 201
    assert (await list_comments(client, ctx["classmate"], "assignment", published)).json()["total"] == 1

    # students cannot see drafts at all
    assert (await add_comment(client, ctx["student"], "assignment", draft)).status_code == 404
    assert (await list_comments(client, ctx["student"], "assignment", draft)).status_code == 404
    # teachers can
    assert (await add_comment(client, ctx["teacher"], "assignment", draft, "Draft note")).status_code == 201
    assert (await list_comments(client, ctx["teacher"], "assignment", draft)).json()["total"] == 1


async def test_outsiders_have_no_access(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    aid = await new_announcement(client, ctx)
    mine = (await add_comment(client, ctx["student"], "announcement", aid)).json()

    assert (await add_comment(client, ctx["outsider"], "announcement", aid)).status_code == 404
    assert (await list_comments(client, ctx["outsider"], "announcement", aid)).status_code == 404
    assert (await client.delete(f"{COMMENTS}/{mine['id']}", headers=ctx["outsider"])).status_code == 404


async def test_validation_and_auth(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    aid = await new_announcement(client, ctx)
    student = ctx["student"]

    assert (await add_comment(client, student, "announcement", str(uuid.uuid4()))).status_code == 404
    assert (await add_comment(client, student, "assignment", aid)).status_code == 404  # id of the wrong type
    assert (await add_comment(client, student, "quiz", aid)).status_code == 422  # unsupported target type
    assert (await add_comment(client, student, "announcement", aid, "   ")).status_code == 422
    assert (await add_comment(client, student, "announcement", aid, "x" * 5001)).status_code == 422
    forged = {"target_type": "announcement", "target_id": aid, "body": "hi", "author_id": str(uuid.uuid4())}
    assert (await client.post(COMMENTS, json=forged, headers=student)).status_code == 422

    assert (await client.get(COMMENTS, headers=student)).status_code == 422  # missing query params
    bad_id = {"target_type": "announcement", "target_id": "nope"}
    assert (await client.get(COMMENTS, params=bad_id, headers=student)).status_code == 422
    assert (await list_comments(client, student, "announcement", aid, limit=0)).status_code == 422

    assert (await client.post(COMMENTS, json=forged)).status_code == 401
    assert (await client.get(COMMENTS, params={"target_type": "announcement", "target_id": aid})).status_code == 401


async def test_comments_are_scoped_to_their_target(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    first, second = await new_announcement(client, ctx), await new_announcement(client, ctx)
    await add_comment(client, ctx["student"], "announcement", first, "on first")

    assert (await list_comments(client, ctx["student"], "announcement", first)).json()["total"] == 1
    assert (await list_comments(client, ctx["student"], "announcement", second)).json() == {
        "items": [], "total": 0, "limit": 50, "offset": 0,
    }


async def test_pagination(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    aid = await new_announcement(client, ctx)
    for text in ("a", "b", "c"):
        await add_comment(client, ctx["student"], "announcement", aid, text)

    page = (await list_comments(client, ctx["student"], "announcement", aid, limit=2, offset=2)).json()
    assert [c["body"] for c in page["items"]] == ["c"] and page["total"] == 3


# ------------------------------------------------------------------- delete
async def test_delete_permissions(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    aid = await new_announcement(client, ctx)

    mine = (await add_comment(client, ctx["student"], "announcement", aid, "mine")).json()
    url = f"{COMMENTS}/{mine['id']}"
    assert (await client.delete(url)).status_code == 401
    assert (await client.delete(url, headers=ctx["classmate"])).status_code == 403  # member, not author
    assert (await client.delete(url, headers=ctx["outsider"])).status_code == 404
    assert (await client.delete(url, headers=ctx["student"])).status_code == 204  # author
    assert (await client.delete(url, headers=ctx["student"])).status_code == 404  # already gone

    theirs = (await add_comment(client, ctx["classmate"], "announcement", aid, "theirs")).json()
    assert (await client.delete(f"{COMMENTS}/{theirs['id']}", headers=ctx["teacher"])).status_code == 204

    assert (await client.delete(f"{COMMENTS}/{uuid.uuid4()}", headers=ctx["teacher"])).status_code == 404
    assert (await client.delete(f"{COMMENTS}/not-a-uuid", headers=ctx["teacher"])).status_code == 422
    assert (await list_comments(client, ctx["teacher"], "announcement", aid)).json()["total"] == 0


async def test_deleting_the_target_removes_its_comments(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    assignment_id = await seed_assignment(session_maker, ctx["cid"])
    await add_comment(client, ctx["student"], "assignment", assignment_id)

    async with session_maker() as s:
        assignment = await s.get(Assignment, uuid.UUID(assignment_id))
        await s.delete(assignment)  # ORM delete -> after_delete listener removes the comments
        await s.commit()
        assert await s.scalar(select(func.count()).select_from(Comment)) == 0


# ----------------------------------------------------------------- archived
async def test_archived_classroom_is_read_only(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    aid = await new_announcement(client, ctx)
    mine = (await add_comment(client, ctx["student"], "announcement", aid)).json()
    classroom_url = f"{API}/classrooms/{ctx['cid']}"

    await client.patch(classroom_url, json={"is_archived": True}, headers=ctx["teacher"])
    assert (await add_comment(client, ctx["student"], "announcement", aid)).status_code == 403
    assert (await client.delete(f"{COMMENTS}/{mine['id']}", headers=ctx["student"])).status_code == 403
    assert (await list_comments(client, ctx["student"], "announcement", aid)).json()["total"] == 1

    await client.patch(classroom_url, json={"is_archived": False}, headers=ctx["teacher"])
    assert (await client.delete(f"{COMMENTS}/{mine['id']}", headers=ctx["student"])).status_code == 204


# -------------------------------------------------------------------- admin
async def test_admin_can_comment_and_moderate(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    aid = await new_announcement(client, ctx)
    admin = await make_user(client, "root@example.com")
    await promote_to_admin(session_maker, "root@example.com")

    theirs = (await add_comment(client, ctx["student"], "announcement", aid)).json()
    assert (await add_comment(client, admin, "announcement", aid, "Admin here")).status_code == 201
    assert (await client.delete(f"{COMMENTS}/{theirs['id']}", headers=admin)).status_code == 204