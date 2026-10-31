"""Quizzes, questions, options, attempts and answers.

Grading conventions
-------------------
* ``mcq`` / ``true_false``: options are stored in :class:`QuizOption`; exactly the
  options with ``is_correct=True`` are correct. ``true_false`` has two options
  ("True"/"False").
* ``short_answer``: every :class:`QuizOption` with ``is_correct=True`` is an
  accepted answer (compared case-insensitively by the service layer). If a
  question has no options the answer must be graded manually (``is_correct`` stays
  NULL until a teacher grades it).

Attempts
--------
A student may have several attempts when ``Quiz.allow_retake`` is true, but only one
*open* attempt (``submitted_at IS NULL``) at a time (partial unique index).

Purpose
-------
SQLAlchemy ORM models for the classroom quiz subsystem: teachers author
:class:`Quiz` objects containing :class:`QuizQuestion` rows (each with
:class:`QuizOption` answer choices), and students produce :class:`QuizAttempt`
rows containing one :class:`QuizAnswer` per question.

Schema history
--------------
* STEP 3 (init): quizzes, quiz_questions, quiz_options, quiz_attempts,
  quiz_answers created. ``quiz_attempts`` enforced ``UNIQUE(quiz_id,
  student_id)`` — i.e. one attempt per student, no retakes.
* STEP 10 (revision b7e2d4a91c35, migration ``20261010_0002_quiz_retakes``):

  - ``quizzes.allow_retake`` (bool, default false) — retakes are opt-in per quiz.
  - ``quiz_options.order_index`` (int, default 0) — preserves author order.
    The migration backfilled existing rows with
    ``row_number() OVER (PARTITION BY question_id ORDER BY id) - 1`` so legacy
    quizzes keep a stable order.
  - ``quiz_attempts``: the old ``uq_quiz_attempts_quiz_student`` UNIQUE
    constraint was **dropped** and replaced by

      * a plain index ``ix_quiz_attempts_quiz_id_student_id`` for lookups, and
      * a *partial* unique index ``uq_quiz_attempts_open_attempt`` on
        ``(quiz_id, student_id) WHERE submitted_at IS NULL``.

    The partial index enforces **at most one *open* attempt per student per
    quiz** at the DB level, while allowing any number of *finished* attempts
    (retakes). The service layer relies on this: concurrent ``POST /start``
    calls race, one wins, the loser catches ``IntegrityError`` and returns the
    winner's attempt.

Related modules
---------------
* Migration: ``alembic/versions/20261010_0002_quiz_retakes.py``
* Service:   ``app/services/quiz_service.py`` (CRUD, publish side-effects,
             start/submit, results, manual grading)
* Grading:   ``app/utils/quiz_grading.py`` (pure functions, no DB)
* Schemas:   ``app/schemas/quizzes.py`` (teacher vs student views — the student
             view strips ``is_correct`` and accepted short-answers)
* Tests:     ``tests/test_quiz_units.py`` (pure) and
             ``tests/test_quizzes_api.py`` (end-to-end, including retakes and
             the concurrent-``/start`` race)

Invariants
----------
* ``QuizAnswer`` is one row per (attempt, question) — even unanswered questions
  get a row with ``is_correct=False, points_awarded=0`` on submit. Manual-graded
  short answers get ``is_correct=None, points_awarded=None`` until a teacher
  PATCHes them.
* ``QuizAttempt.score`` is the sum of ``QuizAnswer.points_awarded`` after
  submit, and is recomputed from the sum after every manual grade.
* Once any attempt exists for a quiz, questions and ``published`` are locked
  (service returns 409) — but ``title``, ``description``, ``time_limit_minutes``,
  ``due_at``, and ``allow_retake`` remain editable.
"""


from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models._helpers import pg_enum, uuid_fk
from app.models.enums import QuestionType

if TYPE_CHECKING:
    from app.models.classroom import Classroom
    from app.models.user import User


