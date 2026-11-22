"""Table-driven unit tests for voice_parser.parse_command.

No DB, no I/O — pure function tests.  Runs without pytest-asyncio.
"""

import pytest

from app.services.voice_parser import Command, parse_command


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cmd(text: str) -> Command:
    return parse_command(text)


# ---------------------------------------------------------------------------
# Table-driven test cases
# ---------------------------------------------------------------------------

# Format: (input_text, expected_intent, expected_params_subset)
CASES = [
    # --- playback ---
    ("play",                        "play",   {}),
    ("start reading",               "play",   {}),
    ("pause",                       "pause",  {}),
    ("hold on",                     "pause",  {}),
    ("stop",                        "stop",   {}),
    ("quit",                        "stop",   {}),
    ("resume",                      "resume", {}),
    ("continue",                    "resume", {}),
    ("unpause",                     "resume", {}),

    # --- speed ---
    ("speed up",                    "faster",  {}),
    ("go faster",                   "faster",  {}),
    ("slow down",                   "slower",  {}),
    ("go slower",                   "slower",  {}),
    ("decrease speed",              "slower",  {}),

    # --- seek ---
    ("forward",                     "forward",  {"seconds": 30}),
    ("go forward",                  "forward",  {"seconds": 30}),
    ("forward 15 seconds",          "forward",  {"seconds": 15}),
    ("forward thirty seconds",      "forward",  {"seconds": 30}),
    ("forward 60 seconds",          "forward",  {"seconds": 60}),
    ("backward",                    "backward", {"seconds": 30}),
    ("go backward 45 seconds",      "backward", {"seconds": 45}),
    ("back 10 seconds",             "backward", {"seconds": 10}),

    # --- chapters ---
    ("next chapter",                "next_chapter",     {}),
    ("skip chapter",                "next_chapter",     {}),
    ("previous chapter",            "previous_chapter", {}),
    ("last chapter",                "previous_chapter", {}),
    ("go back a chapter",           "previous_chapter", {}),

    # go_chapter with digit
    ("go to chapter 3",             "go_chapter", {"chapter": 3}),
    ("chapter 1",                   "go_chapter", {"chapter": 1}),
    ("open chapter 5",              "go_chapter", {"chapter": 5}),
    ("jump to chapter 10",          "go_chapter", {"chapter": 10}),

    # go_chapter with spoken number
    ("go to chapter two",           "go_chapter", {"chapter": 2}),
    ("chapter twenty three",        "go_chapter", {"chapter": 23}),
    ("chapter three in physics",    "go_chapter", {"chapter": 3, "book": "physics"}),

    # go_page
    ("go to page 5",                "go_page", {"page": 5}),
    ("page 12",                     "go_page", {"page": 12}),
    ("open page seven",             "go_page", {"page": 7}),
    ("page 3 in chemistry",         "go_page", {"page": 3, "book": "chemistry"}),

    # play_topic
    ("play topic waves and motion", "play_topic", {"topic": "waves and motion"}),
    ("find topic introduction",     "play_topic", {"topic": "introduction"}),
    ("go to topic photosynthesis",  "play_topic", {"topic": "photosynthesis"}),
    ("search topic the solar system","play_topic",{"topic": "the solar system"}),

    # --- meta ---
    ("where am i",                  "where_am_i", {}),
    ("current position",            "where_am_i", {}),
    ("help",                        "help",        {}),
    ("what can you say",            "help",        {}),
    ("commands",                    "help",        {}),

    # --- unknown ---
    ("",                            "unknown", {}),
    ("blah blah blah",              "unknown", {}),
    ("1234567",                     "unknown", {}),
]


@pytest.mark.parametrize("text,expected_intent,expected_params", CASES)
def test_parse_command(text: str, expected_intent: str, expected_params: dict) -> None:
    cmd = _cmd(text)
    assert cmd.intent == expected_intent, (
        f"Text={text!r}: expected intent {expected_intent!r}, got {cmd.intent!r}"
    )
    for key, val in expected_params.items():
        assert cmd.params.get(key) == val, (
            f"Text={text!r}: params[{key!r}] expected {val!r}, got {cmd.params.get(key)!r}"
        )


# ---------------------------------------------------------------------------
# Word-to-int edge cases
# ---------------------------------------------------------------------------

from app.services.voice_parser import _word_to_int  # noqa: E402


@pytest.mark.parametrize("text,expected", [
    ("0",        0),
    ("1",        1),
    ("12",       12),
    ("100",      100),
    ("one",      1),
    ("two",      2),
    ("ten",      10),
    ("twenty",   20),
    ("thirty",   30),
    ("twenty three", 23),
    ("forty five",   45),
    ("one hundred",  100),
    ("first",    1),
    ("1st",      1),
    ("second",   2),
    ("3rd",      3),
    ("twelfth",  12),
    ("eleven",   11),
    ("nineteen", 19),
    (None,       None),   # guard: not a string
])
def test_word_to_int(text, expected) -> None:
    if text is None:
        return  # skip sentinel
    assert _word_to_int(text) == expected, f"_word_to_int({text!r}) should be {expected}"


def test_word_to_int_unrecognised() -> None:
    assert _word_to_int("zork") is None


# ---------------------------------------------------------------------------
# Spoken-number extraction via full parse
# ---------------------------------------------------------------------------

def test_chapter_spoken_number_twenty_three() -> None:
    cmd = parse_command("go to chapter twenty three")
    assert cmd.intent == "go_chapter"
    assert cmd.params["chapter"] == 23


def test_chapter_ordinal_third() -> None:
    cmd = parse_command("chapter third")
    assert cmd.intent == "go_chapter"
    assert cmd.params["chapter"] == 3


def test_forward_spoken_seconds() -> None:
    cmd = parse_command("forward twenty seconds")
    assert cmd.intent == "forward"
    assert cmd.params["seconds"] == 20


def test_class_hint_extraction() -> None:
    cmd = parse_command("chapter 2 in physics 1st year")
    assert cmd.intent == "go_chapter"
    assert cmd.params["chapter"] == 2
    assert cmd.params["class_hint"] is not None
    assert "1st" in cmd.params["class_hint"]


def test_book_hint_extraction() -> None:
    cmd = parse_command("chapter 5 in biology")
    assert cmd.intent == "go_chapter"
    assert cmd.params["book"] == "biology"


def test_play_topic_with_class_hint() -> None:
    cmd = parse_command("play topic Newton laws in 2nd year")
    assert cmd.intent == "play_topic"
    assert "newton laws" in cmd.params["topic"].lower()
    assert cmd.params["class_hint"] is not None


def test_whitespace_normalisation() -> None:
    cmd = parse_command("  go   to   chapter  7  ")
    assert cmd.intent == "go_chapter"
    assert cmd.params["chapter"] == 7

