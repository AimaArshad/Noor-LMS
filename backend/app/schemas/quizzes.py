"""Quiz, question, attempt and result schemas.

Security: student-facing schemas (``*Public`` / ``QuizStudentRead``) never contain
``is_correct`` and never expose accepted short answers.

``QuizRead`` / ``QuizStudentRead`` carry a ``view`` discriminator so endpoints that
return either one (``GET /quizzes/{id}``) have an unambiguous response model.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.models.enums import QuestionType
from app.schemas.common import (
    Body5k,
    Body10k,
    Grade,
    ORMModel,
    OptBody5k,
    OptBody10k,
    Points,
    RequestModel,
    Score,
    Str255,
    Str1000,
    UpdateModel,
)
from app.schemas.users import UserPublic

MAX_QUESTIONS = 200
MAX_OPTIONS = 10
#: ``quiz_attempts.score`` is NUMERIC(7,2)
MAX_TOTAL_POINTS = Decimal("99999.99")


# ------------------------------------------------------------------- creation
class QuizOptionCreate(RequestModel):
    text: Str1000
    is_correct: bool = False


class QuizQuestionCreate(RequestModel):
    """One question.

    Rules by type:
      * ``mcq``: 2-10 options, exactly one correct.
      * ``true_false``: exactly 2 options, exactly one correct.
      * ``short_answer``: options are the accepted answers (all ``is_correct=True``);
        no options means the answer is graded manually by the teacher.
    """

    prompt: Body5k
    type: QuestionType = QuestionType.MCQ
    points: Points = Decimal("1")
    order_index: int | None = Field(default=None, ge=0, le=1000)
    options: list[QuizOptionCreate] = Field(default_factory=list, max_length=MAX_OPTIONS)

    @model_validator(mode="after")
    def _validate_options(self) -> "QuizQuestionCreate":
        texts = [o.text.casefold() for o in self.options]
        if len(texts) != len(set(texts)):
            raise ValueError("Option texts must be unique within a question")

        correct = sum(1 for o in self.options if o.is_correct)

        if self.type == QuestionType.MCQ:
            if len(self.options) < 2:
                raise ValueError("Multiple-choice questions need at least 2 options")
            if correct != 1:
                raise ValueError("Multiple-choice questions need exactly one correct option")
        elif self.type == QuestionType.TRUE_FALSE:
            if len(self.options) != 2:
                raise ValueError("True/false questions need exactly 2 options")
            if correct != 1:
                raise ValueError("True/false questions need exactly one correct option")
        else:  # short_answer
            if any(not o.is_correct for o in self.options):
                raise ValueError("Every short-answer option is an accepted answer: set is_correct=true")
        return self


def _normalise_order(questions: list[QuizQuestionCreate]) -> list[QuizQuestionCreate]:
    """Fill missing ``order_index`` values with the list position."""
    for position, question in enumerate(questions):
        if question.order_index is None:
            question.order_index = position
    return questions


def _check_total_points(questions: list[QuizQuestionCreate]) -> None:
    if sum((q.points for q in questions), Decimal("0")) > MAX_TOTAL_POINTS:
        raise ValueError(f"The total points of a quiz must not exceed {MAX_TOTAL_POINTS}")


class QuizCreate(RequestModel):
    """Body of ``POST /classrooms/{id}/quizzes`` (quiz + nested questions + options)."""

    title: Str255
    description: OptBody10k = None
    time_limit_minutes: int | None = Field(default=None, gt=0, le=600)
    due_at: AwareDatetime | None = None
    published: bool = False
    allow_retake: bool = False
    questions: list[QuizQuestionCreate] = Field(default_factory=list, max_length=MAX_QUESTIONS)

    @model_validator(mode="after")
    def _validate_quiz(self) -> "QuizCreate":
        if self.published and not self.questions:
            raise ValueError("A published quiz must contain at least one question")
        _check_total_points(self.questions)
        _normalise_order(self.questions)
        return self


class QuizUpdate(UpdateModel):
    """PATCH body. If ``questions`` is sent it REPLACES all questions.

    The service refuses to replace questions (or unpublish) once attempts exist.
    """

    non_nullable = frozenset({"title", "published", "allow_retake", "questions"})

    title: Str255 | None = None
    description: OptBody10k = None
    time_limit_minutes: int | None = Field(default=None, gt=0, le=600)
    due_at: AwareDatetime | None = None
    published: bool | None = None
    allow_retake: bool | None = None
    questions: list[QuizQuestionCreate] | None = Field(default=None, max_length=MAX_QUESTIONS)

    @model_validator(mode="after")
    def _validate_quiz_patch(self) -> "QuizUpdate":
        if self.questions is not None:
            _check_total_points(self.questions)
            _normalise_order(self.questions)
            if self.published is True and not self.questions:
                raise ValueError("A published quiz must contain at least one question")
        return self


# ----------------------------------------------------------------------- reads
class QuizOptionRead(ORMModel):
    """Teacher view (includes the answer key)."""

    id: uuid.UUID
    text: str
    is_correct: bool


class QuizOptionPublic(ORMModel):
    """Student view: no answer key."""

    id: uuid.UUID
    text: str


class QuizQuestionRead(ORMModel):
    id: uuid.UUID
    quiz_id: uuid.UUID
    prompt: str
    type: QuestionType
    points: Score
    order_index: int
    options: list[QuizOptionRead] = Field(default_factory=list)


class QuizQuestionPublic(ORMModel):
    id: uuid.UUID
    prompt: str
    type: QuestionType
    points: Score
    order_index: int
    options: list[QuizOptionPublic] = Field(default_factory=list)

    @model_validator(mode="after")
    def _hide_accepted_answers(self) -> "QuizQuestionPublic":
        """Short-answer 'options' are the accepted answers: never show them to students."""
        if self.type == QuestionType.SHORT_ANSWER:
            self.options = []
        return self


class QuizSummary(ORMModel):
    """Quiz without questions (for list endpoints)."""

    id: uuid.UUID
    classroom_id: uuid.UUID
    title: str
    description: str | None = None
    time_limit_minutes: int | None = None
    due_at: datetime | None = None
    published: bool
    allow_retake: bool = False
    created_at: datetime
    updated_at: datetime


class QuizRead(QuizSummary):
    """Teacher view with full questions and answer key."""

    view: Literal["teacher"] = "teacher"
    questions: list[QuizQuestionRead] = Field(default_factory=list)


class QuizStudentRead(QuizSummary):
    """Student view: questions without the answer key."""

    view: Literal["student"] = "student"
    questions: list[QuizQuestionPublic] = Field(default_factory=list)


# -------------------------------------------------------------------- attempts
class AttemptStart(BaseModel):
    """Response of ``POST /quizzes/{id}/start`` (built by the service)."""

    attempt_id: uuid.UUID
    quiz_id: uuid.UUID
    started_at: datetime
    expires_at: datetime | None = Field(
        default=None, description="started_at + time limit; null when the quiz is untimed"
    )
    quiz: QuizStudentRead


class AnswerSubmit(RequestModel):
    """A student's answer to one question.

    Choice questions (mcq / true_false) need ``selected_option_id``;
    short-answer questions need ``answer_text``.
    """

    question_id: uuid.UUID
    selected_option_id: uuid.UUID | None = None
    answer_text: OptBody5k = None

    @model_validator(mode="after")
    def _require_an_answer(self) -> "AnswerSubmit":
        if self.selected_option_id is None and not self.answer_text:
            raise ValueError("Provide 'selected_option_id' or 'answer_text' (omit unanswered questions)")
        return self


class AttemptSubmit(RequestModel):
    """Body of ``POST /quizzes/{id}/submit``."""

    answers: list[AnswerSubmit] = Field(default_factory=list, max_length=MAX_QUESTIONS)

    @model_validator(mode="after")
    def _unique_questions(self) -> "AttemptSubmit":
        ids = [a.question_id for a in self.answers]
        if len(ids) != len(set(ids)):
            raise ValueError("Each question may be answered only once")
        return self


class GradeAnswer(RequestModel):
    """Body of the teacher's manual grading endpoint (must not exceed the question's points)."""

    points_awarded: Grade


class AnswerResult(ORMModel):
    """Per-question result. The answer key is never included."""

    question_id: uuid.UUID
    selected_option_id: uuid.UUID | None = None
    answer_text: str | None = None
    is_correct: bool | None = Field(default=None, description="null = awaiting manual grading")
    points_awarded: Score | None = None


class AttemptResult(ORMModel):
    """Result of one attempt. Built by the service (``QuizService.build_result``).

    * ``student`` is filled for teachers only.
    * ``answers`` is empty while the attempt is open (answers are stored on submit)
      and for attempts that were closed because the time limit ran out.
    """

    id: uuid.UUID
    quiz_id: uuid.UUID
    student_id: uuid.UUID
    student: UserPublic | None = None
    started_at: datetime
    submitted_at: datetime | None = None
    expires_at: datetime | None = None
    score: Score | None = None
    max_score: Score | None = None
    pending_manual_grading: bool = False
    answers: list[AnswerResult] = Field(default_factory=list)


class MyAttemptRead(BaseModel):
    """Response of ``GET /quizzes/{id}/my-attempt``."""

    attempt: AttemptResult | None = Field(
        default=None, description="Your latest attempt (open or finished); null if none"
    )
    attempts_used: int = Field(ge=0)
    can_start: bool = Field(description="True when POST /start would start or resume an attempt")


class QuizResults(BaseModel):
    """Response of ``GET /quizzes/{id}/results`` (teacher).

    * ``attempt_count``: attempts of current students (open and finished), for paging.
    * ``average_score``: average of every student's BEST submitted score.
    """

    quiz_id: uuid.UUID
    attempt_count: int = Field(ge=0)
    submitted_count: int = Field(ge=0)
    not_attempted_count: int = Field(ge=0)
    average_score: float | None = None
    max_score: Score
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    attempts: list[AttemptResult] = Field(default_factory=list)