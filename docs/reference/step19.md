```ts
STEP 19: Phase-1 hardening
What already existed. /auth/* already had slowapi limits, and every list endpoint except two was already limit/offset paginated. This step makes those consistent and configurable, and adds the missing pieces.
Breaking change: all errors now use one envelope.
{"error": {"code": "not_found", "message": "Classroom not found", "details": null}}
The old {"detail": "..."} shape is gone. I updated the frontend error helper and two backend tests that read detail.
Design decisions:
Middleware order (outermost first): request context, security headers, CORS, error boundary, upload guard, slowapi. 
oThe error boundary sits inside CORS and the header middleware. Unhandled 500s therefore still carry CORS headers, X-Request-ID and the security headers.
oStarlette's built-in 500 handler sits outside all of them and would drop all three.
Request IDs. 
oA client X-Request-ID is accepted only if it matches [A-Za-z0-9._-]{8,64}. Otherwise a UUID is generated.
oThe ID is returned as a header and put on every log line through a log-record factory. It is kept out of the JSON body so identical errors stay identical; the "no account enumeration" test depends on that.
Logging. 
oOutput is JSON in production and staging, and readable text elsewhere (LOG_FORMAT=auto|json|text).
oThere is one access-log line per request: method, path, status, duration and client IP. The query string is never logged, because the WebSocket ?token= option would leak tokens.
ouvicorn's own access log is disabled.
Validation errors never echo the submitted value. Pydantic's input field is dropped, so a rejected password never appears in a response.
Sanitization happens at the API boundary, in the Pydantic types. 
oApplied: Unicode NFC, \r\n→\n, removal of control characters, lone surrogates, zero-width spaces and bidi override characters.
oSingle-line fields collapse whitespace; multi-line fields keep \n and \t.
oNUL bytes previously caused a PostgreSQL error, so that request returned a 500. They are now stripped.
oZWNJ/ZWJ are kept because Persian and Urdu text needs them.
oHTML is not escaped on the way in. The defense is output escaping, which React does by default, and escaping twice corrupts data.
Pagination. 
oA shared dependency caps limit at 100 and offset at 100 000.
oGET /classrooms keeps its array body, so no client breaks. It gains an X-Total-Count header.
oGET /classrooms/{id}/people now pages its students (students_total, limit, offset). Teachers are always all returned.
oAn automated OpenAPI audit test checks that every limit parameter in the API is bounded.
Security headers: nosniff, X-Frame-Options: DENY, Referrer-Policy: no-referrer, a restrictive Permissions-Policy, Cache-Control: no-store on API responses, and HSTS in production only. 
oThe CSP is default-src 'none' for the API. A relaxed CSP applies to /docs and /redoc, which need the jsDelivr CDN. File downloads get no CSP.
oIn production the docs and openapi.json are both disabled.
Files in this step
backend/
├── .env.example                          ← EDIT   (new variables)
├── Dockerfile                            ← EDIT   (CMD flag)
├── app/
│   ├── main.py                           ← REPLACE
│   ├── core/
│   │   ├── config.py                     ← EDIT   (log + auth rate-limit settings)
│   │   ├── errors.py                     ← NEW    (envelope + handlers)
│   │   ├── logging_config.py             ← NEW    (request-id aware, JSON/text)
│   │   ├── middleware.py                 ← REPLACE (+ request context, security headers, error boundary)
│   │   ├── openapi.py                    ← NEW    (tags, description, common responses)
│   │   └── pagination.py                 ← NEW
│   ├── utils/sanitize.py                 ← NEW
│   ├── schemas/{common,classrooms}.py    ← REPLACE, EDIT
│   ├── services/classroom_service.py     ← EDIT   (count, paged people)
│   └── api/v1/routers/{auth,classrooms}.py ← REPLACE, EDIT
├── tests/
│   ├── test_hardening.py                 ← NEW
│   ├── test_sanitize.py                  ← NEW
│   ├── test_quizzes_api.py, test_quizzes.py ← EDIT (1 line each)
docker-compose.yml, docker-compose.dev.yml, .env.example, README.md ← EDIT
frontend/src/{api/errors.ts, api/errors.test.ts, types/index.ts,
              features/classrooms/api.ts, features/classrooms/components/PeopleList.tsx,
              pages/classroom/PeoplePage.tsx} ← REPLACE / EDIT
cd backend
touch app/core/{errors,logging_config,openapi,pagination}.py app/utils/sanitize.py
touch tests/{test_hardening,test_sanitize}.py
No new dependencies. limits ships with slowapi.
Backend: core
"""Text sanitisation for user-supplied strings.

Applied by the Pydantic string types in ``schemas/common.py``, i.e. at the API boundary.

Removed from every value:

* control characters (C0 / C1, including NUL: PostgreSQL rejects NUL in text columns),
* lone surrogates (cannot be encoded as UTF-8),
* zero-width space / word joiner / BOM, and the bidi *override* and *isolate* characters
  used for filename and text spoofing (``\u202e`` ...).

Deliberately KEPT: ZWNJ / ZWJ (U+200C / U+200D), which Persian, Urdu, Hindi and others need.

Line breaks are normalised to ``\\n``. Single-line fields collapse all whitespace runs to one
space; multi-line fields keep ``\\n`` and ``\\t``.

HTML is NOT escaped here: escaping belongs to the output side (React escapes by default),
and escaping on input corrupts data when it is escaped again on output.
"""

from __future__ import annotations

import unicodedata
from typing import Any

_DROP = frozenset(
    "\u200b\u2060\ufeff"  # zero-width space, word joiner, BOM
    "\u202a\u202b\u202c\u202d\u202e"  # bidi embeddings / overrides
    "\u2066\u2067\u2068\u2069"  # bidi isolates
)
_LINE_BREAKS = ("\r\n", "\r", "\u2028", "\u2029", "\x85")


def _clean(text: str, *, multiline: bool) -> str:
    text = unicodedata.normalize("NFC", text)
    for line_break in _LINE_BREAKS:
        text = text.replace(line_break, "\n")

    out: list[str] = []
    for char in text:
        if char == "\n":
            out.append("\n" if multiline else " ")
        elif char == "\t":
            out.append("\t" if multiline else " ")
        elif char in _DROP or unicodedata.category(char) in ("Cc", "Cs"):
            continue
        else:
            out.append(char)
    return "".join(out)


def clean_multiline(value: Any) -> Any:  # noqa: ANN401
    """Sanitise a multi-line text value. Non-strings are returned untouched (validation handles them)."""
    if not isinstance(value, str):
        return value
    return _clean(value, multiline=True)


def clean_line(value: Any) -> Any:  # noqa: ANN401
    """Sanitise a single-line value: also collapses every whitespace run into one space."""
    if not isinstance(value, str):
        return value
    return " ".join(_clean(value, multiline=False).split())
"""Structured, request-id aware logging (JSON or human-readable text)."""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

#: The id of the request being handled (set by ``RequestContextMiddleware``).
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

TEXT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(request_id)s | %(message)s"

# Attributes every LogRecord has; anything else was passed via `extra=` and goes into the JSON.
_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "taskName",
    "request_id",
}

_factory_installed = False


def _install_record_factory() -> None:
    """Give EVERY log record (ours and third-party) a ``request_id`` attribute."""
    global _factory_installed
    if _factory_installed:
        return
    previous = logging.getLogRecordFactory()

    def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:  # noqa: ANN401
        record = previous(*args, **kwargs)
        record.request_id = request_id_var.get() or "-"
        return record

    logging.setLogRecordFactory(factory)
    _factory_installed = True


class JsonFormatter(logging.Formatter):
    """One JSON object per line: ts, level, logger, message, request_id, extras, exc_info."""

    def format(self, record: logging.LogRecord) -> str:
        request_id = getattr(record, "request_id", "-")
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": None if request_id == "-" else request_id,
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def setup_logging(*, level: str, json_logs: bool) -> None:
    """Configure the root logger (stdout) and quiet uvicorn's duplicate access log."""
    _install_record_factory()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_logs else logging.Formatter(TEXT_FORMAT))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)

    # uvicorn: route its error log through our handler; our own access log replaces its one.
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
"""One error envelope for the whole API.

    {"error": {"code": "not_found", "message": "Classroom not found", "details": null}}

* ``code``    stable, machine-readable (clients branch on this)
* ``message`` human-readable (safe to show to users)
* ``details`` extra structured data: validation issues, retry hints; otherwise ``null``

The request id travels in the ``X-Request-ID`` response header, not in the body.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

CODE_BY_STATUS: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    416: "range_not_satisfiable",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "service_unavailable",
}

_SOURCES = {"body", "query", "path", "header", "cookie"}


def error_response(
    status_code: int,
    message: str,
    *,
    code: str | None = None,
    details: Any = None,  # noqa: ANN401
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build an envelope response."""
    body = {
        "error": {
            "code": code or CODE_BY_STATUS.get(status_code, f"http_{status_code}"),
            "message": message,
            "details": details,
        }
    }
    return JSONResponse(jsonable_encoder(body), status_code=status_code, headers=headers)


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> Response:
    """``HTTPException`` (ours and Starlette's 404 / 405) -> envelope. Keeps ``WWW-Authenticate`` etc."""
    if exc.status_code in {204, 304}:  # these must not have a body
        return Response(status_code=exc.status_code, headers=exc.headers)

    if isinstance(exc.detail, str):
        message, details = exc.detail, None
    else:  # a dict/list detail: keep it as structured details
        try:
            message = HTTPStatus(exc.status_code).phrase
        except ValueError:
            message = "Error"
        details = exc.detail
    return error_response(exc.status_code, message, details=details, headers=exc.headers)


def _clean_message(message: str) -> str:
    return message.removeprefix("Value error, ").removeprefix("Assertion failed, ")


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """422 with one entry per problem. The submitted value is NEVER echoed back (it may be a password)."""
    details: list[dict[str, Any]] = []
    for error in exc.errors():
        loc = list(error.get("loc", ()))
        source = str(loc.pop(0)) if loc and loc[0] in _SOURCES else None
        details.append(
            {
                "in": source,
                "field": ".".join(str(part) for part in loc) or None,
                "message": _clean_message(str(error.get("msg", "Invalid value"))),
                "type": error.get("type"),
            }
        )
    return error_response(422, "Request validation failed", code="validation_error", details=details)


def _retry_after(exc: RateLimitExceeded) -> int | None:
    """Length of the rate-limit window in seconds (an upper bound for when to retry)."""
    try:
        return int(exc.limit.limit.get_expiry())
    except Exception:  # noqa: BLE001 - never fail while reporting a failure
        return None


# NOTE: deliberately a plain `def`. slowapi's middleware calls the registered handler directly
# (without awaiting it); Starlette runs sync handlers in a thread pool for normal requests.
def rate_limit_exceeded_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
    retry_after = _retry_after(exc)
    return error_response(
        429,
        "Too many requests. Please wait a moment and try again.",
        details={"limit": str(exc.detail), "retry_after_seconds": retry_after},
        headers={"Retry-After": str(retry_after)} if retry_after else None,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Install the envelope handlers. Unhandled exceptions are handled by ``ErrorBoundaryMiddleware``."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
"""Pure-ASGI middleware.

Order used by ``create_app`` (outermost first):

    RequestContext -> SecurityHeaders -> CORS -> ErrorBoundary -> MaxBodySize -> SlowAPI -> app

ErrorBoundary sits INSIDE CORS and SecurityHeaders on purpose: Starlette's own 500 handler sits
outside every user middleware, so its responses would carry no CORS headers, no request id and
no security headers.
"""

from __future__ import annotations

import logging
import re
import time
import uuid

from fastapi import HTTPException, status
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response
from app.core.logging_config import request_id_var

access_logger = logging.getLogger("educonnect.access")
logger = logging.getLogger("educonnect")

_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9._-]{8,64}")


# --------------------------------------------------------------------------- #
# Request id + access log
# --------------------------------------------------------------------------- #
class RequestContextMiddleware:
    """Assigns a request id, echoes it as ``X-Request-ID`` and writes one access-log line.

    The query string is never logged (the WebSocket endpoint can receive ``?token=``).
    """

    QUIET_PREFIXES = ("/health",)  # probes are logged at DEBUG only

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-request-id")
        request_id = incoming if incoming and _REQUEST_ID_RE.fullmatch(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        scope.setdefault("state", {})["request_id"] = request_id

        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            method, path = scope["method"], scope["path"]
            client = scope.get("client")
            if status_code >= 500:
                level = logging.ERROR
            elif path.startswith(self.QUIET_PREFIXES):
                level = logging.DEBUG
            else:
                level = logging.INFO
            access_logger.log(
                level,
                "%s %s -> %s (%.1f ms)",
                method,
                path,
                status_code,
                duration_ms,
                extra={
                    "method": method,
                    "path": path,
                    "status": status_code,
                    "duration_ms": round(duration_ms, 1),
                    "client_ip": client[0] if client else None,
                },
            )
            request_id_var.reset(token)


# --------------------------------------------------------------------------- #
# Security headers
# --------------------------------------------------------------------------- #
_API_CSP = "default-src 'none'; frame-ancestors 'none'"
# Swagger UI and ReDoc load their assets from the jsDelivr CDN and use inline scripts/styles.
_DOCS_CSP = (
    "default-src 'self'; "
    "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.jsdelivr.net; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "worker-src blob:; connect-src 'self'; frame-ancestors 'none'"
)


class SecurityHeadersMiddleware:
    """Adds security headers to every HTTP response. Headers set by a route are never overridden."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        hsts: bool = False,
        files_prefix: str = "/api/v1/files/",
        relaxed_csp_paths: frozenset[str] | set[str] = frozenset(),
    ) -> None:
        self.app = app
        self.files_prefix = files_prefix
        self.relaxed_csp_paths = frozenset(relaxed_csp_paths)
        self._base = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }
        if hsts:
            self._base["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    def _headers_for(self, path: str) -> dict[str, str]:
        headers = dict(self._base)
        is_docs = path in self.relaxed_csp_paths
        is_file = path.startswith(self.files_prefix)
        if is_docs:
            headers["Content-Security-Policy"] = _DOCS_CSP
        elif not is_file:  # downloads keep their own caching rules and get no CSP
            headers["Content-Security-Policy"] = _API_CSP
            headers["Cache-Control"] = "no-store"  # tokens and personal data must not be cached
        return headers

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        extra = self._headers_for(scope["path"])

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in extra.items():
                    headers.setdefault(name, value)
            await send(message)

        await self.app(scope, receive, send_wrapper)


# --------------------------------------------------------------------------- #
# Error boundary
# --------------------------------------------------------------------------- #
class ErrorBoundaryMiddleware:
    """Turns any unhandled exception into the 500 envelope. Details go to the log, never to the client."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            logger.exception("Unhandled error on %s %s", scope["method"], scope["path"])
            if response_started:  # too late to change the response
                raise
            response = error_response(500, "Internal server error")
            await response(scope, receive, send)


# --------------------------------------------------------------------------- #
# Upload size guard
# --------------------------------------------------------------------------- #
def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


class MaxBodySizeMiddleware:
    """Return 413 for ``method path`` requests whose body exceeds ``max_bytes``.

    * A declared ``Content-Length`` that is too large is rejected immediately.
    * Chunked bodies (no ``Content-Length``) are counted while they stream in, and
      abort with 413 as soon as the limit is crossed.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int, path: str, method: str = "POST") -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.path = path
        self.method = method

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != self.method or scope["path"] != self.path:
            await self.app(scope, receive, send)
            return

        declared = _content_length(scope)
        if declared is not None and declared > self.max_bytes:
            response = error_response(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Request body too large")
            await response(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # FastAPI re-raises HTTPExceptions that come out of body parsing.
                    raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Request body too large")
            return message

        await self.app(scope, limited_receive, send)
"""Shared ``limit`` / ``offset`` query parameters.

Every list endpoint accepts ``limit`` (1-100) and ``offset`` (0-100000). Use as a dependency::

    async def list_things(page: PageParams): ...   # page.limit, page.offset
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query

MAX_LIMIT = 100
MAX_OFFSET = 100_000  # deep offsets make PostgreSQL scan and discard rows


@dataclass(frozen=True, slots=True)
class Pagination:
    limit: int
    offset: int


def pagination(default_limit: int = 50):  # noqa: ANN201 - returns a FastAPI dependency
    """Dependency factory with a per-endpoint default page size."""

    def dependency(
        limit: Annotated[int, Query(ge=1, le=MAX_LIMIT, description=f"Page size (1-{MAX_LIMIT}).")] = default_limit,
        offset: Annotated[int, Query(ge=0, le=MAX_OFFSET, description="Number of items to skip.")] = 0,
    ) -> Pagination:
        return Pagination(limit=limit, offset=offset)

    return dependency


PageParams = Annotated[Pagination, Depends(pagination())]
#: People lists default to a larger page.
PeoplePageParams = Annotated[Pagination, Depends(pagination(100))]
"""OpenAPI metadata for /docs: description, tag descriptions and the shared error responses."""

from app.schemas.common import ErrorResponse

API_DESCRIPTION = """
Backend of **EduConnect**, a Google Classroom-style platform: classes, announcements, assignments
with grading, auto-graded quizzes, materials, file uploads, a to-do list and live notifications.

## Authentication
`POST /auth/login` returns an access token (15 minutes) and a refresh token (7 days).
Send the access token as `Authorization: Bearer <token>`; use **Authorize** above to try requests.
Refresh tokens **rotate**: every `POST /auth/refresh` revokes the token it receives.

## Errors
Every error has the same shape:

```json
{"error": {"code": "not_found", "message": "Classroom not found", "details": null}}
details carries a list of {in, field, message, type} for 422 validation_error, and
{limit, retry_after_seconds} for 429 rate_limited. Codes are stable; messages are for people.
Users who are not members of a classroom get 404, not 403, so ids cannot be probed.
Request ids
Every response has an X-Request-ID header (send your own, 8-64 chars of A-Za-z0-9._-, to
correlate logs). Quote it when reporting a problem.
Pagination
List endpoints take limit (1-100) and offset. Page responses are
{items, total, limit, offset}. GET /classrooms returns an array and the total in the
X-Total-Count header.
Rate limits
Authentication endpoints are limited per client IP. Exceeding a limit returns 429 with a
Retry-After header.
WebSocket (not part of OpenAPI)
/ws/notifications: send {"type":"auth","token":"<access JWT>"} as the first message (or use
?token=). The server sends connected, notification, pong and error messages; send
{"type":"ping"} every 30 s. Close codes: 4401 unauthorized or token expired, 4408 idle,
4429 too many connections.
""".strip()
OPENAPI_TAGS = [
{"name": "meta", "description": "Liveness and readiness probes."},
{"name": "auth", "description": "Register, log in, rotate tokens, log out and read the current user."},
{"name": "classrooms", "description": "Create and join classes, update or archive them, and list people."},
{"name": "announcements", "description": "Posts on a class stream. Teachers post; every member reads."},
{"name": "assignments", "description": "Assignments and student submissions. Drafts are hidden from students."},
{"name": "submissions", "description": "Teacher grading: set a grade and feedback, then return the work."},
{"name": "quizzes", "description": "Quizzes with nested questions, timed auto-graded attempts and results."},
{"name": "materials", "description": "Learning materials posted by teachers."},
{"name": "comments", "description": "Comments on assignments and announcements."},
{"name": "files", "description": "Authenticated uploads (type and content checked) and downloads with Range support."},
{"name": "todo", "description": "A student's to-do list, merged from explicit and derived items."},
{"name": "notifications", "description": "In-app notifications. Live delivery uses the WebSocket."},
]
_ERROR_JSON = {"model": ErrorResponse}
#: Documented on every API route (a route's own responses take precedence).
COMMON_RESPONSES: dict[int | str, dict] = {
401: {_ERROR_JSON, "description": "Missing, invalid or expired credentials."},
422: {_ERROR_JSON, "description": "Validation error. details lists every problem."},
429: {
_ERROR_JSON,
"description": "Rate limit exceeded.",
"headers": {"Retry-After": {"description": "Seconds to wait.", "schema": {"type": "integer"}}},
},
500: {_ERROR_JSON, "description": "Unexpected server error. Quote the X-Request-ID header."},
}

## Backend: edits to existing files

```python title="backend/app/core/config.py (edits)"
# 1) with the other imports:
from limits import parse as parse_rate_limit

# 2) inside class Settings, after the "Redis / rate limiting" block:
    # ---- Logging ----
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    #: auto = JSON in production/staging, readable text elsewhere
    LOG_FORMAT: Literal["auto", "json", "text"] = "auto"

    # ---- Per-IP limits for /auth/* (slowapi syntax, e.g. "10/minute") ----
    AUTH_RATE_LIMIT_REGISTER: str = "5/minute"
    AUTH_RATE_LIMIT_LOGIN: str = "10/minute"
    AUTH_RATE_LIMIT_REFRESH: str = "30/minute"
    AUTH_RATE_LIMIT_LOGOUT: str = "30/minute"
    AUTH_RATE_LIMIT_ME: str = "60/minute"

# 3) with the other validators:
    @field_validator(
        "RATE_LIMIT_DEFAULT",
        "AUTH_RATE_LIMIT_REGISTER",
        "AUTH_RATE_LIMIT_LOGIN",
        "AUTH_RATE_LIMIT_REFRESH",
        "AUTH_RATE_LIMIT_LOGOUT",
        "AUTH_RATE_LIMIT_ME",
    )
    @classmethod
    def _validate_rate_limit(cls, value: str) -> str:
        """Fail at startup (not on the first request) when a limit string is malformed."""
        try:
            parse_rate_limit(value)
        except ValueError as exc:
            raise ValueError(f"Invalid rate limit {value!r}; use e.g. '10/minute'") from exc
        return value

# 4) with the other properties:
    @property
    def json_logs(self) -> bool:
        """JSON log lines in production/staging (or when forced)."""
        if self.LOG_FORMAT == "auto":
            return self.ENVIRONMENT in ("production", "staging")
        return self.LOG_FORMAT == "json"
"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.errors import error_response, register_exception_handlers
from app.core.logging_config import setup_logging
from app.core.middleware import (
    ErrorBoundaryMiddleware,
    MaxBodySizeMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.openapi import API_DESCRIPTION, COMMON_RESPONSES, OPENAPI_TAGS
from app.core.rate_limit import limiter
from app.core.redis import close_redis
from app.db.session import engine, get_db
from app.websockets.manager import manager as ws_manager
from app.websockets.routes import router as ws_router

setup_logging(level="DEBUG" if settings.DEBUG else settings.LOG_LEVEL, json_logs=settings.json_logs)
logger = logging.getLogger("educonnect")

# multipart boundaries + form field headers on top of the file itself
_MULTIPART_OVERHEAD_BYTES = 64 * 1024


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown hooks."""
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Starting %s v%s [%s]", settings.PROJECT_NAME, settings.VERSION, settings.ENVIRONMENT)
    yield
    await ws_manager.close_all()
    await close_redis()
    await engine.dispose()
    logger.info("Database engine disposed. Shutdown complete.")


