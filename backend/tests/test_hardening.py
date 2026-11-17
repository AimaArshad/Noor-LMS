"""Hardening: error envelope, request ids, logging, security headers, rate limits, pagination, OpenAPI."""

import logging
import re

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from limits import parse
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.core.config import settings
from app.core.middleware import SecurityHeadersMiddleware
from app.core.rate_limit import limiter
from app.main import app as global_app
from app.main import create_app
from tests.helpers import API, PASSWORD, classroom_context, make_user


@pytest_asyncio.fixture
async def bare():  # noqa: ANN201
    """A fresh app (same middleware and handlers) with a route that crashes. No database needed."""
    app = create_app()

    @app.get("/__boom")
    async def boom() -> None:
        raise RuntimeError("secret internals")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ----------------------------------------------------------- error envelope
async def test_unknown_route_uses_the_envelope(bare: AsyncClient) -> None:
    resp = await bare.get("/nope")
    assert resp.status_code == 404
    assert resp.json() == {"error": {"code": "not_found", "message": "Not Found", "details": None}}


async def test_method_not_allowed(bare: AsyncClient) -> None:
    resp = await bare.post("/health")
    assert resp.status_code == 405 and resp.json()["error"]["code"] == "method_not_allowed"
    assert "allow" in resp.headers


async def test_http_exceptions_keep_their_headers(bare: AsyncClient) -> None:
    resp = await bare.get(f"{API}/auth/me")
    assert resp.status_code == 401 and resp.headers["www-authenticate"] == "Bearer"
    assert resp.json()["error"] == {
        "code": "unauthorized",
        "message": "Not authenticated",
        "details": None,
    }


async def test_validation_errors_list_every_problem_without_echoing_input(
    bare: AsyncClient,
) -> None:
    resp = await bare.post(f"{API}/auth/login", json={"password": "hunter2-secret"})
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "validation_error" and error["message"] == "Request validation failed"
    fields = {item["field"]: item for item in error["details"]}
    assert "email" in fields and fields["email"]["in"] == "body" and fields["email"]["message"]
    assert "hunter2-secret" not in resp.text  # the submitted value is never echoed back


