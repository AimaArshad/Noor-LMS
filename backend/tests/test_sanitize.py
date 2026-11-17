"""Unit tests for text sanitisation (no database needed)."""

import pytest
from pydantic import ValidationError

from app.schemas import AnnouncementCreate, ClassroomCreate, RegisterRequest
from app.utils.sanitize import clean_line, clean_multiline


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Ann   Lee  ", "Ann Lee"),
        ("Ann\x00 Lee", "Ann Lee"),  # NUL would crash PostgreSQL
        ("line\none\r\ntwo", "line one two"),  # single-line fields collapse breaks
        ("evil\u202egpj", "evilgpj"),  # bidi override removed
        ("zero\u200bwidth", "zerowidth"),
        ("tab\there", "tab here"),
        ("e\u0301", "\u00e9"),  # NFC normalisation
        (
            "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645",
            "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645",
        ),  # ZWNJ kept
    ],
)
def test_clean_line(raw: str, expected: str) -> None:
    assert clean_line(raw) == expected


def test_clean_multiline_keeps_line_breaks_and_tabs() -> None:
    assert clean_multiline("a\r\nb\rc\u2028d\x07e\tf") == "a\nb\nc\nde\tf"


def test_lone_surrogates_are_dropped() -> None:
    assert clean_line("\ud800broken") == "broken"  # would fail UTF-8 encoding


def test_non_strings_pass_through_for_normal_validation() -> None:
    assert clean_line(5) == 5 and clean_multiline(None) is None


def test_schemas_apply_the_sanitiser() -> None:
    user = RegisterRequest(
        email="a@example.com", password="Passw0rdX", full_name="Ann\x00\u202e  Lee "
    )
    assert user.full_name == "Ann Lee"
    assert AnnouncementCreate(content="Hi\x00\r\nthere\x07 ").content == "Hi\nthere"
    assert ClassroomCreate(name="Math", section="\x00  ").section is None  # junk -> blank -> None
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@example.com", password="Passw0rdX", full_name="\x00\x07")
