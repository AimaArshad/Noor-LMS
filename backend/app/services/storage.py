"""Storage abstraction for uploaded files (local disk now, S3/MinIO later).

Keys
----
A *key* is an opaque, relative, forward-slash path such as ``ab/ab12...ef.pdf``.
It is stored in ``files.path``. The backend name (``"local"`` / ``"s3"``) is stored
in ``files.storage_backend`` so both can coexist during a migration.

Swapping to S3/MinIO later
--------------------------
Implement :class:`S3Storage` (aioboto3 / aiobotocore), register it in
:func:`get_storage`, and select it with a setting. Nothing else changes.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote

import aiofiles

from app.core.config import settings

logger = logging.getLogger("educonnect.storage")

CHUNK_SIZE = 64 * 1024


class StorageError(Exception):
    """Storage backend failure or invalid key."""


class StorageFileNotFound(StorageError):
    """The requested key does not exist in the backend."""


class StorageBackend(ABC):
    """Interface every storage backend implements."""

    #: Stored in ``files.storage_backend``.
    name: str

    @abstractmethod
    async def save(self, key: str, source: BinaryIO, *, content_type: str | None = None) -> int:
        """Store everything readable from ``source`` (read from its current position).

        Returns:
            Number of bytes written.
        """

    @abstractmethod
    def open(self, key: str, *, start: int = 0, end: int | None = None) -> AsyncIterator[bytes]:
        """Stream the object in chunks. ``start``/``end`` are INCLUSIVE byte offsets
        (same semantics as HTTP ``Range``); ``end=None`` means until the end."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete the object. Must not fail if it does not exist."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """True when the object exists."""

    @abstractmethod
    def url_for(self, key: str, *, expires_in: int = 3600) -> str:
        """A direct URL for the object (pre-signed for S3; ``expires_in`` seconds).

        The API itself never hands this out: downloads go through the authenticated
        ``GET /files/{id}`` endpoint.
        """


# --------------------------------------------------------------------------- #
# Local filesystem
# --------------------------------------------------------------------------- #
class LocalStorage(StorageBackend):
    """Stores objects below ``root`` on the local filesystem."""

    name = "local"

    def __init__(self, root: Path | str, *, public_base_url: str = "/static/uploads") -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.public_base_url = public_base_url.rstrip("/")

    def _resolve(self, key: str) -> Path:
        """Map a key to a path, refusing anything that escapes ``root``."""
        if not key or key.startswith(("/", "\\")) or "\x00" in key:
            raise StorageError(f"Invalid storage key: {key!r}")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise StorageError(f"Invalid storage key: {key!r}")
        return path

    async def save(self, key: str, source: BinaryIO, *, content_type: str | None = None) -> int:
        dest = self._resolve(key)
        tmp = dest.with_name(f"{dest.name}.{uuid.uuid4().hex[:8]}.part")

        def _write() -> int:
            dest.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            try:
                with open(tmp, "wb") as out:
                    while chunk := source.read(CHUNK_SIZE):
                        out.write(chunk)
                        written += len(chunk)
                os.replace(tmp, dest)  # atomic: readers never see a partial file
            except BaseException:
                tmp.unlink(missing_ok=True)
                raise
            return written

        try:
            return await asyncio.to_thread(_write)
        except OSError as exc:
            raise StorageError(f"Could not write {key}") from exc

    async def open(  # type: ignore[override]  # async generator implements the ABC's AsyncIterator
        self, key: str, *, start: int = 0, end: int | None = None
    ) -> AsyncIterator[bytes]:
        if start < 0 or (end is not None and end < start):
            raise ValueError("Invalid byte range")
        path = self._resolve(key)
        remaining = None if end is None else end - start + 1
        try:
            async with aiofiles.open(path, "rb") as fh:
                if start:
                    await fh.seek(start)
                while remaining is None or remaining > 0:
                    chunk = await fh.read(CHUNK_SIZE if remaining is None else min(CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    if remaining is not None:
                        remaining -= len(chunk)
                    yield chunk
        except FileNotFoundError as exc:
            raise StorageFileNotFound(key) from exc

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        await asyncio.to_thread(path.unlink, missing_ok=True)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._resolve(key).is_file)

    def url_for(self, key: str, *, expires_in: int = 3600) -> str:
        """Public URL under the dev-only static mount (no authentication, no expiry)."""
        self._resolve(key)  # validates the key
        return f"{self.public_base_url}/{quote(key)}"


# --------------------------------------------------------------------------- #
# S3 / MinIO (stub)
# --------------------------------------------------------------------------- #
class S3Storage(StorageBackend):
    """S3-compatible storage (AWS S3, MinIO). **Not implemented yet.**

    Implementation notes for later:

    * Use ``aioboto3``; pass ``endpoint_url`` for MinIO.
    * ``save``   -> ``client.upload_fileobj(source, bucket, key, ExtraArgs={"ContentType": ...})``
    * ``open``   -> ``get_object(Range=f"bytes={start}-{end or ''}")``, then iterate ``Body.iter_chunks()``
    * ``delete`` -> ``delete_object``;  ``exists`` -> ``head_object`` (404 -> False)
    * ``url_for`` -> ``generate_presigned_url("get_object", ..., ExpiresIn=expires_in)``
    """

    name = "s3"
    _MESSAGE = "S3Storage is not implemented yet"

    def __init__(
        self,
        bucket: str,
        *,
        endpoint_url: str | None = None,
        region: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        prefix: str = "",
    ) -> None:
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.region = region
        self.access_key = access_key
        self.secret_key = secret_key
        self.prefix = prefix

    async def save(self, key: str, source: BinaryIO, *, content_type: str | None = None) -> int:
        raise NotImplementedError(self._MESSAGE)

    def open(self, key: str, *, start: int = 0, end: int | None = None) -> AsyncIterator[bytes]:
        raise NotImplementedError(self._MESSAGE)

    async def delete(self, key: str) -> None:
        raise NotImplementedError(self._MESSAGE)

    async def exists(self, key: str) -> bool:
        raise NotImplementedError(self._MESSAGE)

    def url_for(self, key: str, *, expires_in: int = 3600) -> str:
        raise NotImplementedError(self._MESSAGE)


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
@lru_cache
def get_storage(backend: str = "local") -> StorageBackend:
    """Return the (cached) backend instance registered under ``backend``."""
    if backend == "local":
        return LocalStorage(settings.STORAGE_DIR)
    if backend == "s3":
        raise StorageError("S3 storage is not configured yet")
    raise StorageError(f"Unknown storage backend: {backend!r}")