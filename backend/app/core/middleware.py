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
        request_id = (
            incoming if incoming and _REQUEST_ID_RE.fullmatch(incoming) else uuid.uuid4().hex
        )
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
            response = error_response(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Request body too large"
            )
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
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Request body too large"
                    )
            return message

        await self.app(scope, limited_receive, send)
