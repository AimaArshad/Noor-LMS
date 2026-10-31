"""Integration tests for assignments & submissions (needs the PostgreSQL test database)."""

import uuid
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient, Response
from sqlalchemy import func, select

from app.api.v1.routers.files import get_storage_backend
from app.main import app
from app.models import Comment, Notification, Submission, TodoItem
from app.services.storage import LocalStorage
from tests.helpers import (
    API,
    add_teacher,
    classroom_context,
    make_user,
    promote_to_admin,
    user_id,
)

pytestmark = pytest.mark.asyncio

ASSIGNMENTS = f"{API}/assignments"
SUBMISSIONS = f"{API}/submissions"
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
DUE = "2030-01-01T10:00:00Z"


# ------------------------------------------------------------------ helpers
def cls_url(ctx: dict[str, Any]) -> str:
    return f"{API}/classrooms/{ctx['cid']}/assignments"


async def create_assignment(
    client: AsyncClient, ctx: dict[str, Any], *, published: bool = True, **extra: Any
) -> dict[str, Any]:
    payload = {
        "title": "HW 1",
        "max_points": 50,
        "state": "published" if published else "draft",
        **extra,
    }
    resp = await client.post(cls_url(ctx), json=payload, headers=ctx["teacher"])
    assert resp.status_code == 201, resp.text
    return resp.json()


async def submit(
    client: AsyncClient,
    ctx: dict[str, Any],
    assignment_id: str,
    who: str = "student",
    content: str | None = "My answer",
    **extra: Any,
) -> Response:
    body: dict[str, Any] = {**extra}
    if content is not None:
        body["content"] = content
    return await client.post(f"{ASSIGNMENTS}/{assignment_id}/submit", json=body, headers=ctx[who])


async def count(session_maker: Any, model: Any, *where: Any) -> int:  # noqa: ANN401
    async with session_maker() as s:
        return await s.scalar(select(func.count()).select_from(model).where(*where)) or 0


@pytest_asyncio.fixture
async def storage(client: AsyncClient, tmp_path: Path) -> LocalStorage:
    backend = LocalStorage(tmp_path / "uploads")
    app.dependency_overrides[get_storage_backend] = lambda: backend
    return backend