class Quiz(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A timed or untimed quiz belonging to a classroom."""

    __tablename__ = "quizzes"
    __table_args__ = (
        CheckConstraint(
            "time_limit_minutes IS NULL OR time_limit_minutes > 0",
            name="time_limit_positive",
        ),
        Index("ix_quizzes_classroom_id_published", "classroom_id", "published"),
    )

    classroom_id: Mapped[uuid.UUID] = uuid_fk("classrooms.id", ondelete="CASCADE", index=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    allow_retake: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    classroom: Mapped[Classroom] = relationship(back_populates="quizzes")
    questions: Mapped[list[QuizQuestion]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="QuizQuestion.order_index",
    )
    attempts: Mapped[list[QuizAttempt]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Quiz {self.title!r} published={self.published}>"


class QuizQuestion(UUIDPrimaryKeyMixin, Base):
    """A single question inside a quiz."""

    __tablename__ = "quiz_questions"
    __table_args__ = (
        CheckConstraint("points >= 0", name="points_non_negative"),
        Index("ix_quiz_questions_quiz_id_order_index", "quiz_id", "order_index"),
    )

    quiz_id: Mapped[uuid.UUID] = uuid_fk("quizzes.id", ondelete="CASCADE", index=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[QuestionType] = mapped_column(
        pg_enum(QuestionType, "question_type"),
        nullable=False,
        default=QuestionType.MCQ,
    )
    points: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, default=Decimal("1"), server_default="1"
    )
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    quiz: Mapped[Quiz] = relationship(back_populates="questions")
    options: Mapped[list[QuizOption]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="QuizOption.order_index",
    )

    def __repr__(self) -> str:
        return f"<QuizQuestion {self.id} type={self.type}>"


class QuizOption(UUIDPrimaryKeyMixin, Base):
    """An answer choice (or accepted short answer) for a question."""

    __tablename__ = "quiz_options"

    question_id: Mapped[uuid.UUID] = uuid_fk("quiz_questions.id", ondelete="CASCADE")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    question: Mapped[QuizQuestion] = relationship(back_populates="options")

    def __repr__(self) -> str:
        return f"<QuizOption {self.id} correct={self.is_correct}>"


class QuizAttempt(UUIDPrimaryKeyMixin, Base):
    """One student's attempt at a quiz.

    Several attempts per student are allowed (retakes are enforced by the service
    through ``Quiz.allow_retake``), but the partial unique index
    ``uq_quiz_attempts_open_attempt`` guarantees at most ONE open attempt
    (``submitted_at IS NULL``) per student per quiz, even under concurrent requests.
    """

    __tablename__ = "quiz_attempts"
    __table_args__ = (
        Index("ix_quiz_attempts_quiz_id_student_id", "quiz_id", "student_id"),
        Index(
            "uq_quiz_attempts_open_attempt",
            "quiz_id",
            "student_id",
            unique=True,
            postgresql_where=sql_text("submitted_at IS NULL"),
        ),
    )

    quiz_id: Mapped[uuid.UUID] = uuid_fk("quizzes.id", ondelete="CASCADE", index=False)
    student_id: Mapped[uuid.UUID] = uuid_fk("users.id", ondelete="CASCADE")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))

    quiz: Mapped[Quiz] = relationship(back_populates="attempts")
    student: Mapped[User] = relationship(back_populates="quiz_attempts")
    answers: Mapped[list[QuizAnswer]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<QuizAttempt {self.id} score={self.score}>"


class QuizAnswer(UUIDPrimaryKeyMixin, Base):
    """A student's answer to one question within an attempt."""

    __tablename__ = "quiz_answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_quiz_answers_attempt_question"),
    )

    attempt_id: Mapped[uuid.UUID] = uuid_fk("quiz_attempts.id", ondelete="CASCADE", index=False)
    question_id: Mapped[uuid.UUID] = uuid_fk("quiz_questions.id", ondelete="CASCADE")
    answer_text: Mapped[str | None] = mapped_column(Text)
    selected_option_id: Mapped[uuid.UUID | None] = uuid_fk(
        "quiz_options.id", ondelete="SET NULL", nullable=True
    )
    # NULL = not graded yet (e.g. short answer awaiting teacher review).
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    points_awarded: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    attempt: Mapped[QuizAttempt] = relationship(back_populates="answers")
    question: Mapped[QuizQuestion] = relationship()
    selected_option: Mapped[QuizOption | None] = relationship()

    def __repr__(self) -> str:
        return f"<QuizAnswer {self.id} correct={self.is_correct}>"
















