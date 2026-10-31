"""Unit tests: grading functions and quiz schemas (no database needed)."""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace as NS
from typing import Annotated

import pytest
from pydantic import Field, TypeAdapter, ValidationError

from app.models.enums import QuestionType
from app.schemas.quizzes import QuizCreate, QuizRead, QuizStudentRead
from app.utils.quiz_grading import AnswerError, grade_answer, normalize_text


def opt(text: str, correct: bool = False) -> NS:
    return NS(id=uuid.uuid4(), text=text, is_correct=correct)


def question(kind: QuestionType, options: list[NS], points: str = "2") -> NS:
    return NS(type=kind, points=Decimal(points), options=options)


# ------------------------------------------------------------------ grading
def test_normalize_text() -> None:
    assert normalize_text("  Ｐａｒｉｓ \n") == "paris"  # NFKC + case + whitespace
    assert normalize_text("City   of\tLight") == "city of light"


@pytest.mark.parametrize("kind", [QuestionType.MCQ, QuestionType.TRUE_FALSE])
def test_choice_questions(kind: QuestionType) -> None:
    right, wrong = opt("4", True), opt("5")
    q = question(kind, [wrong, right])

    good = grade_answer(q, right.id, None)
    assert good.is_correct is True and good.points == Decimal("2") and good.selected_option_id == right.id

    bad = grade_answer(q, wrong.id, None)
    assert bad.is_correct is False and bad.points == Decimal("0")

    blank = grade_answer(q, None, None)
    assert blank.is_correct is False and blank.points == Decimal("0") and blank.selected_option_id is None

    with pytest.raises(AnswerError):
        grade_answer(q, uuid.uuid4(), None)  # option of another question
    with pytest.raises(AnswerError):
        grade_answer(q, None, "4")  # text for a choice question


def test_choice_ignores_stray_text() -> None:
    right = opt("4", True)
    graded = grade_answer(question(QuestionType.MCQ, [right, opt("5")]), right.id, "ignored")
    assert graded.answer_text is None and graded.is_correct is True


def test_short_answer_with_accepted_answers() -> None:
    q = question(QuestionType.SHORT_ANSWER, [opt("Paris", True), opt("City of Light", True)])
    assert grade_answer(q, None, "  PARIS ").is_correct is True
    assert grade_answer(q, None, "city  of   LIGHT").is_correct is True
    wrong = grade_answer(q, None, "Lyon")
    assert wrong.is_correct is False and wrong.points == Decimal("0") and wrong.answer_text == "Lyon"
    with pytest.raises(AnswerError):
        grade_answer(q, uuid.uuid4(), None)  # option id for a short answer


def test_short_answer_without_accepted_answers_is_manual() -> None:
    q = question(QuestionType.SHORT_ANSWER, [])
    pending = grade_answer(q, None, "My essay")
    assert pending.is_correct is None and pending.points is None and pending.answer_text == "My essay"
    unanswered = grade_answer(q, None, None)
    assert unanswered.is_correct is False and unanswered.points == Decimal("0")


# ------------------------------------------------------------------ schemas
def test_total_points_limit() -> None:
    def mcq() -> dict:
        return {
            "prompt": "q",
            "points": "9999.99",
            "options": [{"text": "a", "is_correct": True}, {"text": "b"}],
        }

    QuizCreate(title="ok", questions=[mcq() for _ in range(10)])  # 99 999.90
    with pytest.raises(ValidationError):
        QuizCreate(title="too much", questions=[mcq() for _ in range(11)])


def test_allow_retake_defaults_to_false() -> None:
    assert QuizCreate(title="x").allow_retake is False


def _quiz_base() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": uuid.uuid4(),
        "classroom_id": uuid.uuid4(),
        "title": "Quiz",
        "published": True,
        "created_at": now,
        "updated_at": now,
    }


def test_view_discriminator_picks_the_right_model() -> None:
    adapter = TypeAdapter(Annotated[QuizRead | QuizStudentRead, Field(discriminator="view")])
    teacher = adapter.validate_python({**_quiz_base(), "view": "teacher", "questions": []})
    student = adapter.validate_python({**_quiz_base(), "view": "student", "questions": []})
    assert isinstance(teacher, QuizRead) and isinstance(student, QuizStudentRead)


def test_student_view_drops_the_answer_key() -> None:
    payload = {
        **_quiz_base(),
        "questions": [
            {
                "id": uuid.uuid4(),
                "prompt": "2+2?",
                "type": "mcq",
                "points": "2",
                "order_index": 0,
                "options": [{"id": uuid.uuid4(), "text": "4", "is_correct": True}],
            },
            {
                "id": uuid.uuid4(),
                "prompt": "Capital?",
                "type": "short_answer",
                "points": "1",
                "order_index": 1,
                "options": [{"id": uuid.uuid4(), "text": "Paris", "is_correct": True}],
            },
        ],
    }
    view = QuizStudentRead.model_validate(payload)
    dumped = json.dumps(view.model_dump(mode="json"))
    assert "is_correct" not in dumped and "Paris" not in dumped
    assert view.questions[0].options[0].text == "4" and view.questions[1].options == []