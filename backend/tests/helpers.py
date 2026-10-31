"""Shared helpers for API integration tests: ``from tests.helpers import ...``."""

from __future__ import annotations

import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import update

from app.models import ClassroomMember, MemberRole, User, UserRole

PASSWORD = "Passw0rdX"
API = "/api/v1"


async def make_user(client: AsyncClient, email: str, role: str = "student") -> dict[str, str]:
    """Register + log in; return the Authorization header."""
    reg = await client.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": email.split("@")[0].title(),
            "role": role,
        },
    )
    assert reg.status_code == 201, reg.text
    login = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def user_id(client: AsyncClient, headers: dict[str, str]) -> uuid.UUID:
    resp = await client.get(f"{API}/auth/me", headers=headers)
    return uuid.UUID(resp.json()["id"])


async def classroom_context(client: AsyncClient) -> dict[str, Any]:
    """Teacher Tina owns 'Math 101'; Sam and Cleo are students in it; Olga is an outsider."""
    teacher = await make_user(client, "tina@example.com", "teacher")
    student = await make_user(client, "sam@example.com")
    classmate = await make_user(client, "cleo@example.com")
    outsider = await make_user(client, "olga@example.com")

    resp = await client.post(f"{API}/classrooms", json={"name": "Math 101"}, headers=teacher)
    assert resp.status_code == 201, resp.text
    classroom = resp.json()
    for headers in (student, classmate):
        joined = await client.post(
            f"{API}/classrooms/join", json={"join_code": classroom["join_code"]}, headers=headers
        )
        assert joined.status_code == 200, joined.text
    return {
        "teacher": teacher,
        "student": student,
        "classmate": classmate,
        "outsider": outsider,
        "cid": uuid.UUID(classroom["id"]),
    }


async def promote_to_admin(session_maker: Any, email: str) -> None:
    """The role is read from the DB on every request, so this applies immediately."""
    async with session_maker() as s:
        await s.execute(update(User).where(User.email == email).values(role=UserRole.ADMIN))
        await s.commit()


async def add_teacher(session_maker: Any, classroom_id: uuid.UUID, uid: uuid.UUID) -> None:
    """Make ``uid`` a co-teacher of a classroom."""
    async with session_maker() as s:
        s.add(ClassroomMember(classroom_id=classroom_id, user_id=uid, role=MemberRole.TEACHER))
        await s.commit()