def create_app() -> FastAPI:
    """Application factory."""
    docs_enabled = not settings.is_production
    docs_paths = (
        {"/docs", "/redoc", "/docs/oauth2-redirect", f"{settings.API_V1_PREFIX}/openapi.json"}
        if docs_enabled
        else set()
    )

    app = FastAPI(
        title=f"{settings.PROJECT_NAME} API",
        version=settings.VERSION,
        summary="Google Classroom-style learning platform API.",
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        # In production neither the docs nor the schema are published.
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if docs_enabled else None,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        swagger_ui_parameters={"persistAuthorization": True, "displayRequestDuration": True},
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    register_exception_handlers(app)

    # Middleware: the LAST one added is the OUTERMOST. Resulting order, outermost first:
    # RequestContext -> SecurityHeaders -> CORS -> ErrorBoundary -> MaxBodySize -> SlowAPI -> app
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        MaxBodySizeMiddleware,
        max_bytes=settings.max_upload_size_bytes + _MULTIPART_OVERHEAD_BYTES,
        path=f"{settings.API_V1_PREFIX}/files/upload",
    )
    app.add_middleware(ErrorBoundaryMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "Range", "X-Request-ID"],
        expose_headers=[
            "Content-Range",
            "Content-Disposition",
            "Accept-Ranges",
            "Date",
            "X-Request-ID",
            "X-Total-Count",
        ],
    )
    app.add_middleware(
        SecurityHeadersMiddleware,
        hsts=settings.is_production,
        files_prefix=f"{settings.API_V1_PREFIX}/files/",
        relaxed_csp_paths=docs_paths,
    )
    app.add_middleware(RequestContextMiddleware)

    # ---- Health ----
    @app.get("/health", tags=["meta"], summary="Liveness probe")
    async def health() -> dict[str, str]:
        """Return basic liveness information (no dependencies checked)."""
        return {
            "status": "ok",
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
        }

    @app.get("/health/ready", tags=["meta"], summary="Readiness probe")
    async def readiness(db: AsyncSession = Depends(get_db)) -> JSONResponse:
        """Verify the database connection is usable. Returns 503 on failure."""
        try:
            await db.execute(text("SELECT 1"))
        except Exception:
            logger.exception("Readiness check failed")
            return error_response(
                503, "Database unavailable", code="service_unavailable", details={"database": "down"}
            )
        return JSONResponse(content={"status": "ready", "database": "up"})

    # ---- API v1 ----
    app.include_router(api_router, prefix=settings.API_V1_PREFIX, responses=COMMON_RESPONSES)
    app.include_router(ws_router)  # serves /ws/notifications (outside /api/v1)

    # ---- DEV ONLY: raw static access to stored files ----
    # WARNING: this bypasses authentication. Never enabled outside development;
    # the real download path is the authenticated GET /api/v1/files/{id}.
    if settings.ENVIRONMENT == "development":
        settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        app.mount("/static/uploads", StaticFiles(directory=settings.STORAGE_DIR), name="dev-uploads")
        logger.warning("DEV ONLY: %s is served unauthenticated at /static/uploads", settings.STORAGE_DIR)

    return app


