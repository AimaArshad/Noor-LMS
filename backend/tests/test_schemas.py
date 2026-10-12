"""Validation tests for the Pydantic schemas (no database required)."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.enums import QuestionType, UserRole
from app.schemas import (
    AnswerSubmit,
    AssignmentCreate,
    AttemptResult,
    AttemptSubmit,
    ClassroomJoin,
    ClassroomUpdate,
    QuizCreate,
    QuizQuestionPublic,
    RegisterRequest,
    SubmissionCreate,
    TodoCreate,
)


# ------------------------------------------------------------------- auth
def test_register_normalises_email_and_name() -> None:
    body = RegisterRequest(email="Foo@Example.COM", password="Passw0rdX", full_name="  Ann Lee  ")
    assert body.email == "foo@example.com"
    assert body.full_name == "Ann Lee"
    assert body.role == UserRole.STUDENT


@pytest.mark.parametrize("password", ["short1", "allletters", "12345678", "a1" * 40])
def test_register_rejects_bad_passwords(password: str) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@example.com", password=password, full_name="A")


def test_register_rejects_admin_role_and_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@example.com", password="Passw0rdX", full_name="A", role="admin")
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@example.com", password="Passw0rdX", full_name="A", is_active=False)


# -------------------------------------------------------------- classrooms
def test_join_code_is_normalised() -> None:
    assert ClassroomJoin(code=" ab3-k7 ".replace("-", "")).code == "AB3K7"
    with pytest.raises(ValidationError):
        ClassroomJoin(code="ab!!")


def test_patch_requires_a_field_and_rejects_null_for_required_columns() -> None:
    with pytest.raises(ValidationError):
        ClassroomUpdate()
    with pytest.raises(ValidationError):
        ClassroomUpdate(name=None)
    update = ClassroomUpdate(section="  ")  # blank clears the optional field
    assert update.model_dump(exclude_unset=True) == {"section": None}


# ------------------------------------------------------------- assignments
def test_assignment_points_must_be_positive_and_dates_aware() -> None:
    with pytest.raises(ValidationError):
        AssignmentCreate(title="HW", max_points=0)
    with pytest.raises(ValidationError):
        AssignmentCreate(title="HW", due_at=datetime(2026, 12, 1, 12, 0))  # naive
    ok = AssignmentCreate(title=" HW ", due_at=datetime(2026, 12, 1, tzinfo=timezone.utc))
    assert ok.title == "HW"


def test_submission_needs_content_or_attachment() -> None:
    with pytest.raises(ValidationError):
        SubmissionCreate()
    with pytest.raises(ValidationError):
        SubmissionCreate(content="   ")
    assert SubmissionCreate(content="my answer").content == "my answer"


# ------------------------------------------------------------------ quizzes
def _mcq(correct: int = 1) -> dict:
    return {
        "prompt": "2+2?",
        "type": "mcq",
        "points": "2",
        # "options": [{"text": str(i), "is_correct": i < correct} for i in range(3, 3 + 3)],   #Value error, Multiple-choice questions need exactly one correct option # it detected that the test was constructing an MCQ with zero correct answers and refused to let it through.
         "options": [
            {"text": f"option-{i}", "is_correct": i < correct}
            for i in range(3)
        ],
    }


def test_quiz_nested_creation_and_ordering() -> None:
    quiz = QuizCreate(title="Quiz 1", published=True, questions=[_mcq(), _mcq()])
    assert [q.order_index for q in quiz.questions] == [0, 1]


@pytest.mark.parametrize("correct", [0, 2])
def test_mcq_requires_exactly_one_correct_option(correct: int) -> None:
    with pytest.raises(ValidationError):
        QuizCreate(title="Q", questions=[_mcq(correct)])


def test_published_quiz_needs_questions() -> None:
    with pytest.raises(ValidationError):
        QuizCreate(title="Q", published=True)


def test_question_points_must_be_positive() -> None:
    bad = _mcq()
    bad["points"] = "0"
    with pytest.raises(ValidationError):
        QuizCreate(title="Q", questions=[bad])


def test_true_false_needs_two_options() -> None:
    q = {"prompt": "Sky is blue", "type": "true_false", "options": [{"text": "True", "is_correct": True}]}
    with pytest.raises(ValidationError):
        QuizCreate(title="Q", questions=[q])


def test_student_view_hides_short_answer_key() -> None:
    qid, oid = uuid.uuid4(), uuid.uuid4()
    view = QuizQuestionPublic.model_validate(
        {
            "id": qid,
            "prompt": "Capital of France?",
            "type": QuestionType.SHORT_ANSWER,
            "points": Decimal("1"),
            "order_index": 0,
            "options": [{"id": oid, "text": "Paris"}],
        }
    )
    assert view.options == []
    assert "is_correct" not in QuizQuestionPublic.model_fields["options"].annotation.__args__[0].model_fields


def test_attempt_submit_rules() -> None:
    qid = uuid.uuid4()
    with pytest.raises(ValidationError):
        AnswerSubmit(question_id=qid)
    with pytest.raises(ValidationError):
        AttemptSubmit(answers=[{"question_id": qid, "answer_text": "a"}, {"question_id": qid, "answer_text": "b"}])


def test_decimals_serialise_as_json_numbers() -> None:
    result = AttemptResult(
        id=uuid.uuid4(),
        quiz_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        started_at=datetime.now(timezone.utc),
        score=Decimal("8.50"),
    )
    assert result.model_dump(mode="json")["score"] == 8.5


# --------------------------------------------------------------------- todo
def test_todo_ref_pair() -> None:
    with pytest.raises(ValidationError):
        TodoCreate(title="Read", ref_type="assignment")
    assert TodoCreate(title="Read").ref_id is None