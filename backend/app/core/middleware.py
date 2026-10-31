"""Pure-ASGI middleware that rejects oversized request bodies early."""

from __future__ import annotations

from fastapi import HTTPException, status
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


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
            response = JSONResponse(
                {"detail": "Request body too large"},
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
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