app = create_app()
"""Shared building blocks for every Pydantic schema module.

Conventions
-----------
* ``*Create`` / ``*Update`` / request bodies inherit :class:`RequestModel`
  (``extra="forbid"``): unknown fields return 422, which blocks mass-assignment
  attempts such as sending ``"role": "admin"``.
* ``*Update`` bodies inherit :class:`UpdateModel` (PATCH semantics). Services must
  apply them with ``body.model_dump(exclude_unset=True)``.
* ``*Read`` / response models inherit :class:`ORMModel` (``from_attributes=True``).
  Relationship fields in Read schemas (``author``, ``student``, ``user`` ...) must
  be eager-loaded by the service (``selectinload`` / ``joinedload``). Implicit lazy
  loading does not work under ``AsyncSession``.
* Free-text fields are SANITISED (control characters, bidi overrides, NUL ... removed; see
  ``app/utils/sanitize.py``) before they are validated.
* ``Decimal`` values are serialized to JSON as numbers (not strings).
* Datetimes accepted from clients must be timezone-aware (``AwareDatetime``).
"""

import uuid
from decimal import Decimal
from typing import Annotated, Any, ClassVar, Generic, TypeVar

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    PlainSerializer,
    StringConstraints,
    model_validator,
)

from app.utils.sanitize import clean_line, clean_multiline