async def upload_pdf(client: AsyncClient, headers: dict[str, str], name: str = "doc.pdf") -> dict:
    resp = await client.post(
        f"{API}/files/upload", files={"file": (name, PDF, "application/pdf")}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ------------------------------------------------------------------- create
async def test_create_and_validation(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    resp = await client.post(
        cls_url(ctx),
        json={"title": "  Essay  ", "description": "Write", "due_at": DUE, "max_points": 20},
        headers=ctx["teacher"],
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "Essay" and body["state"] == "draft" and body["max_points"] == 20
    assert body["classroom_id"] == str(ctx["cid"]) and body["attachments"] == []

    teacher = ctx["teacher"]
    assert (await client.post(cls_url(ctx), json={"title": "  "}, headers=teacher)).status_code == 422
    assert (await client.post(cls_url(ctx), json={"title": "x", "max_points": 0}, headers=teacher)).status_code == 422
    naive = {"title": "x", "due_at": "2030-01-01T10:00:00"}
    assert (await client.post(cls_url(ctx), json=naive, headers=teacher)).status_code == 422
    assert (await client.post(cls_url(ctx), json={"title": "x", "classroom_id": str(uuid.uuid4())}, headers=teacher)).status_code == 422


async def test_only_classroom_teachers_create(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    payload = {"title": "x"}
    assert (await client.post(cls_url(ctx), json=payload, headers=ctx["student"])).status_code == 403
    assert (await client.post(cls_url(ctx), json=payload, headers=ctx["outsider"])).status_code == 404
    assert (await client.post(cls_url(ctx), json=payload)).status_code == 401


# --------------------------------------------------------------- visibility
async def test_students_never_see_drafts(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    draft = await create_assignment(client, ctx, published=False, title="Draft")
    live = await create_assignment(client, ctx, title="Live")

    student_list = (await client.get(cls_url(ctx), headers=ctx["student"])).json()
    assert [a["title"] for a in student_list["items"]] == ["Live"] and student_list["total"] == 1
    teacher_list = (await client.get(cls_url(ctx), headers=ctx["teacher"])).json()
    assert {a["title"] for a in teacher_list["items"]} == {"Draft", "Live"}
    only_drafts = (await client.get(cls_url(ctx), params={"state": "draft"}, headers=ctx["teacher"])).json()
    assert [a["title"] for a in only_drafts["items"]] == ["Draft"]
    assert (await client.get(cls_url(ctx), params={"state": "draft"}, headers=ctx["student"])).json()["total"] == 0

    assert (await client.get(f"{ASSIGNMENTS}/{draft['id']}", headers=ctx["student"])).status_code == 404
    assert (await client.get(f"{ASSIGNMENTS}/{draft['id']}", headers=ctx["teacher"])).status_code == 200
    assert (await client.get(f"{ASSIGNMENTS}/{live['id']}", headers=ctx["student"])).status_code == 200
    assert (await client.get(f"{ASSIGNMENTS}/{live['id']}", headers=ctx["outsider"])).status_code == 404
    assert (await client.get(f"{ASSIGNMENTS}/{uuid.uuid4()}", headers=ctx["teacher"])).status_code == 404
    assert (await client.get(f"{ASSIGNMENTS}/{live['id']}")).status_code == 401
    assert (await submit(client, ctx, draft["id"])).status_code == 404

    published = await client.patch(f"{ASSIGNMENTS}/{draft['id']}", json={"state": "published"}, headers=ctx["teacher"])
    assert published.status_code == 200
    assert (await client.get(f"{ASSIGNMENTS}/{draft['id']}", headers=ctx["student"])).status_code == 200


# -------------------------------------------------------------------- todos
async def test_publish_creates_todo_for_every_student(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    ref = lambda aid: (TodoItem.ref_id == uuid.UUID(aid))  # noqa: E731

    draft = await create_assignment(client, ctx, published=False)
    assert await count(session_maker, TodoItem, ref(draft["id"])) == 0

    url = f"{ASSIGNMENTS}/{draft['id']}"
    await client.patch(url, json={"state": "published", "due_at": DUE}, headers=ctx["teacher"])
    assert await count(session_maker, TodoItem, ref(draft["id"])) == 2  # Sam + Cleo, not the teacher
    async with session_maker() as s:
        todos = (await s.scalars(select(TodoItem).where(ref(draft["id"])))).all()
        assert {t.user_id for t in todos} == {await user_id(client, ctx["student"]), await user_id(client, ctx["classmate"])}
        assert all(t.title == "HW 1" and t.due_at is not None and not t.is_done for t in todos)

    await client.patch(url, json={"state": "published"}, headers=ctx["teacher"])  # idempotent
    assert await count(session_maker, TodoItem, ref(draft["id"])) == 2

    await client.patch(url, json={"title": "Renamed"}, headers=ctx["teacher"])
    async with session_maker() as s:
        assert set((await s.scalars(select(TodoItem.title).where(ref(draft["id"])))).all()) == {"Renamed"}

    await client.patch(url, json={"state": "draft"}, headers=ctx["teacher"])
    assert await count(session_maker, TodoItem, ref(draft["id"])) == 0

    direct = await create_assignment(client, ctx)  # created already published
    assert await count(session_maker, TodoItem, ref(direct["id"])) == 2


# ------------------------------------------------------------------- update
async def test_update_rules(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    a = await create_assignment(client, ctx, due_at=DUE)
    url = f"{ASSIGNMENTS}/{a['id']}"
    teacher = ctx["teacher"]

    assert (await client.patch(url, json={"title": "X"}, headers=ctx["student"])).status_code == 403
    assert (await client.patch(url, json={"title": "X"}, headers=ctx["outsider"])).status_code == 404
    assert (await client.patch(url, json={}, headers=teacher)).status_code == 422
    assert (await client.patch(url, json={"title": None}, headers=teacher)).status_code == 422
    assert (await client.patch(url, json={"state": None}, headers=teacher)).status_code == 422

    ok = await client.patch(url, json={"title": " New ", "due_at": None, "description": "  "}, headers=teacher)
    assert ok.status_code == 200
    assert ok.json()["title"] == "New" and ok.json()["due_at"] is None and ok.json()["description"] is None

    # max_points / draft revert are blocked once students have work
    assert (await submit(client, ctx, a["id"])).status_code == 200
    assert (await client.patch(url, json={"state": "draft"}, headers=teacher)).status_code == 409
    sub_id = (await client.get(f"{url}/submissions", headers=teacher)).json()["items"][0]["id"]
    await client.patch(f"{SUBMISSIONS}/{sub_id}/grade", json={"grade": 45}, headers=teacher)
    assert (await client.patch(url, json={"max_points": 40}, headers=teacher)).status_code == 409
    assert (await client.patch(url, json={"max_points": 60}, headers=teacher)).status_code == 200


# ------------------------------------------------------------------- delete
async def test_delete_cascades(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    a = await create_assignment(client, ctx)
    await submit(client, ctx, a["id"])
    await client.post(
        f"{API}/comments",
        json={"target_type": "assignment", "target_id": a["id"], "body": "question"},
        headers=ctx["classmate"],
    )
    url = f"{ASSIGNMENTS}/{a['id']}"

    assert (await client.delete(url, headers=ctx["student"])).status_code == 403
    assert (await client.delete(url, headers=ctx["outsider"])).status_code == 404
    assert (await client.delete(url, headers=ctx["teacher"])).status_code == 204
    assert (await client.get(url, headers=ctx["teacher"])).status_code == 404
    assert (await client.delete(url, headers=ctx["teacher"])).status_code == 404

    aid = uuid.UUID(a["id"])
    assert await count(session_maker, Submission, Submission.assignment_id == aid) == 0
    assert await count(session_maker, TodoItem, TodoItem.ref_id == aid) == 0
    assert await count(session_maker, Comment, Comment.target_id == aid) == 0


# ------------------------------------------------------------------- submit
async def test_submit_resubmit_and_teacher_listing(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    a = await create_assignment(client, ctx)

    first = await submit(client, ctx, a["id"])
    assert first.status_code == 200, first.text
    sub = first.json()
    assert sub["state"] == "turned_in" and sub["content"] == "My answer"
    assert sub["submitted_at"] and sub["grade"] is None and sub["student"]["full_name"] == "Sam"

    teacher_id = await user_id(client, ctx["teacher"])
    async with session_maker() as s:
        notes = (await s.scalars(select(Notification).where(Notification.user_id == teacher_id))).all()
    assert len(notes) == 1 and notes[0].type == "submission_turned_in" and "Sam" in notes[0].title
    assert notes[0].link == f"/classrooms/{ctx['cid']}/assignments/{a['id']}" and not notes[0].is_read

    again = await submit(client, ctx, a["id"], content="Updated answer")
    assert again.status_code == 200 and again.json()["id"] == sub["id"]
    assert again.json()["content"] == "Updated answer"
    assert await count(session_maker, Submission, Submission.assignment_id == uuid.UUID(a["id"])) == 1

    listing = (await client.get(f"{ASSIGNMENTS}/{a['id']}/submissions", headers=ctx["teacher"])).json()
    assert listing["total"] == 1 and listing["not_submitted_count"] == 1  # Cleo has not submitted
    assert listing["items"][0]["student"]["full_name"] == "Sam"
    assert "email" not in listing["items"][0]["student"]

    await submit(client, ctx, a["id"], who="classmate", content="Cleo's work")
    listing = (await client.get(f"{ASSIGNMENTS}/{a['id']}/submissions", headers=ctx["teacher"])).json()
    assert [i["student"]["full_name"] for i in listing["items"]] == ["Cleo", "Sam"]  # sorted by name
    assert listing["not_submitted_count"] == 0
    filtered = (await client.get(f"{ASSIGNMENTS}/{a['id']}/submissions", params={"state": "graded"}, headers=ctx["teacher"])).json()
    assert filtered["total"] == 0

    assert (await client.get(f"{ASSIGNMENTS}/{a['id']}/submissions", headers=ctx["student"])).status_code == 403
    assert (await client.get(f"{ASSIGNMENTS}/{a['id']}/submissions", headers=ctx["outsider"])).status_code == 404


async def test_submit_validation_and_roles(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    a = await create_assignment(client, ctx)
    url = f"{ASSIGNMENTS}/{a['id']}/submit"

    assert (await client.post(url, json={}, headers=ctx["student"])).status_code == 422
    assert (await client.post(url, json={"content": "   "}, headers=ctx["student"])).status_code == 422
    assert (await client.post(url, json={"content": "x", "grade": 50}, headers=ctx["student"])).status_code == 422
    assert (await submit(client, ctx, a["id"], who="teacher")).status_code == 403
    assert (await submit(client, ctx, a["id"], who="outsider")).status_code == 404
    assert (await client.post(url, json={"content": "x"})).status_code == 401


async def test_my_submission(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    a = await create_assignment(client, ctx)
    url = f"{ASSIGNMENTS}/{a['id']}/my-submission"

    empty = await client.get(url, headers=ctx["student"])
    assert empty.status_code == 200 and empty.json() is None
    await submit(client, ctx, a["id"])
    mine = (await client.get(url, headers=ctx["student"])).json()
    assert mine["state"] == "turned_in" and mine["content"] == "My answer"
    assert (await client.get(url, headers=ctx["classmate"])).json() is None  # not someone else's
    assert (await client.get(url, headers=ctx["teacher"])).status_code == 403
    assert (await client.get(url, headers=ctx["outsider"])).status_code == 404


# -------------------------------------------------------- grade and return
async def test_grade_return_lifecycle(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    a = await create_assignment(client, ctx)  # max 50 points
    sub = (await submit(client, ctx, a["id"])).json()
    grade_url, return_url = f"{SUBMISSIONS}/{sub['id']}/grade", f"{SUBMISSIONS}/{sub['id']}/return"
    mine_url = f"{ASSIGNMENTS}/{a['id']}/my-submission"
    teacher, student = ctx["teacher"], ctx["student"]

    # permissions + validation
    assert (await client.patch(grade_url, json={"grade": 10}, headers=student)).status_code == 403
    assert (await client.patch(grade_url, json={"grade": 10}, headers=ctx["classmate"])).status_code == 403
    assert (await client.patch(grade_url, json={"grade": 10}, headers=ctx["outsider"])).status_code == 404
    assert (await client.patch(grade_url, json={"grade": 10})).status_code == 401
    assert (await client.patch(f"{SUBMISSIONS}/{uuid.uuid4()}/grade", json={"grade": 1}, headers=teacher)).status_code == 404
    assert (await client.patch(grade_url, json={"grade": 51}, headers=teacher)).status_code == 422  # > max
    assert (await client.patch(grade_url, json={"grade": -1}, headers=teacher)).status_code == 422
    assert (await client.patch(grade_url, json={"grade": "abc"}, headers=teacher)).status_code == 422
    assert (await client.patch(grade_url, json={}, headers=teacher)).status_code == 422

    # grading: teacher sees it, the student does not
    graded = await client.patch(grade_url, json={"grade": 45, "feedback": "Well done"}, headers=teacher)
    assert graded.status_code == 200, graded.text
    g = graded.json()
    assert g["state"] == "graded" and g["grade"] == 45 and g["feedback"] == "Well done" and g["graded_at"]
    hidden = (await client.get(mine_url, headers=student)).json()
    assert hidden["state"] == "turned_in" and hidden["grade"] is None and hidden["feedback"] is None
    assert (await submit(client, ctx, a["id"], content="late edit")).status_code == 409  # graded: no edits
    listing = (await client.get(f"{ASSIGNMENTS}/{a['id']}/submissions", headers=teacher)).json()
    assert listing["items"][0]["state"] == "graded" and listing["items"][0]["grade"] == 45

    # return: now the student sees everything + gets notified
    returned = await client.patch(return_url, headers=teacher)  # body is optional
    assert returned.status_code == 200 and returned.json()["state"] == "returned"
    seen = (await client.get(mine_url, headers=student)).json()
    assert seen["state"] == "returned" and seen["grade"] == 45 and seen["feedback"] == "Well done"
    student_id = await user_id(client, student)
    async with session_maker() as s:
        notes = (await s.scalars(select(Notification).where(Notification.user_id == student_id))).all()
    assert [n.type for n in notes] == ["submission_returned"]
    assert (await client.patch(return_url, headers=teacher)).status_code == 409  # already returned

    # regrade after return is visible immediately and keeps the state
    regraded = await client.patch(grade_url, json={"grade": 40}, headers=teacher)
    assert regraded.json()["state"] == "returned"
    assert (await client.get(mine_url, headers=student)).json()["grade"] == 40

    # student resubmits after a return -> back to turned_in, grade cleared
    again = await submit(client, ctx, a["id"], content="Second try")
    assert again.status_code == 200
    assert again.json()["state"] == "turned_in" and again.json()["grade"] is None


async def test_return_with_feedback_only_and_blank_clears(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    a = await create_assignment(client, ctx)
    sub = (await submit(client, ctx, a["id"])).json()
    teacher = ctx["teacher"]

    resp = await client.patch(
        f"{SUBMISSIONS}/{sub['id']}/return", json={"feedback": "Please add sources"}, headers=teacher
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "returned" and resp.json()["grade"] is None
    assert resp.json()["feedback"] == "Please add sources"

    cleared = await client.patch(f"{SUBMISSIONS}/{sub['id']}/grade", json={"grade": 10, "feedback": ""}, headers=teacher)
    assert cleared.json()["feedback"] is None


# -------------------------------------------------------------- attachments
async def test_attachments_ownership_and_access(client: AsyncClient, storage: LocalStorage, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    teacher_file = await upload_pdf(client, ctx["teacher"], "worksheet.pdf")
    ref = {"file_id": teacher_file["id"], "name": "client-says-this.pdf"}

    a = await create_assignment(client, ctx, attachments=[ref])
    assert a["attachments"][0]["name"] == "worksheet.pdf"  # name comes from the DB, not the client
    assert (await client.get(teacher_file["download_url"], headers=ctx["student"])).status_code == 200
    assert (await client.get(teacher_file["download_url"], headers=ctx["outsider"])).status_code == 404

    # a student cannot attach somebody else's file to their submission
    stolen = await submit(client, ctx, a["id"], attachments=[ref])
    assert stolen.status_code == 422

    mine = await upload_pdf(client, ctx["student"], "answer.pdf")
    ok = await submit(client, ctx, a["id"], content=None, attachments=[{"file_id": mine["id"], "name": "x.pdf"}])
    assert ok.status_code == 200 and ok.json()["attachments"][0]["name"] == "answer.pdf"
    assert (await client.get(mine["download_url"], headers=ctx["teacher"])).status_code == 200  # grading
    assert (await client.get(mine["download_url"], headers=ctx["classmate"])).status_code == 404

    # a co-teacher can edit while keeping the owner's attachment
    carl = await make_user(client, "carl@example.com", "teacher")
    await add_teacher(session_maker, ctx["cid"], await user_id(client, carl))
    keep = await client.patch(f"{ASSIGNMENTS}/{a['id']}", json={"attachments": [ref], "title": "By Carl"}, headers=carl)
    assert keep.status_code == 200 and keep.json()["attachments"][0]["name"] == "worksheet.pdf"
    # ...but cannot attach a file they do not own
    other = await upload_pdf(client, ctx["teacher"], "other.pdf")
    bad = await client.patch(f"{ASSIGNMENTS}/{a['id']}", json={"attachments": [{"file_id": other["id"], "name": "o.pdf"}]}, headers=carl)
    assert bad.status_code == 422

    # attached files cannot be deleted (STEP 7 rule)
    assert (await client.delete(teacher_file["download_url"], headers=ctx["teacher"])).status_code == 409


# ----------------------------------------------------------------- archived
async def test_archived_classroom_is_read_only(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    a = await create_assignment(client, ctx)
    sub = (await submit(client, ctx, a["id"])).json()
    await client.patch(f"{API}/classrooms/{ctx['cid']}", json={"is_archived": True}, headers=ctx["teacher"])
    teacher = ctx["teacher"]

    assert (await client.post(cls_url(ctx), json={"title": "x"}, headers=teacher)).status_code == 403
    assert (await client.patch(f"{ASSIGNMENTS}/{a['id']}", json={"title": "x"}, headers=teacher)).status_code == 403
    assert (await client.delete(f"{ASSIGNMENTS}/{a['id']}", headers=teacher)).status_code == 403
    assert (await submit(client, ctx, a["id"], content="late")).status_code == 403
    assert (await client.patch(f"{SUBMISSIONS}/{sub['id']}/grade", json={"grade": 5}, headers=teacher)).status_code == 403
    assert (await client.patch(f"{SUBMISSIONS}/{sub['id']}/return", headers=teacher)).status_code == 403
    assert (await client.get(cls_url(ctx), headers=ctx["student"])).status_code == 200  # reads still work
    assert (await client.get(f"{ASSIGNMENTS}/{a['id']}/submissions", headers=teacher)).status_code == 200


# -------------------------------------------------------------------- admin
async def test_admin_manages_but_cannot_submit(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    admin = await make_user(client, "root@example.com")
    await promote_to_admin(session_maker, "root@example.com")

    created = await client.post(cls_url(ctx), json={"title": "By admin", "state": "published"}, headers=admin)
    assert created.status_code == 201, created.text
    aid = created.json()["id"]
    assert (await client.get(f"{ASSIGNMENTS}/{aid}/submissions", headers=admin)).status_code == 200
    assert (await client.post(f"{ASSIGNMENTS}/{aid}/submit", json={"content": "x"}, headers=admin)).status_code == 403