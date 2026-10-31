"""Pure grading functions (no database access, easy to unit-test).

``question`` is any object with ``type``, ``points`` and ``options`` (each option with
``id``, ``text``, ``is_correct``): a ``QuizQuestion`` ORM instance or a test stub.
"""

from __future__ import annotations

import unicodedata
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.models.enums import QuestionType

_ZERO = Decimal("0")


class AnswerError(ValueError):
    """The submitted answer does not fit the question (wrong kind, foreign option, ...)."""


@dataclass(frozen=True, slots=True)
class GradedAnswer:
    """What gets stored for one question.

    ``is_correct`` / ``points`` are ``None`` only for manually graded answers that
    are waiting for the teacher.
    """

    selected_option_id: uuid.UUID | None
    answer_text: str | None
    is_correct: bool | None
    points: Decimal | None


def normalize_text(value: str) -> str:
    """Case-insensitive, whitespace-insensitive form used to compare short answers."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def grade_answer(
    question: Any,  # noqa: ANN401
    selected_option_id: uuid.UUID | None,
    answer_text: str | None,
) -> GradedAnswer:
    """Grade one answer.

    * No answer at all -> wrong, 0 points.
    * mcq / true_false -> needs ``selected_option_id`` of one of the question's options.
    * short_answer     -> needs ``answer_text``; compared with the accepted answers
      (options flagged correct). With no accepted answers it is graded manually.

    Raises:
        AnswerError: wrong kind of answer for the question type, or a foreign option id.
    """
    if selected_option_id is None and not answer_text:
        return GradedAnswer(None, None, False, _ZERO)

    if question.type in (QuestionType.MCQ, QuestionType.TRUE_FALSE):
        if selected_option_id is None:
            raise AnswerError("this question needs 'selected_option_id'")
        option = next((o for o in question.options if o.id == selected_option_id), None)
        if option is None:
            raise AnswerError("the selected option does not belong to this question")
        correct = bool(option.is_correct)
        return GradedAnswer(option.id, None, correct, question.points if correct else _ZERO)

    # short answer
    if not answer_text:
        raise AnswerError("this question needs 'answer_text'")
    text = answer_text.strip()
    accepted = {normalize_text(o.text) for o in question.options if o.is_correct}
    if not accepted:
        return GradedAnswer(None, text, None, None)  # manual grading
    correct = normalize_text(text) in accepted
    return GradedAnswer(None, text, correct, question.points if correct else _ZERO)