# --------------------------------------------------------------------------- #
# Base classes
# --------------------------------------------------------------------------- #


class ORMModel(BaseModel):
    """Base for response schemas built from SQLAlchemy objects."""

    model_config = ConfigDict(from_attributes=True)


class RequestModel(BaseModel):
    """Base for request bodies. Unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")


class UpdateModel(RequestModel):
    """Base for PATCH bodies.

    * At least one field must be sent.
    * Fields listed in ``non_nullable`` may be omitted but not set to ``null``
      (their database columns are NOT NULL).
    """

    non_nullable: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _validate_patch(self) -> "UpdateModel":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for name in self.model_fields_set & self.non_nullable:
            if getattr(self, name) is None:
                raise ValueError(f"'{name}' cannot be null")
        return self


# --------------------------------------------------------------------------- #
# String types (the BeforeValidator is LAST so it runs FIRST)
# --------------------------------------------------------------------------- #


def blank_to_none(value: Any) -> Any:  # noqa: ANN401
    """Sanitise, strip and turn blank strings into ``None`` (for optional text fields)."""
    if isinstance(value, str):
        value = clean_multiline(value).strip()
        return value or None
    return value


def _line(max_length: int) -> Any:  # noqa: ANN401
    return Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length),
        BeforeValidator(clean_line),
    ]


def _body(max_length: int) -> Any:  # noqa: ANN401
    return Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length),
        BeforeValidator(clean_multiline),
    ]


# Required, single-line, trimmed, non-empty strings.
Str100 = _line(100)
Str200 = _line(200)
Str255 = _line(255)
Str1000 = _line(1000)
# Required multi-line text (keeps line breaks and tabs).
Body5k = _body(5_000)
Body10k = _body(10_000)
Body20k = _body(20_000)

# Optional strings: blank input ("" or "   ") becomes None.
OptStr100 = Annotated[Str100 | None, BeforeValidator(blank_to_none)]
OptBody5k = Annotated[Body5k | None, BeforeValidator(blank_to_none)]
OptBody10k = Annotated[Body10k | None, BeforeValidator(blank_to_none)]
OptBody20k = Annotated[Body20k | None, BeforeValidator(blank_to_none)]


def _check_url_or_path(value: str | None) -> str | None:
    """Allow ``http(s)://`` URLs or app-relative paths (``/api/v1/files/...``)."""
    if value is None:
        return value
    if len(value) > 1024:
        raise ValueError("Must be at most 1024 characters")
    if value.startswith("//") or not value.startswith(("http://", "https://", "/")):
        raise ValueError("Must be an http(s) URL or an absolute path starting with '/'")
    return value


