"""``parse_command`` — convert a voice transcript into a structured Command.

Design
------
* Pure functions; no I/O, no DB.  Easily unit-tested.
* Table-driven: each intent is detected by one or more regex patterns tried
  in priority order.
* Spoken numbers ("twenty three", "1st", "2nd") are normalised to integers.
* rapidfuzz is used by the caller (voice_command_service) for fuzzy matching
  of book/class/topic names against the DB; this module only extracts the
  raw text tokens from the transcript.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Spoken-number normalisation
# ---------------------------------------------------------------------------

_ONES: dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}

_ORDINAL_MAP: dict[str, int] = {
    "first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3,
    "fourth": 4, "4th": 4, "fifth": 5, "5th": 5, "sixth": 6, "6th": 6,
    "seventh": 7, "7th": 7, "eighth": 8, "8th": 8, "ninth": 9, "9th": 9,
    "tenth": 10, "10th": 10, "eleventh": 11, "11th": 11, "twelfth": 12,
    "12th": 12,
}

_HUNDRED = "hundred"
_AND_RE = re.compile(r"\band\b", re.IGNORECASE)


def _word_to_int(text: str) -> int | None:
    """Convert a spoken-number string to int, or return None."""
    text = text.strip().lower()
    if text.isdigit():
        return int(text)
    if text in _ORDINAL_MAP:
        return _ORDINAL_MAP[text]

    # Remove filler "and" ("one hundred and three")
    text = _AND_RE.sub("", text)
    tokens = text.split()

    total = 0
    current = 0
    matched_any = False

    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        if tok in _ONES:
            current += _ONES[tok]
            matched_any = True
        elif tok == _HUNDRED:
            if current == 0:
                current = 1
            current *= 100
            matched_any = True
        elif tok in _ORDINAL_MAP:
            current += _ORDINAL_MAP[tok]
            matched_any = True
        else:
            return None  # unrecognised token

    total += current
    return total if matched_any else None


# ---------------------------------------------------------------------------
# Class/year normalisation ("1st year" → "1st year", "class 10" → "class 10")
# ---------------------------------------------------------------------------

_CLASS_PATTERNS = [
    re.compile(r"\b(class\s+\d+|year\s+\d+|\d+(?:st|nd|rd|th)\s+year|grade\s+\d+)\b", re.IGNORECASE),
]

def _extract_class(text: str) -> str | None:
    for pat in _CLASS_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(0).strip()
    return None


# ---------------------------------------------------------------------------
# Intent patterns (tried in ORDER — first match wins)
# ---------------------------------------------------------------------------
# Each entry: (intent_name, compiled_regex, named_groups_to_extract)
# Named groups used:
#   num        — chapter/page number (may be digit or word)
#   seconds    — seconds for forward/backward (may be digit or word)
#   topic      — arbitrary topic text
#   book       — book/audiobook name hint

_N = r"(?P<num>\d+|[a-z]+(?:\s+(?!(?:in|of|from)\b)[a-z]+)*)"  # number: digits or spoken words, stops before "in/of/from"
_S = r"(?P<seconds>\d+|[a-z][\w ]*)"    # seconds token
_B = r"(?:\s+(?:in|of|from)\s+(?P<book>.+))?"  # optional "in <book>" suffix (greedy to EOL)

# ORDER MATTERS: more specific → less specific
_INTENT_TABLE: list[tuple[str, re.Pattern[str]]] = [
    # --- navigation ---
    ("where_am_i",   re.compile(r"\b(where am i|current position|where are we|where's this)\b", re.IGNORECASE)),
    ("help",         re.compile(r"^(help|what can (you|i) (say|do)|commands)$", re.IGNORECASE)),
    ("next_chapter", re.compile(r"\b(next chapter|skip chapter|forward chapter)\b", re.IGNORECASE)),
    ("previous_chapter", re.compile(r"\b(previous chapter|last chapter|back chapter|go back a chapter)\b", re.IGNORECASE)),

    # go_chapter: "go to chapter 3", "chapter 3 in physics", "open chapter two"
    ("go_chapter",   re.compile(
        r"\b(?:go\s+to\s+|open\s+|jump\s+to\s+)?chapter\s+" + _N + _B,
        re.IGNORECASE,
    )),

    # go_page
    ("go_page",      re.compile(
        r"\b(?:go\s+to\s+|open\s+|jump\s+to\s+)?page\s+" + _N + _B,
        re.IGNORECASE,
    )),

    # play_topic: "play topic waves and motion", "find topic introduction"
    ("play_topic",   re.compile(
        r"\b(?:play|find|search|go\s+to)\s+topic\s+(?P<topic>.+)",
        re.IGNORECASE,
    )),

    # --- speed ---
    ("faster",  re.compile(r"\b(speed\s*up|faster|increase speed|go faster)\b", re.IGNORECASE)),
    ("slower",  re.compile(r"\b(slow\s*(?:down|er)|slower|decrease speed|go slower)\b", re.IGNORECASE)),

    # --- seek ---
    ("forward",  re.compile(
        r"\b(?:go\s+)?forward(?:\s+" + _S + r"\s+seconds?)?\b",
        re.IGNORECASE,
    )),
    ("backward", re.compile(
        r"\b(?:go\s+)?(?:backward|back(?:ward)?)(?:\s+" + _S + r"\s+seconds?)?\b",
        re.IGNORECASE,
    )),

    # --- playback ---
    ("resume", re.compile(r"\b(resume|continue|unpause)\b", re.IGNORECASE)),
    ("pause",  re.compile(r"\b(pause|hold|wait)\b", re.IGNORECASE)),
    ("stop",   re.compile(r"\b(stop|quit|exit|end)\b", re.IGNORECASE)),
    ("play",   re.compile(r"\b(play|start|begin|read)\b", re.IGNORECASE)),
]


# ---------------------------------------------------------------------------
# Command dataclass
# ---------------------------------------------------------------------------

@dataclass
class Command:
    """Parsed voice command."""

    intent: str
    """One of the intent names defined in _INTENT_TABLE."""

    params: dict[str, Any] = field(default_factory=dict)
    """
    Intent-specific parameters:
    - go_chapter:    chapter (int|None), book (str|None), class_hint (str|None)
    - go_page:       page (int|None), book (str|None)
    - play_topic:    topic (str), book (str|None), class_hint (str|None)
    - forward/backward: seconds (int) — default 30
    - all others:    empty
    """


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_command(text: str) -> Command:
    """Parse a voice transcript into a :class:`Command`.

    Strips leading/trailing whitespace, folds multiple spaces, then tries
    each pattern in ``_INTENT_TABLE`` in order.  Returns a ``Command`` with
    intent ``"unknown"`` if nothing matches.

    Args:
        text: Raw transcript string.

    Returns:
        A :class:`Command` with ``intent`` and ``params``.
    """
    text = " ".join(text.strip().split())  # normalise whitespace

    for intent, pattern in _INTENT_TABLE:
        m = pattern.search(text)
        if m is None:
            continue

        gd = m.groupdict()
        params: dict[str, Any] = {}

        if intent in ("go_chapter",):
            raw_num = (gd.get("num") or "").strip()
            params["chapter"] = _word_to_int(raw_num)
            params["book"] = (gd.get("book") or "").strip() or None
            params["class_hint"] = _extract_class(text)

        elif intent == "go_page":
            raw_num = (gd.get("num") or "").strip()
            params["page"] = _word_to_int(raw_num)
            params["book"] = (gd.get("book") or "").strip() or None

        elif intent == "play_topic":
            params["topic"] = (gd.get("topic") or "").strip()
            params["book"] = (gd.get("book") or "").strip() or None
            params["class_hint"] = _extract_class(text)

        elif intent in ("forward", "backward"):
            raw_s = (gd.get("seconds") or "").strip()
            params["seconds"] = _word_to_int(raw_s) if raw_s else 30
            if params["seconds"] is None:
                params["seconds"] = 30

        return Command(intent=intent, params=params)

    return Command(intent="unknown", params={})
