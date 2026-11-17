"""Text sanitisation for user-supplied strings.

Applied by the Pydantic string types in ``schemas/common.py``, i.e. at the API boundary.

Removed from every value:

* control characters (C0 / C1, including NUL: PostgreSQL rejects NUL in text columns),
* lone surrogates (cannot be encoded as UTF-8),
* zero-width space / word joiner / BOM, and the bidi *override* and *isolate* characters
  used for filename and text spoofing (``\u202e`` ...).

Deliberately KEPT: ZWNJ / ZWJ (U+200C / U+200D), which Persian, Urdu, Hindi and others need.

Line breaks are normalised to ``\n``. Single-line fields collapse all whitespace runs to one
space; multi-line fields keep ``\n`` and ``\t``.

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