async def test_unhandled_errors_are_hidden_but_logged(
    bare: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    origin = settings.CORS_ORIGINS[0]
    with caplog.at_level(logging.ERROR):
        resp = await bare.get("/__boom", headers={"Origin": origin})

    assert resp.status_code == 500
    assert resp.json() == {
        "error": {"code": "internal_error", "message": "Internal server error", "details": None}
    }
    assert "secret internals" not in resp.text and "RuntimeError" not in resp.text
    # even a crash carries a request id, security headers and CORS headers
    assert resp.headers["x-request-id"] and resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["access-control-allow-origin"] == origin

    crashes = [r for r in caplog.records if r.exc_info and "secret internals" in str(r.exc_info[1])]
    assert crashes and crashes[0].request_id == resp.headers["x-request-id"]


# ---------------------------------------------------------------- request id
async def test_request_id_is_generated_and_echoed(bare: AsyncClient) -> None:
    generated = (await bare.get("/health")).headers["x-request-id"]
    assert re.fullmatch(r"[0-9a-f]{32}", generated)

    echoed = await bare.get("/health", headers={"X-Request-ID": "client-id-12345"})
    assert echoed.headers["x-request-id"] == "client-id-12345"

    for bad in ("short", "has spaces in it!!", "a/b/c/d/e/f/g/h", "x" * 65):
        replaced = await bare.get("/health", headers={"X-Request-ID": bad})
        assert replaced.headers["x-request-id"] != bad
        assert re.fullmatch(r"[0-9a-f]{32}", replaced.headers["x-request-id"])


async def test_access_log_has_the_request_id_and_never_the_query_string(
    bare: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="educonnect.access"):
        resp = await bare.get("/nope?token=SUPERSECRET")

    records = [r for r in caplog.records if r.name == "educonnect.access"]
    assert len(records) == 1
    record = records[0]
    assert record.request_id == resp.headers["x-request-id"]
    assert (record.method, record.path, record.status) == ("GET", "/nope", 404)
    assert "SUPERSECRET" not in str(record.__dict__) and "SUPERSECRET" not in record.getMessage()


def test_json_formatter() -> None:
    import json

    from app.core.logging_config import JsonFormatter

    record = logging.LogRecord(
        "educonnect.test", logging.WARNING, __file__, 1, "hello %s", ("world",), None
    )
    record.request_id = "abc12345"
    record.status = 404  # an `extra=` field
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "hello world" and payload["level"] == "WARNING"
    assert payload["request_id"] == "abc12345" and payload["status"] == 404
    assert payload["ts"].endswith("+00:00")


# ---------------------------------------------------------- security headers
async def test_security_headers_on_api_responses(bare: AsyncClient) -> None:
    headers = (await bare.get("/health")).headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
    assert "camera=()" in headers["permissions-policy"]
    assert headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in headers  # not production


async def test_docs_get_a_relaxed_csp(bare: AsyncClient) -> None:
    resp = await bare.get("/docs")
    assert resp.status_code == 200
    csp = resp.headers["content-security-policy"]
    assert "cdn.jsdelivr.net" in csp and "default-src 'none'" not in csp


def _mini(hsts: bool) -> Starlette:
    async def page(_):  # noqa: ANN001, ANN202
        return PlainTextResponse("ok")

    async def download(_):  # noqa: ANN001, ANN202
        return PlainTextResponse("data", headers={"Cache-Control": "private, max-age=3600"})

    app = Starlette(routes=[Route("/", page), Route("/api/v1/files/x", download)])
    app.add_middleware(SecurityHeadersMiddleware, hsts=hsts, files_prefix="/api/v1/files/")
    return app


@pytest.mark.parametrize("hsts", [True, False])
async def test_hsts_follows_the_flag(hsts: bool) -> None:
    async with AsyncClient(transport=ASGITransport(app=_mini(hsts)), base_url="http://t") as c:
        resp = await c.get("/")
    assert ("strict-transport-security" in resp.headers) is hsts


async def test_downloads_keep_their_own_caching_and_get_no_csp() -> None:
    async with AsyncClient(transport=ASGITransport(app=_mini(False)), base_url="http://t") as c:
        resp = await c.get("/api/v1/files/x")
    assert resp.headers["cache-control"] == "private, max-age=3600"  # not overridden by no-store
    assert "content-security-policy" not in resp.headers
    assert resp.headers["x-content-type-options"] == "nosniff"


# ---------------------------------------------------------------- rate limits
async def test_auth_endpoints_are_rate_limited(client: AsyncClient) -> None:
    allowed = parse(settings.AUTH_RATE_LIMIT_LOGIN).amount
    body = {"email": "nobody@example.com", "password": PASSWORD}
    limiter.enabled = True  # the shared `client` fixture switches it off
    limiter.reset()
    try:
        for _ in range(allowed):
            assert (await client.post(f"{API}/auth/login", json=body)).status_code == 401
        blocked = await client.post(f"{API}/auth/login", json=body)
    finally:
        limiter.reset()
        limiter.enabled = False

    assert blocked.status_code == 429
    error = blocked.json()["error"]
    assert error["code"] == "rate_limited"
    assert 1 <= error["details"]["retry_after_seconds"] <= 60
    assert blocked.headers["retry-after"] == str(error["details"]["retry_after_seconds"])
    assert blocked.headers["x-request-id"]


# ----------------------------------------------------------------- sanitising
async def test_control_characters_never_reach_the_database(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    base = f"{API}/classrooms/{ctx['cid']}"
    teacher = ctx["teacher"]

    posted = await client.post(
        f"{base}/announcements",
        json={"content": "Hello\u0000 wor\u202eld\r\nline two\u0007"},
        headers=teacher,
    )
    assert posted.status_code == 201, posted.text  # a NUL used to make PostgreSQL fail with a 500
    assert posted.json()["content"] == "Hello world\nline two"

    assignment = await client.post(
        f"{base}/assignments", json={"title": "Line\none\u0000"}, headers=teacher
    )
    assert assignment.status_code == 201 and assignment.json()["title"] == "Line one"


# ----------------------------------------------------------------- pagination
async def test_classroom_list_reports_the_total_in_a_header(client: AsyncClient) -> None:
    teacher = await make_user(client, "total@example.com", "teacher")
    for i in range(3):
        created = await client.post(
            f"{API}/classrooms", json={"name": f"Class {i}"}, headers=teacher
        )
        assert created.status_code == 201, created.text

    first = await client.get(f"{API}/classrooms", params={"limit": 2}, headers=teacher)
    assert first.status_code == 200
    assert len(first.json()) == 2 and first.headers["x-total-count"] == "3"
    rest = await client.get(
        f"{API}/classrooms", params={"limit": 2, "offset": 2}, headers=teacher
    )
    assert len(rest.json()) == 1 and rest.headers["x-total-count"] == "3"

    for bad in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"offset": 100_001}):
        assert (
            await client.get(f"{API}/classrooms", params=bad, headers=teacher)
        ).status_code == 422


