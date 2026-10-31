"""Small HTTP helpers for file downloads."""

from __future__ import annotations

import re
from urllib.parse import quote


class RangeNotSatisfiable(Exception):
    """The requested byte range lies outside the file (respond 416)."""


# Single range only; digits are capped so int() can never explode.
_RANGE_RE = re.compile(r"bytes=(\d{0,18})-(\d{0,18})")


def parse_range(header: str | None, size: int) -> tuple[int, int] | None:
    """Parse an HTTP ``Range`` header into an inclusive ``(start, end)`` pair.

    Returns:
        ``None`` when the whole file should be sent: no header, or a header that is
        malformed / multi-range (RFC 9110 allows servers to ignore those).

    Raises:
        RangeNotSatisfiable: for a well-formed range that starts beyond the end of the file.
    """
    if not header:
        return None
    match = _RANGE_RE.fullmatch(header.strip())
    if match is None:
        return None
    first, last = match.groups()
    if not first and not last:
        return None
    if size <= 0:
        raise RangeNotSatisfiable

    if not first:  # suffix range: the last N bytes
        suffix = int(last)
        if suffix == 0:
            raise RangeNotSatisfiable
        return max(size - suffix, 0), size - 1

    start = int(first)
    if last and int(last) < start:  # syntactically invalid -> ignore header
        return None
    if start >= size:
        raise RangeNotSatisfiable
    end = size - 1 if not last else min(int(last), size - 1)
    return start, end


def content_disposition(filename: str, *, inline: bool) -> str:
    """Build a safe ``Content-Disposition`` value (ASCII fallback + RFC 5987 UTF-8 name)."""
    kind = "inline" if inline else "attachment"
    ascii_name = "".join(c for c in filename if 32 <= ord(c) < 127 and c not in '"\\') or "download"
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename, safe='')}"