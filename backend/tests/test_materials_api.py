"""Integration tests for /classrooms/{id}/materials (needs the PostgreSQL test database)."""

import uuid
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1.routers.files import get_storage_backend
from app.main import app
from app.models import Notification
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

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


def base(ctx: dict[str, Any]) -> str:
    return f"{API}/classrooms/{ctx['cid']}/materials"


async def post_material(
    client: AsyncClient, ctx: dict[str, Any], title: str = "Slides", **extra: Any
) -> dict[str, Any]:
    resp = await client.post(base(ctx), json={"title": title, **extra}, headers=ctx["teacher"])
    assert resp.status_code == 201, resp.text
    return resp.json()


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


# ------------------------------------------------------------ create + read
async def test_teacher_posts_and_members_read(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    resp = await client.post(
        base(ctx),
        json={"title": "  Week 1 slides  ", "description": "Read before class"},
        headers=ctx["teacher"],
    )
    assert resp.status_code == 201, resp.text
    material = resp.json()
    assert material["title"] == "Week 1 slides" and material["description"] == "Read before class"
    assert material["classroom_id"] == str(ctx["cid"]) and material["attachments"] == []

    for who in ("teacher", "student", "classmate"):
        listing = (await client.get(base(ctx), headers=ctx[who])).json()
        assert listing["total"] == 1 and listing["items"][0]["id"] == material["id"], who
        one = await client.get(f"{base(ctx)}/{material['id']}", headers=ctx[who])
        assert one.status_code == 200 and one.json()["title"] == "Week 1 slides"

    assert (await client.get(base(ctx), headers=ctx["outsider"])).status_code == 404
    assert (await client.get(f"{base(ctx)}/{material['id']}", headers=ctx["outsider"])).status_code == 404
    assert (await client.get(base(ctx))).status_code == 401


async def test_permissions_and_validation(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    material = await post_material(client, ctx)
    item = f"{base(ctx)}/{material['id']}"
    teacher = ctx["teacher"]

    assert (await client.post(base(ctx), json={"title": "x"}, headers=ctx["student"])).status_code == 403
    assert (await client.patch(item, json={"title": "x"}, headers=ctx["student"])).status_code == 403
    assert (await client.delete(item, headers=ctx["student"])).status_code == 403
    assert (await client.post(base(ctx), json={"title": "x"}, headers=ctx["outsider"])).status_code == 404
    assert (await client.post(base(ctx), json={"title": "x"})).status_code == 401

    assert (await client.post(base(ctx), json={"title": "   "}, headers=teacher)).status_code == 422
    assert (await client.post(base(ctx), json={"title": "x" * 256}, headers=teacher)).status_code == 422
    assert (await client.post(base(ctx), json={"title": "x", "classroom_id": str(uuid.uuid4())}, headers=teacher)).status_code == 422
    dup = {"file_id": str(uuid.uuid4()), "name": "a.pdf"}
    assert (await client.post(base(ctx), json={"title": "x", "attachments": [dup, dup]}, headers=teacher)).status_code == 422
    unknown = {"title": "x", "attachments": [{"file_id": str(uuid.uuid4()), "name": "a.pdf"}]}
    assert (await client.post(base(ctx), json=unknown, headers=teacher)).status_code == 422

    assert (await client.get(f"{base(ctx)}/{uuid.uuid4()}", headers=teacher)).status_code == 404
    assert (await client.get(f"{base(ctx)}/not-a-uuid", headers=teacher)).status_code == 422


async def test_list_order_pagination_and_scope(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    for title in ("one", "two", "three"):
        await post_material(client, ctx, title)
    full = (await client.get(base(ctx), headers=ctx["student"])).json()
    assert [m["title"] for m in full["items"]] == ["three", "two", "one"] and full["total"] == 3
    page = (await client.get(base(ctx), params={"limit": 2, "offset": 1}, headers=ctx["student"])).json()
    assert [m["title"] for m in page["items"]] == ["two", "one"]
    assert (await client.get(base(ctx), params={"limit": 0}, headers=ctx["student"])).status_code == 422

    other = (await client.post(f"{API}/classrooms", json={"name": "Other"}, headers=ctx["teacher"])).json()
    wrong = f"{API}/classrooms/{other['id']}/materials/{full['items'][0]['id']}"
    assert (await client.get(wrong, headers=ctx["teacher"])).status_code == 404  # wrong classroom
    assert (await client.delete(wrong, headers=ctx["teacher"])).status_code == 404


# ------------------------------------------------------------ update/delete
async def test_update_and_delete(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    material = await post_material(client, ctx, description="old")
    item = f"{base(ctx)}/{material['id']}"
    teacher = ctx["teacher"]

    assert (await client.patch(item, json={}, headers=teacher)).status_code == 422
    assert (await client.patch(item, json={"title": None}, headers=teacher)).status_code == 422
    assert (await client.patch(item, json={"attachments": None}, headers=teacher)).status_code == 422

    ok = await client.patch(item, json={"title": " New ", "description": "  "}, headers=teacher)
    assert ok.status_code == 200, ok.text
    assert ok.json()["title"] == "New" and ok.json()["description"] is None
    assert ok.json()["updated_at"] >= ok.json()["created_at"]

    assert (await client.delete(item, headers=teacher)).status_code == 204
    assert (await client.get(item, headers=teacher)).status_code == 404
    assert (await client.delete(item, headers=teacher)).status_code == 404


# ------------------------------------------------------------ notifications
async def test_students_are_notified(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    material = await post_material(client, ctx, "Syllabus")

    async with session_maker() as s:
        notes = (await s.scalars(select(Notification).order_by(Notification.created_at))).all()
    assert len(notes) == 2  # Sam and Cleo, not the teacher
    assert {n.user_id for n in notes} == {
        await user_id(client, ctx["student"]),
        await user_id(client, ctx["classmate"]),
    }
    assert all(
        n.type == "material_posted"
        and n.title == "New material: Syllabus"
        and n.link == f"/classrooms/{ctx['cid']}/materials/{material['id']}"
        and not n.is_read
        for n in notes
    )
    mine = (await client.get(f"{API}/notifications", headers=ctx["student"])).json()
    assert mine["total"] == 1 and mine["unread_count"] == 1


# -------------------------------------------------------------- attachments
async def test_attachments(client: AsyncClient, storage: LocalStorage, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    teacher_file = await upload_pdf(client, ctx["teacher"], "reading.pdf")
    ref = {"file_id": teacher_file["id"], "name": "client-says-this.pdf"}

    material = await post_material(client, ctx, "Reading", attachments=[ref])
    assert material["attachments"][0]["name"] == "reading.pdf"  # name comes from the DB
    assert (await client.get(teacher_file["download_url"], headers=ctx["student"])).status_code == 200
    assert (await client.get(teacher_file["download_url"], headers=ctx["outsider"])).status_code == 404
    assert (await client.delete(teacher_file["download_url"], headers=ctx["teacher"])).status_code == 409

    # a co-teacher keeps the owner's attachment but cannot attach a file they do not own
    carl = await make_user(client, "carl@example.com", "teacher")
    await add_teacher(session_maker, ctx["cid"], await user_id(client, carl))
    item = f"{base(ctx)}/{material['id']}"
    keep = await client.patch(item, json={"attachments": [ref], "title": "By Carl"}, headers=carl)
    assert keep.status_code == 200 and keep.json()["attachments"][0]["name"] == "reading.pdf"
    other = await upload_pdf(client, ctx["teacher"], "other.pdf")
    bad = await client.patch(item, json={"attachments": [{"file_id": other["id"], "name": "o.pdf"}]}, headers=carl)
    assert bad.status_code == 422

    # detaching (or deleting the material) frees the file again
    assert (await client.patch(item, json={"attachments": []}, headers=ctx["teacher"])).json()["attachments"] == []
    assert (await client.delete(teacher_file["download_url"], headers=ctx["teacher"])).status_code == 204


# ----------------------------------------------------------------- archived
async def test_archived_classroom_is_read_only(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    material = await post_material(client, ctx)
    item = f"{base(ctx)}/{material['id']}"
    await client.patch(f"{API}/classrooms/{ctx['cid']}", json={"is_archived": True}, headers=ctx["teacher"])

    assert (await client.post(base(ctx), json={"title": "x"}, headers=ctx["teacher"])).status_code == 403
    assert (await client.patch(item, json={"title": "x"}, headers=ctx["teacher"])).status_code == 403
    assert (await client.delete(item, headers=ctx["teacher"])).status_code == 403
    assert (await client.get(base(ctx), headers=ctx["student"])).status_code == 200


# -------------------------------------------------------------------- admin
async def test_admin_can_post_without_being_a_member(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    admin = await make_user(client, "root@example.com")
    await promote_to_admin(session_maker, "root@example.com")
    resp = await client.post(base(ctx), json={"title": "By admin"}, headers=admin)
    assert resp.status_code == 201, resp.text