async def test_people_students_are_paginated(client: AsyncClient) -> None:
    teacher = await make_user(client, "owner@example.com", "teacher")
    created = await client.post(
        f"{API}/classrooms", json={"name": "Paged"}, headers=teacher
    )
    assert created.status_code == 201, created.text
    classroom = created.json()
    cid = classroom["id"]

    for i in range(3):
        student = await make_user(client, f"pupil{i}@example.com")
        joined = await client.post(
            f"{API}/classrooms/join",
            json={"join_code": classroom["join_code"]},
            headers=student,
        )
        assert joined.status_code == 200, joined.text

    url = f"{API}/classrooms/{cid}/people"
    first = (await client.get(url, params={"limit": 2}, headers=teacher)).json()
    assert len(first["students"]) == 2 and first["students_total"] == 3
    assert len(first["teachers"]) == 1 and first["limit"] == 2 and first["offset"] == 0

    last = (await client.get(url, params={"limit": 2, "offset": 2}, headers=teacher)).json()
    assert len(last["students"]) == 1 and len(last["teachers"]) == 1  # teachers always listed

    assert (await client.get(url, params={"limit": 0}, headers=teacher)).status_code == 422
    assert (await client.get(url, params={"limit": 101}, headers=teacher)).status_code == 422


def test_every_limit_parameter_in_the_api_is_bounded() -> None:
    spec = global_app.openapi()
    found = 0
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            for param in operation.get("parameters", []):
                schema = param["schema"]
                if param["name"] == "limit":
                    found += 1
                    assert schema["minimum"] == 1 and schema["maximum"] <= 100, f"{method} {path}"
                if param["name"] == "offset":
                    assert schema["minimum"] == 0, f"{method} {path}"
    assert found >= 10  # every list endpoint


# ------------------------------------------------------------------- OpenAPI
def test_every_tag_is_declared_and_described() -> None:
    spec = global_app.openapi()
    declared = {tag["name"]: tag.get("description") for tag in spec["tags"]}
    used = {
        tag for item in spec["paths"].values() for op in item.values() for tag in op.get("tags", [])
    }
    assert used <= declared.keys()
    assert all(declared.values()), "every tag needs a description"


def test_errors_are_documented_with_the_envelope() -> None:
    spec = global_app.openapi()
    responses = spec["paths"]["/api/v1/auth/login"]["post"]["responses"]
    for code in ("401", "422", "429", "500"):
        ref = responses[code]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("/ErrorResponse"), code
    assert "Retry-After" in responses["429"]["headers"]
