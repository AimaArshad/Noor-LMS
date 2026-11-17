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
