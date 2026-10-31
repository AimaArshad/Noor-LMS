"""Unit tests: file types, Range parsing, LocalStorage, upload size middleware (no DB)."""

import io
import zipfile
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.core.middleware import MaxBodySizeMiddleware
from app.services.storage import LocalStorage, S3Storage, StorageError
from app.utils.file_types import TYPE_BY_EXTENSION, get_extension, sanitize_filename
from app.utils.http import RangeNotSatisfiable, content_disposition, parse_range


# --------------------------------------------------------------- file names
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("report.pdf", "report.pdf"),
        ("../../etc/passwd.txt", "passwd.txt"),
        ("C:\\Users\\me\\notes.txt", "notes.txt"),
        ("a\r\nb.txt", "ab.txt"),
        ("invoice\u202egpj.exe", "invoicegpj.exe"),  # right-to-left override removed
        ("..", ""),
        ("   ", ""),
        (None, ""),
    ],
)
def test_sanitize_filename(raw: str | None, expected: str) -> None:
    assert sanitize_filename(raw) == expected


def test_sanitize_filename_truncates_but_keeps_extension() -> None:
    name = sanitize_filename("a" * 400 + ".pdf")
    assert len(name) == 255 and name.endswith(".pdf")


def test_extensions() -> None:
    assert get_extension("A.PDF") == ".pdf" and get_extension("noext") == "" and get_extension("x.") == ""
    assert ".svg" not in TYPE_BY_EXTENSION and ".html" not in TYPE_BY_EXTENSION


# -------------------------------------------------------------------- range
@pytest.mark.parametrize(
    ("header", "size", "expected"),
    [
        (None, 100, None),
        ("bytes=0-3", 100, (0, 3)),
        ("bytes=95-", 100, (95, 99)),
        ("bytes=-5", 100, (95, 99)),
        ("bytes=0-9999", 100, (0, 99)),
        ("bytes=-500", 100, (0, 99)),
        ("bytes=9-3", 100, None),  # invalid -> ignored
        ("bytes=0-3,5-6", 100, None),  # multi-range -> ignored
        ("items=0-3", 100, None),
        ("garbage", 100, None),
    ],
)
def test_parse_range(header: str | None, size: int, expected: tuple[int, int] | None) -> None:
    assert parse_range(header, size) == expected


@pytest.mark.parametrize("header", ["bytes=100-", "bytes=500-600", "bytes=-0"])
def test_parse_range_unsatisfiable(header: str) -> None:
    with pytest.raises(RangeNotSatisfiable):
        parse_range(header, 100)


def test_content_disposition_is_header_safe() -> None:
    value = content_disposition('evil"\r\nX-Injected: 1.txt', inline=False)
    assert "\r" not in value and "\n" not in value
    assert value.startswith("attachment;") and "filename*=UTF-8''" in value
    assert "inline" in content_disposition("ünï.pdf", inline=True)


# ------------------------------------------------------------ local storage
async def _collect(chunks) -> bytes:  # noqa: ANN001
    return b"".join([c async for c in chunks])


@pytest.mark.asyncio
async def test_local_storage_roundtrip(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    data = bytes(range(256)) * 1000  # 256 000 bytes -> several chunks
    key = "ab/abcdef.bin"

    assert not await storage.exists(key)
    assert await storage.save(key, io.BytesIO(data)) == len(data)
    assert await storage.exists(key)
    assert await _collect(storage.open(key)) == data
    assert await _collect(storage.open(key, start=10, end=19)) == data[10:20]
    assert await _collect(storage.open(key, start=len(data) - 5)) == data[-5:]
    assert not list(tmp_path.rglob("*.part"))  # temp file was renamed

    await storage.delete(key)
    await storage.delete(key)  # idempotent
    assert not await storage.exists(key)


@pytest.mark.asyncio
async def test_local_storage_rejects_path_traversal(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "root")
    for bad in ("../outside.txt", "/etc/passwd", "a/../../outside.txt", "", "x\x00y"):
        with pytest.raises(StorageError):
            await storage.save(bad, io.BytesIO(b"x"))
        with pytest.raises(StorageError):
            await storage.exists(bad)
    assert not (tmp_path / "outside.txt").exists()


def test_local_storage_url_for(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path, public_base_url="/static/uploads/")
    assert storage.url_for("ab/file name.pdf") == "/static/uploads/ab/file%20name.pdf"


@pytest.mark.asyncio
async def test_s3_stub_is_not_implemented() -> None:
    s3 = S3Storage("bucket")
    with pytest.raises(NotImplementedError):
        await s3.save("k", io.BytesIO(b"x"))
    with pytest.raises(NotImplementedError):
        s3.url_for("k")


# --------------------------------------------------------------- middleware
def _mini_app(max_bytes: int) -> FastAPI:
    app = FastAPI()
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=max_bytes, path="/up")

    @app.post("/up")
    async def up(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    @app.post("/other")
    async def other(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    return app


@pytest.mark.asyncio
async def test_middleware_limits() -> None:
    async def chunked(total: int):  # noqa: ANN202 - no Content-Length -> counted while streaming
        for _ in range(total // 100):
            yield b"x" * 100

    async with AsyncClient(transport=ASGITransport(app=_mini_app(1000)), base_url="http://t") as c:
        assert (await c.post("/up", content=b"x" * 900)).json() == {"size": 900}
        assert (await c.post("/up", content=b"x" * 1001)).status_code == 413  # Content-Length
        assert (await c.post("/up", content=chunked(500))).status_code == 200
        assert (await c.post("/up", content=chunked(2000))).status_code == 413  # streamed
        assert (await c.post("/other", content=b"x" * 5000)).status_code == 200  # other paths untouched