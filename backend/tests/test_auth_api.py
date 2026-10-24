"""Integration tests for the auth endpoints (requires the PostgreSQL test database)."""

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

from app.core.deps import require_role
from app.db.session import get_db
from app.models import User, UserRole

pytestmark = pytest.mark.asyncio

PASSWORD = "Passw0rdX"


def _payload(email: str = "ann@example.com", role: str = "student") -> dict:
    return {"email": email, "password": PASSWORD, "full_name": "Ann Lee", "role": role}


async def _login(client: AsyncClient, email: str = "ann@example.com") -> dict:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ register
async def test_register_success(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/register", json=_payload("Ann@Example.COM"))
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "ann@example.com" and body["role"] == "student"
    assert "password" not in body and "hashed_password" not in body


async def test_register_duplicate_email_case_insensitive(client: AsyncClient) -> None:
    assert (await client.post("/api/v1/auth/register", json=_payload("a@example.com"))).status_code == 201
    resp = await client.post("/api/v1/auth/register", json=_payload("A@EXAMPLE.com"))
    assert resp.status_code == 409


async def test_register_rejects_admin_weak_password_and_extra_fields(client: AsyncClient) -> None:
    assert (await client.post("/api/v1/auth/register", json=_payload(role="admin"))).status_code == 422
    weak = {**_payload(), "password": "weak"}
    assert (await client.post("/api/v1/auth/register", json=weak)).status_code == 422
    extra = {**_payload(), "is_active": False}
    assert (await client.post("/api/v1/auth/register", json=extra)).status_code == 422


# --------------------------------------------------------------------- login
async def test_login_success_and_failures(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=_payload())
    tokens = await _login(client)
    assert tokens["token_type"] == "bearer" and tokens["expires_in"] > 0

    wrong = await client.post("/api/v1/auth/login", json={"email": "ann@example.com", "password": "Wrong1234"})
    unknown = await client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()  # no account enumeration


async def test_disabled_account(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    await client.post("/api/v1/auth/register", json=_payload())
    tokens = await _login(client)
    async with session_maker() as s:
        await s.execute(update(User).where(User.email == "ann@example.com").values(is_active=False))
        await s.commit()

    resp = await client.post("/api/v1/auth/login", json={"email": "ann@example.com", "password": PASSWORD})
    assert resp.status_code == 403
    me = await client.get("/api/v1/auth/me", headers=_bearer(tokens["access_token"]))
    assert me.status_code == 401  # existing access tokens stop working immediately


# ------------------------------------------------------------------------ me
async def test_me(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=_payload())
    tokens = await _login(client)

    ok = await client.get("/api/v1/auth/me", headers=_bearer(tokens["access_token"]))
    assert ok.status_code == 200 and ok.json()["email"] == "ann@example.com"

    assert (await client.get("/api/v1/auth/me")).status_code == 401
    assert (await client.get("/api/v1/auth/me", headers=_bearer("garbage"))).status_code == 401
    # a refresh token must not work as an access token
    assert (await client.get("/api/v1/auth/me", headers=_bearer(tokens["refresh_token"]))).status_code == 401


# ------------------------------------------------------------------- refresh
async def test_refresh_rotates_and_detects_reuse(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=_payload())
    first = await _login(client)

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert resp.status_code == 200
    second = resp.json()
    assert second["refresh_token"] != first["refresh_token"]
    assert (await client.get("/api/v1/auth/me", headers=_bearer(second["access_token"]))).status_code == 200

    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert reuse.status_code == 401  # old token is revoked


async def test_refresh_rejects_access_token_and_garbage(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=_payload())
    tokens = await _login(client)
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})).status_code == 401
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": "x" * 40})).status_code == 401


# -------------------------------------------------------------------- logout
async def test_logout_revokes_refresh_token(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=_payload())
    tokens = await _login(client)

    out = await client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert out.status_code == 204
    again = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert again.status_code == 401
    # idempotent, even for junk tokens
    assert (await client.post("/api/v1/auth/logout", json={"refresh_token": "junk" * 5})).status_code == 204


# ------------------------------------------------------------- require_role
async def test_require_role(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    mini = FastAPI()

    @mini.get("/teachers-only")
    async def teachers_only(user: Annotated[User, Depends(require_role(UserRole.TEACHER))]) -> dict:
        return {"email": user.email}

    async def _get_db():  # noqa: ANN202
        async with session_maker() as session:
            yield session

    mini.dependency_overrides[get_db] = _get_db

    await client.post("/api/v1/auth/register", json=_payload("t@example.com", "teacher"))
    await client.post("/api/v1/auth/register", json=_payload("s@example.com", "student"))
    teacher = await _login(client, "t@example.com")
    student = await _login(client, "s@example.com")

    async with AsyncClient(transport=ASGITransport(app=mini), base_url="http://mini") as c:
        assert (await c.get("/teachers-only", headers=_bearer(teacher["access_token"]))).status_code == 200
        assert (await c.get("/teachers-only", headers=_bearer(student["access_token"]))).status_code == 403
        assert (await c.get("/teachers-only")).status_code == 401


def test_require_role_needs_a_role() -> None:
    with pytest.raises(ValueError):
        require_role()