OptUrlOrPath = Annotated[
    str | None, BeforeValidator(blank_to_none), AfterValidator(_check_url_or_path)
]


# --------------------------------------------------------------------------- #
# Email / password
# --------------------------------------------------------------------------- #


def _normalise_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 320:
        raise ValueError("Email must be at most 320 characters")
    return value


LowerEmail = Annotated[EmailStr, AfterValidator(_normalise_email)]


def _validate_password(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 bytes (bcrypt limit)")
    if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
        raise ValueError("Password must contain at least one letter and one digit")
    return value


# Passwords are never stripped or sanitised: every character is legitimate.
Password = Annotated[
    str, StringConstraints(min_length=8, max_length=72), AfterValidator(_validate_password)
]


# --------------------------------------------------------------------------- #
# Numbers (JSON output as float, not string)
# --------------------------------------------------------------------------- #


def _decimal_to_float(value: Decimal) -> float:
    return float(value)


_as_number = PlainSerializer(_decimal_to_float, return_type=float, when_used="json")

#: Any numeric value read from the DB (grades, scores, points).
Score = Annotated[Decimal, _as_number]
#: Positive points for questions (max 9999.99, 2 decimals).
Points = Annotated[Decimal, Field(gt=0, le=Decimal("9999.99"), decimal_places=2), _as_number]
#: A grade given by a teacher (>= 0, 2 decimals).
Grade = Annotated[Decimal, Field(ge=0, le=Decimal("99999.99"), decimal_places=2), _as_number]


# --------------------------------------------------------------------------- #
# Attachments (stored as JSONB lists on assignments/submissions/materials)
# --------------------------------------------------------------------------- #


class AttachmentRef(ORMModel):
    """Reference to an uploaded file (see ``POST /files/upload``)."""

    file_id: uuid.UUID
    name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=512),
        BeforeValidator(clean_line),
    ]
    mime_type: str | None = Field(default=None, max_length=255)