#  FIRST VERSION  -> D:\preparation\NI-AI Projects\FYP\educonnect\backend\alembic\versions\20261008_0001_init.py

# """Quizzes, questions, options, attempts and answers.

# Grading conventions
# -------------------
# * ``mcq`` / ``true_false``: options are stored in :class:`QuizOption`; exactly the
#   options with ``is_correct=True`` are correct. ``true_false`` has two options
#   ("True"/"False").
# * ``short_answer``: every :class:`QuizOption` with ``is_correct=True`` is an
#   accepted answer (compared case-insensitively by the service layer). If a
#   question has no options the answer must be graded manually (``is_correct`` stays
#   NULL until a teacher grades it).
# """

# from __future__ import annotations

# import uuid
# from datetime import datetime
# from decimal import Decimal
# from typing import TYPE_CHECKING

# from sqlalchemy import (
#     Boolean,
#     CheckConstraint,
#     DateTime,
#     Index,
#     Integer,
#     Numeric,
#     String,
#     Text,
#     UniqueConstraint,
#     false,
#     func,
# )
# from sqlalchemy.orm import Mapped, mapped_column, relationship

# from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
# from app.models._helpers import pg_enum, uuid_fk
# from app.models.enums import QuestionType

# if TYPE_CHECKING:
#     from app.models.classroom import Classroom
#     from app.models.user import User


# class Quiz(UUIDPrimaryKeyMixin, TimestampMixin, Base):
#     """A timed or untimed quiz belonging to a classroom."""

#     __tablename__ = "quizzes"
#     __table_args__ = (
#         CheckConstraint(
#             "time_limit_minutes IS NULL OR time_limit_minutes > 0",
#             name="time_limit_positive",
#         ),
#         Index("ix_quizzes_classroom_id_published", "classroom_id", "published"),
#     )

#     classroom_id: Mapped[uuid.UUID] = uuid_fk("classrooms.id", ondelete="CASCADE", index=False)
#     title: Mapped[str] = mapped_column(String(255), nullable=False)
#     description: Mapped[str | None] = mapped_column(Text)
#     time_limit_minutes: Mapped[int | None] = mapped_column(Integer)
#     due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
#     published: Mapped[bool] = mapped_column(
#         Boolean, nullable=False, default=False, server_default=false()
#     )

#     classroom: Mapped[Classroom] = relationship(back_populates="quizzes")
#     questions: Mapped[list[QuizQuestion]] = relationship(
#         back_populates="quiz",
#         cascade="all, delete-orphan",
#         passive_deletes=True,
#         order_by="QuizQuestion.order_index",
#     )
#     attempts: Mapped[list[QuizAttempt]] = relationship(
#         back_populates="quiz", cascade="all, delete-orphan", passive_deletes=True
#     )

#     def __repr__(self) -> str:
#         return f"<Quiz {self.title!r} published={self.published}>"


# class QuizQuestion(UUIDPrimaryKeyMixin, Base):
#     """A single question inside a quiz."""

#     __tablename__ = "quiz_questions"
#     __table_args__ = (
#         CheckConstraint("points >= 0", name="points_non_negative"),
#         Index("ix_quiz_questions_quiz_id_order_index", "quiz_id", "order_index"),
#     )

