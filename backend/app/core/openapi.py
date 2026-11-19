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
```

`details` carries a list of `{in, field, message, type}` for `422 validation_error`, and
`{limit, retry_after_seconds}` for `429 rate_limited`. Codes are stable; messages are for people.
Users who are not members of a classroom get 404, not 403, so ids cannot be probed.

## Request ids
Every response has an `X-Request-ID` header (send your own, 8-64 chars of `A-Za-z0-9._-`, to
correlate logs). Quote it when reporting a problem.

## Pagination
List endpoints take `limit` (1-100) and `offset`. Page responses are
`{items, total, limit, offset}`. `GET /classrooms` returns an array and the total in the
`X-Total-Count` header.

## Rate limits
Authentication endpoints are limited per client IP. Exceeding a limit returns `429` with a
`Retry-After` header.

## WebSocket (not part of OpenAPI)
`/ws/notifications`: send `{"type":"auth","token":"<access JWT>"}` as the first message (or use
`?token=`). The server sends `connected`, `notification`, `pong` and `error` messages; send
`{"type":"ping"}` every 30 s. Close codes: `4401` unauthorized or token expired, `4408` idle,
`4429` too many connections.
""".strip()

OPENAPI_TAGS = [
    {"name": "meta", "description": "Liveness and readiness probes."},
    {
        "name": "auth",
        "description": "Register, log in, rotate tokens, log out and read the current user.",
    },
    {
        "name": "classrooms",
        "description": "Create and join classes, update or archive them, and list people.",
    },
    {
        "name": "announcements",
        "description": "Posts on a class stream. Teachers post; every member reads.",
    },
    {
        "name": "assignments",
        "description": "Assignments and student submissions. Drafts are hidden from students.",
    },
    {
        "name": "submissions",
        "description": "Teacher grading: set a grade and feedback, then return the work.",
    },
    {
        "name": "quizzes",
        "description": "Quizzes with nested questions, timed auto-graded attempts and results.",
    },
    {"name": "materials", "description": "Learning materials posted by teachers."},
    {"name": "comments", "description": "Comments on assignments and announcements."},
    {
        "name": "files",
        "description": "Authenticated uploads (type and content checked) and downloads with Range support.",
    },
    {
        "name": "todo",
        "description": "A student's to-do list, merged from explicit and derived items.",
    },
    {
        "name": "notifications",
        "description": "In-app notifications. Live delivery uses the WebSocket.",
    },
    {
        "name": "accessibility",
        "description": "Text-to-speech synthesis and voice listing for screen-reader users.",
    },
]

_ERROR_JSON = {"model": ErrorResponse}
#: Documented on every API route (a route's own responses take precedence).
COMMON_RESPONSES: dict[int | str, dict] = {
    401: {**_ERROR_JSON, "description": "Missing, invalid or expired credentials."},
    422: {**_ERROR_JSON, "description": "Validation error. details lists every problem."},
    429: {
        **_ERROR_JSON,
        "description": "Rate limit exceeded.",
        "headers": {
            "Retry-After": {"description": "Seconds to wait.", "schema": {"type": "integer"}}
        },
    },
    500: {**_ERROR_JSON, "description": "Unexpected server error. Quote the X-Request-ID header."},
}
