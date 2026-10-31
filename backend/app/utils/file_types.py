"""Allowed upload types and server-side content verification.

The client-supplied ``Content-Type`` is never trusted. A file is accepted only when

1. its extension is on the allow-list, and
2. its bytes match that type (magic numbers / ZIP structure / valid UTF-8 text).

The stored MIME type comes from the allow-list, not from the client.
SVG and HTML are intentionally NOT allowed (script execution risk when served
from our own origin).
"""

from __future__ import annotations

import codecs
import unicodedata
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import BinaryIO

Checker = Callable[[BinaryIO], bool]

_TEXT_SAMPLE_BYTES = 8192
_MAX_NAME_LENGTH = 255


# --------------------------------------------------------------------------- #
# Content checkers (each one restores the file position to 0 where it matters)
# --------------------------------------------------------------------------- #
def _head(fh: BinaryIO, n: int = 16) -> bytes:
    fh.seek(0)
    data = fh.read(n)
    fh.seek(0)
    return data


def _starts_with(*prefixes: bytes) -> Checker:
    def check(fh: BinaryIO) -> bool:
        head = _head(fh)
        return any(head.startswith(prefix) for prefix in prefixes)

    return check


def _riff(form: bytes) -> Checker:
    def check(fh: BinaryIO) -> bool:
        head = _head(fh, 12)
        return head[:4] == b"RIFF" and head[8:12] == form

    return check


def _is_mp3(fh: BinaryIO) -> bool:
    head = _head(fh, 4)
    if head[:3] == b"ID3":
        return True
    return len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0  # MPEG frame sync


def _zip_containing(*required: str) -> Checker:
    """Valid ZIP archive that contains every ``required`` entry name."""

    def check(fh: BinaryIO) -> bool:
        fh.seek(0)
        try:
            with zipfile.ZipFile(fh) as archive:  # reads the central directory only
                names = set(archive.namelist())
        except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, ValueError, EOFError, NotImplementedError):
            return False
        finally:
            fh.seek(0)
        return all(name in names for name in required)

    return check


def _is_text(fh: BinaryIO) -> bool:
    head = _head(fh, _TEXT_SAMPLE_BYTES)
    if b"\x00" in head:
        return False
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        decoder.decode(head, final=False)  # final=False: a cut multi-byte char at the end is fine
    except UnicodeDecodeError:
        return False
    return True


# --------------------------------------------------------------------------- #
# Allow-list
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class FileType:
    """One allowed kind of file."""

    mime: str
    extensions: tuple[str, ...]
    check: Checker
    inline_safe: bool = False  # may be displayed in the browser (otherwise forced download)

    def matches(self, fh: BinaryIO) -> bool:
        """True when the content of ``fh`` really is this type. Rewinds ``fh`` afterwards."""
        try:
            return self.check(fh)
        finally:
            fh.seek(0)


_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

ALLOWED_TYPES: tuple[FileType, ...] = (
    FileType("application/pdf", (".pdf",), _starts_with(b"%PDF-"), inline_safe=True),
    FileType(_DOCX, (".docx",), _zip_containing("[Content_Types].xml", "word/document.xml")),
    FileType(_PPTX, (".pptx",), _zip_containing("[Content_Types].xml", "ppt/presentation.xml")),
    FileType("image/png", (".png",), _starts_with(b"\x89PNG\r\n\x1a\n"), inline_safe=True),
    FileType("image/jpeg", (".jpg", ".jpeg"), _starts_with(b"\xff\xd8\xff"), inline_safe=True),
    FileType("image/gif", (".gif",), _starts_with(b"GIF87a", b"GIF89a"), inline_safe=True),
    FileType("image/webp", (".webp",), _riff(b"WEBP"), inline_safe=True),
    FileType("application/zip", (".zip",), _zip_containing()),
    FileType("audio/mpeg", (".mp3",), _is_mp3, inline_safe=True),
    FileType("audio/wav", (".wav",), _riff(b"WAVE"), inline_safe=True),
    FileType("text/plain", (".txt",), _is_text, inline_safe=True),
)

TYPE_BY_EXTENSION: dict[str, FileType] = {
    ext: file_type for file_type in ALLOWED_TYPES for ext in file_type.extensions
}
TYPE_BY_MIME: dict[str, FileType] = {file_type.mime: file_type for file_type in ALLOWED_TYPES}
ALLOWED_EXTENSIONS: tuple[str, ...] = tuple(sorted(TYPE_BY_EXTENSION))


# --------------------------------------------------------------------------- #
# File names
# --------------------------------------------------------------------------- #
def sanitize_filename(raw: str | None) -> str:
    """Return a safe display name, or ``""`` when nothing usable remains.

    * keeps only the last path component (blocks ``../../x``),
    * removes control and invisible formatting characters (CR/LF header injection,
      right-to-left override tricks like ``invoice\\u202Egpj.exe``),
    * truncates to 255 characters while keeping the extension.
    """
    if not raw:
        return ""
    name = raw.replace("\\", "/").split("/")[-1]
    name = "".join(ch for ch in name if unicodedata.category(ch) not in ("Cc", "Cf")).strip()
    if name in {"", ".", ".."}:
        return ""
    if len(name) > _MAX_NAME_LENGTH:
        suffix = PurePosixPath(name).suffix[:20]
        name = name[: _MAX_NAME_LENGTH - len(suffix)] + suffix
    return name


def get_extension(name: str) -> str:
    """Lower-cased extension including the dot (``""`` when there is none)."""
    return PurePosixPath(name).suffix.lower()