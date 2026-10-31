"""Integration tests for /todo (needs the PostgreSQL test database)."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models import TodoItem
from tests.helpers import API, classroom_context, make_user, user_id

pytestmark = pytest.mark.asyncio

TODO = f"{API}/todo"


# ------------------------------------------------------------------ helpers
async def new_assignment(
    client: AsyncClient, ctx: dict[str, Any], title: str = "HW", *, published: bool = True, **extra: Any
) -> dict[str, Any]:
    payload = {"title": title, "state": "published" if published else "draft", **extra}
    resp = await client.post(
        f"{API}/classrooms/{ctx['cid']}/assignments", json=payload, headers=ctx["teacher"]
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def new_quiz(client: AsyncClient, ctx: dict[str, Any], title: str = "Quiz", **extra: Any) -> dict[str, Any]:
    payload = {
        "title": title,
        "published": True,
        "questions": [
            {
                "prompt": "2+2?",
                "type": "mcq",
                "points": 1,
                "options": [{"text": "3"}, {"text": "4", "is_correct": True}],
            }
        ],
        **extra,
    }
    resp = await client.post(f"{API}/classrooms/{ctx['cid']}/quizzes", json=payload, headers=ctx["teacher"])
    assert resp.status_code == 201, resp.text
    return resp.json()


async def todo(client: AsyncClient, headers: dict[str, str], **params: Any) -> dict[str, Any]:
    resp = await client.get(TODO, params=params, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def count_rows(session_maker: Any, uid: uuid.UUID) -> int:  # noqa: ANN401
    async with session_maker() as s:
        return await s.scalar(select(func.count()).select_from(TodoItem).where(TodoItem.user_id == uid)) or 0


# ------------------------------------------------------------- merged list
async def test_list_merges_assignments_and_quizzes_sorted_by_due_date(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    await new_quiz(client, ctx, "Quiz (no due date)")
    await new_assignment(client, ctx, "Later", due_at="2031-01-01T10:00:00Z")
    await new_assignment(client, ctx, "Sooner", due_at="2030-01-01T10:00:00Z")
    await new_assignment(client, ctx, "Hidden draft", published=False)

    data = await todo(client, ctx["student"])
    assert [i["title"] for i in data["items"]] == ["Sooner", "Later", "Quiz (no due date)"]
    assert data["total"] == 3 and data["pending_count"] == 3 and data["overdue_count"] == 0
    first = data["items"][0]
    assert first["ref_type"] == "assignment" and first["is_done"] is False and first["is_overdue"] is False
    assert first["classroom_name"] == "Math 101" and first["classroom_id"] == str(ctx["cid"])
    assert first["link"] == f"/classrooms/{ctx['cid']}/assignments/{first['ref_id']}"
    assert data["items"][2]["link"] == f"/classrooms/{ctx['cid']}/quizzes/{data['items'][2]['ref_id']}"

    assert (await todo(client, ctx["teacher"]))["total"] == 0  # teachers have no derived items
    assert (await client.get(TODO)).status_code == 401


async def test_late_joiner_gets_derived_items_materialized(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    await new_assignment(client, ctx, "Old homework")
    await new_quiz(client, ctx, "Old quiz")

    dan = await make_user(client, "dan@example.com")
    code = (await client.get(f"{API}/classrooms/{ctx['cid']}", headers=ctx["teacher"])).json()["join_code"]
    assert (await client.post(f"{API}/classrooms/join", json={"join_code": code}, headers=dan)).status_code == 200
    dan_id = await user_id(client, dan)
    assert await count_rows(session_maker, dan_id) == 0

    first = await todo(client, dan)
    assert {i["title"] for i in first["items"]} == {"Old homework", "Old quiz"}
    assert await count_rows(session_maker, dan_id) == 2  # now real rows with real ids

    second = await todo(client, dan)  # idempotent: same ids, no duplicates
    assert {i["id"] for i in second["items"]} == {i["id"] for i in first["items"]}
    assert await count_rows(session_maker, dan_id) == 2


# -------------------------------------------------------------- completion
async def test_turned_in_work_counts_as_done(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    assignment = await new_assignment(client, ctx, "HW")
    quiz = await new_quiz(client, ctx, "Quiz")
    student = ctx["student"]
    assert (await todo(client, student))["pending_count"] == 2

    sub = await client.post(f"{API}/assignments/{assignment['id']}/submit", json={"content": "done"}, headers=student)
    assert sub.status_code == 200
    data = await todo(client, student)
    assert data["pending_count"] == 1
    assert [i["title"] for i in (await todo(client, student, is_done="false"))["items"]] == ["Quiz"]
    done = (await todo(client, student, is_done="true"))["items"]
    assert [i["title"] for i in done] == ["HW"] and done[0]["is_done"] is True

    await client.post(f"{API}/quizzes/{quiz['id']}/start", headers=student)
    assert (await client.post(f"{API}/quizzes/{quiz['id']}/submit", json={"answers": []}, headers=student)).status_code == 200
    assert (await todo(client, student))["pending_count"] == 0

    classmate = await todo(client, ctx["classmate"])  # other students are unaffected
    assert classmate["pending_count"] == 2


# --------------------------------------------------------------------- PATCH
async def test_mark_done_and_undone(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    assignment = await new_assignment(client, ctx, "HW")
    item = (await todo(client, ctx["student"]))["items"][0]
    url = f"{TODO}/{item['id']}"

    marked = await client.patch(url, json={"is_done": True}, headers=ctx["student"])
    assert marked.status_code == 200 and marked.json()["is_done"] is True
    assert marked.json()["title"] == "HW" and marked.json()["classroom_name"] == "Math 101"
    assert (await todo(client, ctx["student"]))["pending_count"] == 0

    undone = await client.patch(url, json={"is_done": False}, headers=ctx["student"])
    assert undone.json()["is_done"] is False and (await todo(client, ctx["student"]))["pending_count"] == 1

    # turned-in work cannot be un-done
    await client.post(f"{API}/assignments/{assignment['id']}/submit", json={"content": "x"}, headers=ctx["student"])
    forced = await client.patch(url, json={"is_done": False}, headers=ctx["student"])
    assert forced.status_code == 200 and forced.json()["is_done"] is True


async def test_patch_validation_and_isolation(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    await new_assignment(client, ctx)
    item = (await todo(client, ctx["student"]))["items"][0]
    url = f"{TODO}/{item['id']}"

    assert (await client.patch(url, json={"is_done": True}, headers=ctx["classmate"])).status_code == 404  # not theirs
    assert (await client.patch(f"{TODO}/{uuid.uuid4()}", json={"is_done": True}, headers=ctx["student"])).status_code == 404
    assert (await client.patch(f"{TODO}/not-a-uuid", json={"is_done": True}, headers=ctx["student"])).status_code == 422
    assert (await client.patch(url, json={}, headers=ctx["student"])).status_code == 422
    assert (await client.patch(url, json={"is_done": None}, headers=ctx["student"])).status_code == 422
    assert (await client.patch(url, json={"is_done": True, "title": "hack"}, headers=ctx["student"])).status_code == 422
    assert (await client.patch(url, json={"is_done": True})).status_code == 401


# ------------------------------------------------------------- visibility
async def test_items_disappear_when_they_no_longer_apply(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    teacher, student = ctx["teacher"], ctx["student"]
    assignment = await new_assignment(client, ctx, "HW")
    assert (await todo(client, student))["total"] == 1

    await client.patch(f"{API}/assignments/{assignment['id']}", json={"state": "draft"}, headers=teacher)
    assert (await todo(client, student))["total"] == 0  # unpublished
    await client.patch(f"{API}/assignments/{assignment['id']}", json={"state": "published"}, headers=teacher)
    assert (await todo(client, student))["total"] == 1

    await client.patch(f"{API}/classrooms/{ctx['cid']}", json={"is_archived": True}, headers=teacher)
    assert (await todo(client, student))["total"] == 0  # archived classroom
    await client.patch(f"{API}/classrooms/{ctx['cid']}", json={"is_archived": False}, headers=teacher)
    assert (await todo(client, student))["total"] == 1

    assert (await client.post(f"{API}/classrooms/{ctx['cid']}/leave", headers=student)).status_code == 204
    assert (await todo(client, student))["total"] == 0  # left the classroom

    await client.delete(f"{API}/assignments/{assignment['id']}", headers=teacher)
    assert (await todo(client, ctx["classmate"]))["total"] == 0  # deleted


async def test_overdue_and_pagination(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    await new_assignment(client, ctx, "Late", due_at="2020-01-01T00:00:00Z")
    for i, due in enumerate(("2030-01-01T00:00:00Z", "2031-01-01T00:00:00Z", "2032-01-01T00:00:00Z")):
        await new_assignment(client, ctx, f"Future {i}", due_at=due)

    data = await todo(client, ctx["student"])
    assert data["items"][0]["title"] == "Late" and data["items"][0]["is_overdue"] is True
    assert data["overdue_count"] == 1 and data["total"] == 4

    page = await todo(client, ctx["student"], limit=2, offset=1)
    assert [i["title"] for i in page["items"]] == ["Future 0", "Future 1"] and page["total"] == 4
    assert (await client.get(TODO, params={"limit": 0}, headers=ctx["student"])).status_code == 422


async def test_personal_items_are_always_listed(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    sam = await user_id(client, ctx["student"])
    async with session_maker() as s:
        s.add(TodoItem(user_id=sam, title="Buy pens"))
        await s.commit()

    data = await todo(client, ctx["student"])
    item = data["items"][0]
    assert item["title"] == "Buy pens" and item["ref_type"] is None
    assert item["classroom_id"] is None and item["link"] is None and item["is_overdue"] is False

    marked = await client.patch(f"{TODO}/{item['id']}", json={"is_done": True}, headers=ctx["student"])
    assert marked.status_code == 200 and marked.json()["is_done"] is True
    await client.post(f"{API}/classrooms/{ctx['cid']}/leave", headers=ctx["student"])
    assert (await todo(client, ctx["student"]))["total"] == 1  # still there after leaving
    assert (await todo(client, ctx["classmate"]))["total"] == 0  # and private to Sam