#     quiz_id: Mapped[uuid.UUID] = uuid_fk("quizzes.id", ondelete="CASCADE", index=False)
#     prompt: Mapped[str] = mapped_column(Text, nullable=False)
#     type: Mapped[QuestionType] = mapped_column(
#         pg_enum(QuestionType, "question_type"),
#         nullable=False,
#         default=QuestionType.MCQ,
#     )
#     points: Mapped[Decimal] = mapped_column(
#         Numeric(6, 2), nullable=False, default=Decimal("1"), server_default="1"
#     )
#     order_index: Mapped[int] = mapped_column(
#         Integer, nullable=False, default=0, server_default="0"
#     )

#     quiz: Mapped[Quiz] = relationship(back_populates="questions")
#     options: Mapped[list[QuizOption]] = relationship(
#         back_populates="question", cascade="all, delete-orphan", passive_deletes=True
#     )

#     def __repr__(self) -> str:
#         return f"<QuizQuestion {self.id} type={self.type}>"


# class QuizOption(UUIDPrimaryKeyMixin, Base):
#     """An answer choice (or accepted short answer) for a question."""

#     __tablename__ = "quiz_options"

#     question_id: Mapped[uuid.UUID] = uuid_fk("quiz_questions.id", ondelete="CASCADE")
#     text: Mapped[str] = mapped_column(Text, nullable=False)
#     is_correct: Mapped[bool] = mapped_column(
#         Boolean, nullable=False, default=False, server_default=false()
#     )

#     question: Mapped[QuizQuestion] = relationship(back_populates="options")

#     def __repr__(self) -> str:
#         return f"<QuizOption {self.id} correct={self.is_correct}>"


# class QuizAttempt(UUIDPrimaryKeyMixin, Base):
#     """One student's attempt at a quiz.

#     A unique constraint allows a single attempt per student per quiz. Drop
#     ``uq_quiz_attempts_quiz_student`` in a migration to support retakes.
#     """

#     __tablename__ = "quiz_attempts"
#     __table_args__ = (
#         UniqueConstraint("quiz_id", "student_id", name="uq_quiz_attempts_quiz_student"),
#     )

#     quiz_id: Mapped[uuid.UUID] = uuid_fk("quizzes.id", ondelete="CASCADE", index=False)
#     student_id: Mapped[uuid.UUID] = uuid_fk("users.id", ondelete="CASCADE")
#     started_at: Mapped[datetime] = mapped_column(
#         DateTime(timezone=True), server_default=func.now(), nullable=False
#     )
#     submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
#     score: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))

#     quiz: Mapped[Quiz] = relationship(back_populates="attempts")
#     student: Mapped[User] = relationship(back_populates="quiz_attempts")
#     answers: Mapped[list[QuizAnswer]] = relationship(
#         back_populates="attempt", cascade="all, delete-orphan", passive_deletes=True
#     )

#     def __repr__(self) -> str:
#         return f"<QuizAttempt {self.id} score={self.score}>"


# class QuizAnswer(UUIDPrimaryKeyMixin, Base):
#     """A student's answer to one question within an attempt."""

#     __tablename__ = "quiz_answers"
#     __table_args__ = (
#         UniqueConstraint("attempt_id", "question_id", name="uq_quiz_answers_attempt_question"),
#     )

#     attempt_id: Mapped[uuid.UUID] = uuid_fk("quiz_attempts.id", ondelete="CASCADE", index=False)
#     question_id: Mapped[uuid.UUID] = uuid_fk("quiz_questions.id", ondelete="CASCADE")
#     answer_text: Mapped[str | None] = mapped_column(Text)
#     selected_option_id: Mapped[uuid.UUID | None] = uuid_fk(
#         "quiz_options.id", ondelete="SET NULL", nullable=True
#     )
#     # NULL = not graded yet (e.g. short answer awaiting teacher review).
#     is_correct: Mapped[bool | None] = mapped_column(Boolean)
#     points_awarded: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

#     attempt: Mapped[QuizAttempt] = relationship(back_populates="answers")
#     question: Mapped[QuizQuestion] = relationship()
#     selected_option: Mapped[QuizOption | None] = relationship()

#     def __repr__(self) -> str:
#         return f"<QuizAnswer {self.id} correct={self.is_correct}>"
