"""Integration tests for /classrooms (needs the PostgreSQL test database)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.models import (
    Announcement,
    Assignment,
    ClassroomMember,
    MemberRole,
    User,
    UserRole,
)

pytestmark = pytest.mark.asyncio

PASSWORD = "Passw0rdX"
BASE = "/api/v1/classrooms"


# ------------------------------------------------------------------ helpers
async def make_user(client: AsyncClient, email: str, role: str = "student") -> dict[str, str]:
    """Register + log in; return the Authorization header."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": email.split("@")[0].title(),
            "role": role,
        },
    )
    assert reg.status_code == 201, reg.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def user_id(client: AsyncClient, headers: dict[str, str]) -> str:
    return (await client.get("/api/v1/auth/me", headers=headers)).json()["id"]


async def create_classroom(client: AsyncClient, headers: dict[str, str], name: str = "Math 101") -> dict:
    resp = await client.post(BASE, json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def join(client: AsyncClient, headers: dict[str, str], code: str):  # noqa: ANN201
    return await client.post(f"{BASE}/join", json={"join_code": code}, headers=headers)


# ------------------------------------------------------------------- create
async def test_teacher_creates_classroom(client: AsyncClient) -> None:
    teacher = await make_user(client, "tina@example.com", "teacher")
    body = await create_classroom(client, teacher)

    assert body["my_role"] == "teacher" and body["name"] == "Math 101"
    assert 6 <= len(body["join_code"]) <= 8 and body["join_code"].isalnum() and body["join_code"].isupper()

    people = (await client.get(f"{BASE}/{body['id']}/people", headers=teacher)).json()
    assert [t["user"]["full_name"] for t in people["teachers"]] == ["Tina"]
    assert people["students"] == []


async def test_only_teachers_can_create(client: AsyncClient) -> None:
    student = await make_user(client, "sam@example.com")
    teacher = await make_user(client, "tina@example.com", "teacher")
    assert (await client.post(BASE, json={"name": "X"}, headers=student)).status_code == 403
    assert (await client.post(BASE, json={"name": "X"})).status_code == 401
    assert (await client.post(BASE, json={"name": "   "}, headers=teacher)).status_code == 422
    assert (await client.post(BASE, json={"name": "X", "owner_id": str(uuid.uuid4())}, headers=teacher)).status_code == 422


async def test_join_code_collision_is_retried(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    teacher = await make_user(client, "tina@example.com", "teacher")
    first = await create_classroom(client, teacher, "A")
    codes = iter([first["join_code"], "ZZZZZZZ"])  # 1st attempt collides, 2nd is free
    monkeypatch.setattr("app.services.classroom_service.generate_join_code", lambda: next(codes))
    second = await create_classroom(client, teacher, "B")
    assert second["join_code"] == "ZZZZZZZ"


# --------------------------------------------------------------------- join
async def test_join_flow(client: AsyncClient) -> None:
    teacher = await make_user(client, "tina@example.com", "teacher")
    student = await make_user(client, "sam@example.com")
    classroom = await create_classroom(client, teacher)

    ok = await join(client, student, classroom["join_code"].lower())  # case-insensitive
    assert ok.status_code == 200
    assert ok.json()["my_role"] == "student" and ok.json()["join_code"] is None

    assert (await join(client, student, classroom["join_code"])).status_code == 409  # twice
    assert (await join(client, teacher, classroom["join_code"])).status_code == 409  # owner
    assert (await join(client, student, "NOPE999")).status_code == 404
    assert (await client.post(f"{BASE}/join", json={"join_code": "a!"}, headers=student)).status_code == 422


async def test_join_accepts_legacy_code_key(client: AsyncClient) -> None:
    teacher = await make_user(client, "tina@example.com", "teacher")
    student = await make_user(client, "sam@example.com")
    classroom = await create_classroom(client, teacher)
    resp = await client.post(f"{BASE}/join", json={"code": classroom["join_code"]}, headers=student)
    assert resp.status_code == 200


async def test_cannot_join_archived_classroom(client: AsyncClient) -> None:
    teacher = await make_user(client, "tina@example.com", "teacher")
    student = await make_user(client, "sam@example.com")
    classroom = await create_classroom(client, teacher)
    await client.patch(f"{BASE}/{classroom['id']}", json={"is_archived": True}, headers=teacher)
    assert (await join(client, student, classroom["join_code"])).status_code == 403


# --------------------------------------------------------------------- list
async def test_list_is_scoped_to_membership_and_hides_archived(client: AsyncClient) -> None:
    teacher = await make_user(client, "tina@example.com", "teacher")
    student = await make_user(client, "sam@example.com")
    outsider = await make_user(client, "olga@example.com")

    a = await create_classroom(client, teacher, "A")
    b = await create_classroom(client, teacher, "B")
    await join(client, student, a["join_code"])
    await client.patch(f"{BASE}/{b['id']}", json={"is_archived": True}, headers=teacher)

    mine = (await client.get(BASE, headers=teacher)).json()
    assert [c["name"] for c in mine] == ["A"] and mine[0]["join_code"] == a["join_code"]

    with_archived = (await client.get(BASE, params={"include_archived": True}, headers=teacher)).json()
    assert {c["name"] for c in with_archived} == {"A", "B"}
    assert len((await client.get(BASE, params={"include_archived": True, "limit": 1}, headers=teacher)).json()) == 1

    seen = (await client.get(BASE, headers=student)).json()
    assert [c["name"] for c in seen] == ["A"]
    assert seen[0]["my_role"] == "student" and seen[0]["join_code"] is None

    assert (await client.get(BASE, headers=outsider)).json() == []


# ---------------------------------------------------------------------- get
async def test_get_requires_membership(client: AsyncClient) -> None:
    teacher = await make_user(client, "tina@example.com", "teacher")
    student = await make_user(client, "sam@example.com")
    outsider = await make_user(client, "olga@example.com")
    classroom = await create_classroom(client, teacher)
    await join(client, student, classroom["join_code"])
    url = f"{BASE}/{classroom['id']}"

    assert (await client.get(url, headers=teacher)).json()["join_code"] == classroom["join_code"]
    assert (await client.get(url, headers=student)).json()["join_code"] is None
    assert (await client.get(url, headers=outsider)).status_code == 404
    assert (await client.get(f"{BASE}/{uuid.uuid4()}", headers=teacher)).status_code == 404
    assert (await client.get(f"{BASE}/not-a-uuid", headers=teacher)).status_code == 422
    assert (await client.get(url)).status_code == 401


# -------------------------------------------------------------------- patch
async def test_update_permissions_and_validation(client: AsyncClient) -> None:
    teacher = await make_user(client, "tina@example.com", "teacher")
    student = await make_user(client, "sam@example.com")
    classroom = await create_classroom(client, teacher)
    await join(client, student, classroom["join_code"])
    url = f"{BASE}/{classroom['id']}"

    assert (await client.patch(url, json={"name": "Hacked"}, headers=student)).status_code == 403

    resp = await client.patch(url, json={"name": " Physics ", "section": "B", "subject": "  "}, headers=teacher)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Physics" and body["section"] == "B" and body["subject"] is None

    assert (await client.patch(url, json={}, headers=teacher)).status_code == 422
    assert (await client.patch(url, json={"name": None}, headers=teacher)).status_code == 422
    assert (await client.patch(url, json={"owner_id": str(uuid.uuid4())}, headers=teacher)).status_code == 422


# ------------------------------------------------------------------- people
async def test_people_listing_hides_emails_and_sorts(client: AsyncClient) -> None:
    teacher = await make_user(client, "tina@example.com", "teacher")
    zed = await make_user(client, "zed@example.com")
    amy = await make_user(client, "amy@example.com")
    classroom = await create_classroom(client, teacher)
    for h in (zed, amy):
        await join(client, h, classroom["join_code"])

    resp = await client.get(f"{BASE}/{classroom['id']}/people", headers=zed)
    assert resp.status_code == 200
    people = resp.json()
    assert [s["user"]["full_name"] for s in people["students"]] == ["Amy", "Zed"]
    assert all("email" not in m["user"] for m in people["teachers"] + people["students"])


# -------------------------------------------------------------------- leave
async def test_leave(client: AsyncClient) -> None:
    teacher = await make_user(client, "tina@example.com", "teacher")
    student = await make_user(client, "sam@example.com")
    outsider = await make_user(client, "olga@example.com")
    classroom = await create_classroom(client, teacher)
    await join(client, student, classroom["join_code"])
    url = f"{BASE}/{classroom['id']}"

    assert (await client.post(f"{url}/leave", headers=teacher)).status_code == 409  # owner
    assert (await client.post(f"{url}/leave", headers=student)).status_code == 204
    assert (await client.get(url, headers=student)).status_code == 404  # access is gone
    assert (await client.post(f"{url}/leave", headers=student)).status_code == 404  # already left
    assert (await client.post(f"{url}/leave", headers=outsider)).status_code == 404
    assert (await join(client, student, classroom["join_code"])).status_code == 200  # can rejoin


# ------------------------------------------------------------------- delete
async def test_delete_is_owner_only_and_cascades(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    teacher = await make_user(client, "tina@example.com", "teacher")
    co_teacher = await make_user(client, "carl@example.com", "teacher")
    student = await make_user(client, "sam@example.com")
    classroom = await create_classroom(client, teacher)
    cid = uuid.UUID(classroom["id"])
    await join(client, student, classroom["join_code"])

    async with session_maker() as s:  # promote Carl to co-teacher + seed some content
        s.add(ClassroomMember(classroom_id=cid, user_id=uuid.UUID(await user_id(client, co_teacher)), role=MemberRole.TEACHER))
        s.add(Assignment(classroom_id=cid, title="HW1"))
        s.add(Announcement(classroom_id=cid, content="Hello"))
        await s.commit()

    url = f"{BASE}/{classroom['id']}"
    assert (await client.delete(url, headers=student)).status_code == 403
    assert (await client.delete(url, headers=co_teacher)).status_code == 403
    assert (await client.patch(url, json={"room": "12"}, headers=co_teacher)).status_code == 200  # co-teacher may edit

    assert (await client.delete(url, headers=teacher)).status_code == 204
    assert (await client.get(url, headers=teacher)).status_code == 404

    async with session_maker() as s:
        for model in (ClassroomMember, Assignment, Announcement):
            assert await s.scalar(select(func.count()).select_from(model)) == 0


# -------------------------------------------------------------------- admin
async def test_admin_can_manage_any_classroom(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    teacher = await make_user(client, "tina@example.com", "teacher")
    admin = await make_user(client, "root@example.com")
    async with session_maker() as s:  # role is read from the DB on every request
        await s.execute(update(User).where(User.email == "root@example.com").values(role=UserRole.ADMIN))
        await s.commit()

    classroom = await create_classroom(client, teacher)
    url = f"{BASE}/{classroom['id']}"

    got = await client.get(url, headers=admin)
    assert got.status_code == 200 and got.json()["my_role"] == "teacher" and got.json()["join_code"]
    assert (await client.patch(url, json={"name": "Renamed"}, headers=admin)).status_code == 200
    assert (await client.post(f"{url}/leave", headers=admin)).status_code == 404  # not a member
    assert (await client.delete(url, headers=admin)).status_code == 204