def _unique_attachments(items: list[AttachmentRef]) -> list[AttachmentRef]:
    ids = [item.file_id for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate attachments are not allowed")
    return items


#: Request-side attachment list: max 20, no duplicates.
AttachmentList = Annotated[
    list[AttachmentRef], Field(max_length=20), AfterValidator(_unique_attachments)
]


def dump_attachments(items: list[AttachmentRef]) -> list[dict[str, Any]]:
    """Convert attachments to JSON-safe dicts for the JSONB column (UUID -> str)."""
    return [item.model_dump(mode="json") for item in items]


# --------------------------------------------------------------------------- #
# Generic responses
# --------------------------------------------------------------------------- #

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """The ``error`` object of every error response."""

    code: str = Field(description="Stable machine-readable code, e.g. `not_found`, `validation_error`.")
    message: str = Field(description="Human-readable explanation, safe to show to users.")
    details: Any | None = Field(
        default=None,
        description="Validation issues (`422`), retry hints (`429`) or other structured data; otherwise null.",
    )


class ErrorResponse(BaseModel):
    """Envelope of every error response: ``{"error": {"code", "message", "details"}}``."""

    error: ErrorDetail


#: Kept so routers can keep documenting ``{"model": Message}``.
Message = ErrorResponse


class Page(BaseModel, Generic[T]):
    """Offset-paginated list response."""

    items: list[T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
"""Authentication endpoints: /auth/register, /login, /refresh, /logout, /me.

Every endpoint is rate limited per client IP. The limits come from settings
(``AUTH_RATE_LIMIT_*``); a blocked request gets 429 with a ``Retry-After`` header.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import CurrentUser
from app.core.rate_limit import limiter
from app.core.redis import get_redis
from app.db.session import get_db
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenPair
from app.schemas.common import Message
from app.schemas.users import UserRead
from app.services.auth_service import AuthService

router = APIRouter()


def get_auth_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> AuthService:
    """Build the per-request :class:`AuthService`."""
    return AuthService(db, redis)


Service = Annotated[AuthService, Depends(get_auth_service)]


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a teacher or student account",
    responses={409: {"model": Message, "description": "Email already registered"}},
)
@limiter.limit(settings.AUTH_RATE_LIMIT_REGISTER)
async def register(request: Request, body: RegisterRequest, service: Service) -> UserRead:
    """Self-registration. Only the ``teacher`` and ``student`` roles are allowed."""
    return await service.register(body)  # type: ignore[return-value]


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Log in and receive an access + refresh token",
    responses={
        401: {"model": Message, "description": "Incorrect email or password"},
        403: {"model": Message, "description": "Account is disabled"},
    },
)
@limiter.limit(settings.AUTH_RATE_LIMIT_LOGIN)
async def login(request: Request, body: LoginRequest, service: Service) -> TokenPair:
    return await service.login(body.email, body.password)


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Rotate tokens using a refresh token",
    responses={401: {"model": Message}, 503: {"model": Message}},
)
@limiter.limit(settings.AUTH_RATE_LIMIT_REFRESH)
async def refresh(request: Request, body: RefreshRequest, service: Service) -> TokenPair:
    """The submitted refresh token is revoked and can never be used again."""
    return await service.refresh(body.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a refresh token",
    responses={503: {"model": Message}},
)
@limiter.limit(settings.AUTH_RATE_LIMIT_LOGOUT)
async def logout(request: Request, body: LogoutRequest, service: Service) -> Response:
    """The client must also discard its access token (valid until it expires)."""
    await service.logout(body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Current authenticated user",
    responses={401: {"model": Message}},
)
@limiter.limit(settings.AUTH_RATE_LIMIT_ME)
async def me(request: Request, current_user: CurrentUser) -> UserRead:
    return current_user  # type: ignore[return-value]
Pagination edits (classrooms)
class ClassroomPeople(ORMModel):
    """Response of ``GET /classrooms/{id}/people``.

    Teachers are always listed in full. Students are paginated: ``students_total`` is the
    number of students in the class, ``limit`` / ``offset`` describe the returned slice.
    """

    teachers: list[ClassroomMemberRead] = Field(default_factory=list)
    students: list[ClassroomMemberRead] = Field(default_factory=list)
    students_total: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1)
    offset: int = Field(default=0, ge=0)
# 1) import line: add `func`
from sqlalchemy import func, select

# 2) add this method next to list_for_user
    async def count_for_user(self, user: User, *, include_archived: bool) -> int:
        """Total classrooms the user is a member of (for the X-Total-Count header)."""
        stmt = (
            select(func.count())
            .select_from(Classroom)
            .join(ClassroomMember, ClassroomMember.classroom_id == Classroom.id)
            .where(ClassroomMember.user_id == user.id)
        )
        if not include_archived:
            stmt = stmt.where(Classroom.is_archived.is_(False))
        return await self.db.scalar(stmt) or 0

# 3) REPLACE list_people with:
    async def list_people(
        self, classroom: Classroom, *, limit: int, offset: int
    ) -> ClassroomPeople:
        """All teachers (owner first) and one page of students (alphabetical)."""
        active = (ClassroomMember.classroom_id == classroom.id, User.is_active.is_(True))
        base = (
            select(ClassroomMember)
            .join(ClassroomMember.user)
            .options(contains_eager(ClassroomMember.user))
            .where(*active)
        )
        teacher_rows = (
            await self.db.scalars(base.where(ClassroomMember.role == MemberRole.TEACHER))
        ).all()
        student_rows = (
            await self.db.scalars(
                base.where(ClassroomMember.role == MemberRole.STUDENT)
                .order_by(User.full_name, User.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        students_total = (
            await self.db.scalar(
                select(func.count())
                .select_from(ClassroomMember)
                .join(User, User.id == ClassroomMember.user_id)
                .where(*active, ClassroomMember.role == MemberRole.STUDENT)
            )
            or 0
        )

        owner_id: uuid.UUID = classroom.owner_id
        teachers = sorted(
            teacher_rows, key=lambda m: (m.user_id != owner_id, m.user.full_name.casefold())
        )
        return ClassroomPeople(
            teachers=[ClassroomMemberRead.model_validate(m) for m in teachers],
            students=[ClassroomMemberRead.model_validate(m) for m in student_rows],
            students_total=students_total,
            limit=limit,
            offset=offset,
        )
# 1) add to the imports
from app.core.pagination import PageParams, PeoplePageParams

# 2) REPLACE list_classrooms with
@router.get(
    "",
    response_model=list[ClassroomDetail],
    summary="List my classrooms",
    responses={
        200: {
            "headers": {
                "X-Total-Count": {
                    "description": "Total classrooms matching the filter (ignores limit/offset).",
                    "schema": {"type": "integer"},
                }
            }
        }
    },
)
async def list_classrooms(
    response: Response,
    user: CurrentUser,
    service: Service,
    page: PageParams,
    include_archived: Annotated[bool, Query(description="Also return archived classrooms")] = False,
) -> list[ClassroomDetail]:
    """Classrooms you teach or attend, newest first. Join codes are shown only where you teach."""
    rows = await service.list_for_user(
        user, include_archived=include_archived, limit=page.limit, offset=page.offset
    )
    response.headers["X-Total-Count"] = str(
        await service.count_for_user(user, include_archived=include_archived)
    )
    return [service.build_detail(classroom, role) for classroom, role in rows]

# 3) REPLACE list_people with
async def list_people(
    access: ClassroomMemberAccess, service: Service, page: PeoplePageParams
) -> ClassroomPeople:
    """All teachers, plus one page of students (``students_total`` tells you how many exist)."""
    return await service.list_people(access.classroom, limit=page.limit, offset=page.offset)
Keep the existing decorator (@router.get("/{classroom_id}/people", ...)) on list_people.
Configuration edits
# ---------- Logging ----------
LOG_LEVEL=INFO                   # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT=auto                  # auto = JSON in production/staging, text elsewhere

# ---------- Per-IP limits for /auth/* ----------
AUTH_RATE_LIMIT_REGISTER=5/minute
AUTH_RATE_LIMIT_LOGIN=10/minute
AUTH_RATE_LIMIT_REFRESH=30/minute
AUTH_RATE_LIMIT_LOGOUT=30/minute
AUTH_RATE_LIMIT_ME=60/minute
# Logging: JSON lines in production, readable text otherwise (auto), or force json/text.
LOG_LEVEL=INFO
LOG_FORMAT=auto
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      LOG_FORMAT: ${LOG_FORMAT:-auto}
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header"]
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --proxy-headers --no-server-header
## Hardening

| Area | Behaviour |
|---|---|
| Errors | Every error is `{"error": {"code", "message", "details"}}`. `422` lists each problem in `details`; `429` carries `retry_after_seconds` and a `Retry-After` header |
| Request ids | Every response has `X-Request-ID` (send your own to correlate logs). The same id is on every log line of that request |
| Logging | JSON lines in production/staging, readable text otherwise (`LOG_FORMAT`). One access-log line per request; query strings are never logged |
| Rate limits | `/auth/*` is limited per IP (`AUTH_RATE_LIMIT_*`, backed by Redis). Behind a reverse proxy, run uvicorn with `--proxy-headers` and set `FORWARDED_ALLOW_IPS` so the real client IP is used |
| Input | Free text is normalised (NFC) and stripped of control characters, NUL bytes and bidi overrides. HTML is stored as typed and escaped on output |
| Pagination | `limit` 1-100, `offset` 0-100000 everywhere. `GET /classrooms` returns the total in `X-Total-Count` |
| Headers | `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, strict CSP and `no-store` on the API, HSTS in production |
| Docs | `/docs`, `/redoc` and `openapi.json` are disabled when `ENVIRONMENT=production` |
Existing tests that must change
grep -rn '"detail"' backend/tests    # find every place that reads the old error shape
# REPLACE
    assert rejected.status_code == 409 and "time limit" in rejected.json()["detail"].lower()
# WITH
    assert rejected.status_code == 409 and "time limit" in rejected.json()["error"]["message"].lower()
# REPLACE
    assert late.status_code == 409 and "time limit" in late.json()["detail"].lower()
# WITH
    assert late.status_code == 409 and "time limit" in late.json()["error"]["message"].lower()
New tests
"""Unit tests for text sanitisation (no database needed)."""

import pytest
from pydantic import ValidationError

from app.schemas import AnnouncementCreate, ClassroomCreate, RegisterRequest
from app.utils.sanitize import clean_line, clean_multiline


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Ann   Lee  ", "Ann Lee"),
        ("Ann\x00 Lee", "Ann Lee"),  # NUL would crash PostgreSQL
        ("line\none\r\ntwo", "line one two"),  # single-line fields collapse breaks
        ("evil\u202egpj", "evilgpj"),  # bidi override removed
        ("zero\u200bwidth", "zerowidth"),
        ("tab\there", "tab here"),
        ("e\u0301", "\u00e9"),  # NFC normalisation
        ("\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645", "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645"),  # ZWNJ kept
    ],
)
def test_clean_line(raw: str, expected: str) -> None:
    assert clean_line(raw) == expected


def test_clean_multiline_keeps_line_breaks_and_tabs() -> None:
    assert clean_multiline("a\r\nb\rc\u2028d\x07e\tf") == "a\nb\nc\nde\tf"


def test_lone_surrogates_are_dropped() -> None:
    assert clean_line("\ud800broken") == "broken"  # would fail UTF-8 encoding


def test_non_strings_pass_through_for_normal_validation() -> None:
    assert clean_line(5) == 5 and clean_multiline(None) is None


def test_schemas_apply_the_sanitiser() -> None:
    user = RegisterRequest(
        email="a@example.com", password="Passw0rdX", full_name="Ann\x00\u202e  Lee "
    )
    assert user.full_name == "Ann Lee"
    assert AnnouncementCreate(content="Hi\x00\r\nthere\x07 ").content == "Hi\nthere"
    assert ClassroomCreate(name="Math", section="\x00  ").section is None  # only junk -> blank -> None
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@example.com", password="Passw0rdX", full_name="\x00\x07")
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
from tests.helpers import API, PASSWORD


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
    assert resp.json()["error"] == {"code": "unauthorized", "message": "Not authenticated", "details": None}


async def test_validation_errors_list_every_problem_without_echoing_input(bare: AsyncClient) -> None:
    resp = await bare.post(f"{API}/auth/login", json={"password": "hunter2-secret"})
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "validation_error" and error["message"] == "Request validation failed"
    fields = {item["field"]: item for item in error["details"]}
    assert "email" in fields and fields["email"]["in"] == "body" and fields["email"]["message"]
    assert "hunter2-secret" not in resp.text  # the submitted value is never echoed back


async def test_unhandled_errors_are_hidden_but_logged(bare: AsyncClient, caplog: pytest.LogCaptureFixture) -> None:
    origin = settings.CORS_ORIGINS[0]
    with caplog.at_level(logging.ERROR):
        resp = await bare.get("/__boom", headers={"Origin": origin})

    assert resp.status_code == 500
    assert resp.json() == {"error": {"code": "internal_error", "message": "Internal server error", "details": None}}
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

    record = logging.LogRecord("educonnect.test", logging.WARNING, __file__, 1, "hello %s", ("world",), None)
    record.request_id = "abc12345"
    record.status = 404  # an `extra=` field
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "hello world" and payload["level"] == "WARNING"
    assert payload["request_id"] == "abc12345" and payload["status"] == 404 and payload["ts"].endswith("+00:00")


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
async def test_control_characters_never_reach_the_database(client: AsyncClient, classroom_factory) -> None:
    room = await classroom_factory(students=0)
    teacher = room.teacher.headers

    posted = await client.post(
        f"{room.url}/announcements",
        json={"content": "Hello\u0000 wor\u202eld\r\nline two\u0007"},
        headers=teacher,
    )
    assert posted.status_code == 201, posted.text  # a NUL used to make PostgreSQL fail with a 500
    assert posted.json()["content"] == "Hello world\nline two"

    assignment = await client.post(f"{room.url}/assignments", json={"title": "Line\none\u0000"}, headers=teacher)
    assert assignment.status_code == 201 and assignment.json()["title"] == "Line one"


# ----------------------------------------------------------------- pagination
async def test_classroom_list_reports_the_total_in_a_header(
    client: AsyncClient, user_factory, classroom_factory
) -> None:
    teacher = await user_factory("teacher")
    for i in range(3):
        await classroom_factory(students=0, name=f"Class {i}", teacher=teacher)

    first = await client.get(f"{API}/classrooms", params={"limit": 2}, headers=teacher.headers)
    assert first.status_code == 200 and len(first.json()) == 2 and first.headers["x-total-count"] == "3"
    rest = await client.get(f"{API}/classrooms", params={"limit": 2, "offset": 2}, headers=teacher.headers)
    assert len(rest.json()) == 1 and rest.headers["x-total-count"] == "3"

    for bad in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"offset": 100_001}):
        assert (await client.get(f"{API}/classrooms", params=bad, headers=teacher.headers)).status_code == 422


async def test_people_students_are_paginated(client: AsyncClient, classroom_factory) -> None:
    room = await classroom_factory(students=3)
    url, teacher = f"{room.url}/people", room.teacher.headers

    first = (await client.get(url, params={"limit": 2}, headers=teacher)).json()
    assert len(first["students"]) == 2 and first["students_total"] == 3
    assert len(first["teachers"]) == 1 and first["limit"] == 2 and first["offset"] == 0

    last = (await client.get(url, params={"limit": 2, "offset": 2}, headers=teacher)).json()
    assert len(last["students"]) == 1 and len(last["teachers"]) == 1  # teachers are always listed

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
    used = {tag for item in spec["paths"].values() for op in item.values() for tag in op.get("tags", [])}
    assert used <= declared.keys()
    assert all(declared.values()), "every tag needs a description"
    assert {"auth", "classrooms", "assignments", "quizzes", "files", "notifications"} <= declared.keys()


def test_errors_are_documented_with_the_envelope() -> None:
    spec = global_app.openapi()
    responses = spec["paths"]["/api/v1/auth/login"]["post"]["responses"]
    for code in ("401", "422", "429", "500"):
        ref = responses[code]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("/ErrorResponse"), code
    assert "Retry-After" in responses["429"]["headers"]
Frontend edits
import axios from "axios";

/** HTTP status of a failed request, or `undefined` for network errors / non-HTTP errors. */
export function getStatus(error: unknown): number | undefined {
  return axios.isAxiosError(error) ? error.response?.status : undefined;
}

interface ValidationDetail {
  field?: string | null;
  message?: string;
}

/** The API's error envelope: `{ error: { code, message, details } }`. */
interface ApiErrorBody {
  error?: { code?: string; message?: string; details?: unknown };
  detail?: unknown; // legacy shape, kept as a fallback
}

/** Stable machine-readable error code (`not_found`, `validation_error`, ...), if the API sent one. */
export function getErrorCode(error: unknown): string | undefined {
  if (!axios.isAxiosError(error)) return undefined;
  return (error.response?.data as ApiErrorBody | undefined)?.error?.code;
}

/** Turn any error (API envelope, network failure, plain Error) into UI text. */
export function getErrorMessage(
  error: unknown,
  fallback = "Something went wrong. Please try again.",
): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) return "Cannot reach the server. Check your connection.";

    const body = error.response.data as ApiErrorBody | undefined;
    const api = body?.error;

    if (error.response.status === 429) {
      const wait = (api?.details as { retry_after_seconds?: number | null } | null | undefined)
        ?.retry_after_seconds;
      return wait
        ? `Too many requests. Please try again in ${wait} seconds.`
        : "Too many requests. Please wait a moment and retry.";
    }

    if (api) {
      if (api.code === "validation_error" && Array.isArray(api.details)) {
        const messages = (api.details as ValidationDetail[]).map((issue) =>
          issue.field ? `${issue.field}: ${issue.message ?? "invalid"}` : (issue.message ?? "invalid"),
        );
        if (messages.length) return messages.join("; ");
      }
      if (api.message) return api.message;
    }
    if (typeof body?.detail === "string") return body.detail;
    return fallback;
  }
  return error instanceof Error ? error.message : fallback;
}
import { AxiosError, type AxiosResponse } from "axios";
import { describe, expect, it } from "vitest";

import { getErrorCode, getErrorMessage, getStatus } from "@/api/errors";

function httpError(status: number, data: unknown): AxiosError {
  const response = { status, data, statusText: "", headers: {}, config: {} } as unknown as AxiosResponse;
  return new AxiosError("failed", "ERR_BAD_REQUEST", undefined, undefined, response);
}

const envelope = (code: string, message: string, details: unknown = null) => ({
  error: { code, message, details },
});

describe("getStatus / getErrorCode", () => {
  it("reads the HTTP status of axios errors only", () => {
    expect(getStatus(httpError(409, {}))).toBe(409);
    expect(getStatus(new AxiosError("Network Error"))).toBeUndefined();
    expect(getStatus(new Error("boom"))).toBeUndefined();
  });

  it("reads the machine-readable code", () => {
    expect(getErrorCode(httpError(404, envelope("not_found", "Classroom not found")))).toBe("not_found");
    expect(getErrorCode(new Error("boom"))).toBeUndefined();
  });
});

describe("getErrorMessage", () => {
  it("uses the message of the error envelope", () => {
    const error = httpError(409, envelope("conflict", "Email already registered"));
    expect(getErrorMessage(error)).toBe("Email already registered");
  });

  it("joins validation issues as `field: message`", () => {
    const error = httpError(
      422,
      envelope("validation_error", "Request validation failed", [
        { in: "body", field: "email", message: "invalid email", type: "value_error" },
        { in: "body", field: null, message: "Provide an answer", type: "value_error" },
      ]),
    );
    expect(getErrorMessage(error)).toBe("email: invalid email; Provide an answer");
  });

  it("tells the user how long to wait after a rate limit", () => {
    const limited = httpError(
      429,
      envelope("rate_limited", "Too many requests.", { limit: "10 per 1 minute", retry_after_seconds: 42 }),
    );
    expect(getErrorMessage(limited)).toMatch(/42 seconds/);
    expect(getErrorMessage(httpError(429, {}))).toMatch(/Too many requests/);
  });

  it("explains network failures and still understands the legacy shape", () => {
    expect(getErrorMessage(new AxiosError("Network Error", "ERR_NETWORK"))).toMatch(/Cannot reach the server/);
    expect(getErrorMessage(httpError(400, { detail: "old style" }))).toBe("old style");
  });

  it("handles plain errors and unknown values", () => {
    expect(getErrorMessage(new Error("boom"))).toBe("boom");
    expect(getErrorMessage("weird", "fallback text")).toBe("fallback text");
  });
});
export interface ClassroomPeople {
  teachers: ClassroomMember[];
  students: ClassroomMember[];
  /** Number of students in the class (the list holds one page). */
  students_total?: number;
  limit?: number;
  offset?: number;
}
  /** Teachers in full, students one page (100 is the API maximum). */
  people: (id: string) =>
    api.get<ClassroomPeople>(`/classrooms/${id}/people`, { params: { limit: 100 } }).then((r) => r.data),
// 1) signature: add an optional `total`
export function PeopleList({ title, members, total }: { title: string; members: ClassroomMember[]; total?: number }) {
  const shownTotal = total ?? members.length;

// 2) heading count: REPLACE ({members.length}) WITH ({shownTotal})

// 3) after the closing </ul>, inside the `else` branch, add:
          {shownTotal > members.length ? (
            <p className="py-2 text-xs text-muted-foreground">
              Showing the first {members.length} of {shownTotal}.
            </p>
          ) : null}
// REPLACE
        <PeopleList title="Students" members={data?.students ?? []} />
// WITH
        <PeopleList title="Students" members={data?.students ?? []} total={data?.students_total} />

How to run and test
make test-fast          # core suite (needs the two edited quiz tests)
make test               # everything, including test_hardening.py and test_sanitize.py
make lint               # ruff + eslint; fix anything new

cd frontend && npm test && npm run build
Expected: all green. If a test still reads ["detail"], grep -rn '"detail"' backend/tests shows it.
Manual checks
docker compose up --build -d
BASE=http://localhost:8000
#	Command	Expected
1	curl -si $BASE/nope	404, body {"error":{"code":"not_found","message":"Not Found","details":null}}, plus an x-request-id header
2	curl -si $BASE/health -H 'X-Request-ID: my-trace-0001'	Same id echoed back. The container log line for GET /health appears only at DEBUG level
3	curl -si -X POST $BASE/api/v1/auth/login -H 'Content-Type: application/json' -d '{"password":"x"}'	422, code: validation_error, details with field: "email", and no echo of the password
4	for i in $(seq 1 12); do curl -s -o /dev/null -w "%{http_code} " -X POST $BASE/api/v1/auth/login -H 'Content-Type: application/json' -d '{"email":"x@example.com","password":"Passw0rd1"}'; done	401 ten times, then 429 429
5	Repeat one of those blocked calls with -i	Retry-After: <seconds> header and details.retry_after_seconds
6	curl -si $BASE/health | head -20	x-content-type-options, x-frame-options, referrer-policy, permissions-policy, content-security-policy, cache-control: no-store; no server: header; no HSTS (not production)
7	Open http://localhost:8000/docs	Tags have descriptions, the intro explains errors, ids, pagination and the WebSocket. Swagger UI still works, so the relaxed CSP is correct
8	With a teacher token: curl -s -X POST $BASE/api/v1/classrooms/$CID/announcements -H "$AUTH" -H 'Content-Type: application/json' -d '{"content":"Hi\u0000 there\r\nbye"}'	201, content "Hi there\nbye" (it used to be a 500)
9	curl -si "$BASE/api/v1/classrooms?limit=2" -H "$AUTH" | grep -i x-total-count	The total, regardless of limit
10	curl -s "$BASE/api/v1/classrooms?limit=500" -H "$AUTH"	422 envelope
11	Set ENVIRONMENT=production, restart	/docs, /redoc and /api/v1/openapi.json return 404, and responses carry strict-transport-security. Logs are JSON lines, one object per line with a request_id field
12	docker compose logs backend | tail -3	Text lines like ... | educonnect.access | 3f9c... | POST /api/v1/auth/login -> 401 (84.1 ms)
Frontend: trigger a rate limit by logging in 11 times quickly. The form shows "Too many requests. Please try again in N seconds." Registering with an invalid email shows email: … from the validation details.
Troubleshooting
Problem	Fix
A test fails on ["detail"]	The envelope replaced it. Use ["error"]["message"] (see the two edits above)
ValueError: Invalid rate limit '10 per minute' on startup	Use slowapi syntax: 10/minute
Rate-limit counts are shared across tests	Not an issue: RATE_LIMIT_DEFAULT is huge in tests, and the rate-limit test calls limiter.reset()
Everyone shares one IP and gets limited together	You are behind a proxy. Run uvicorn with --proxy-headers and set FORWARDED_ALLOW_IPS to the proxy's address
Swagger UI is blank	The relaxed CSP is only applied to /docs, /redoc and openapi.json when docs are enabled. Check ENVIRONMENT is not production
Browser can't read X-Request-ID or X-Total-Count	They are in CORS expose_headers. Restart the API after pulling the new main.py
ImportError: cannot import name 'Message'	schemas/common.py must be the new version. Message is now an alias of ErrorResponse
Logs show duplicated or uvicorn-formatted access lines	An old CMD without --no-server-header is harmless. Duplicated lines mean a second setup_logging call: keep it only in main.py
students_total missing in the frontend	schemas/classrooms.py, the service and the router edits must all be applied
Not included in this step: a per-account login lockout (the per-IP limit remains), TrustedHostMiddleware, and a pagination envelope for GET /classrooms (it stays an array so existing clients keep working).
Reply NEXT to start Phase 2 (accessibility: neural TTS/STT, voice commands, spoken feedback).
```