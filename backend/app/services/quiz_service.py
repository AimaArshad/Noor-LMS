"""Quiz & attempt business logic.

Covers: quiz CRUD with nested questions/options, publish side effects (to-do items),
student start / submit (auto-grading, time limit, retakes), my-attempt, teacher
results and manual grading of short answers.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, joinedload, selectinload

from app.core.quiz_deps import QuizAccess
from app.models import (
    Classroom,
    ClassroomMember,
    MemberRole,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizOption,
    QuizQuestion,
    TodoRefType,
    User,
)
from app.schemas.common import Page
from app.schemas.quizzes import (
    AnswerResult,
    AttemptResult,
    AttemptStart,
    AttemptSubmit,
    GradeAnswer,
    MyAttemptRead,
    QuizCreate,
    QuizQuestionCreate,
    QuizResults,
    QuizStudentRead,
    QuizSummary,
    QuizUpdate,
)
from app.schemas.users import UserPublic
from app.services import todo_sync
from app.services.guards import ensure_not_archived
from app.utils.quiz_grading import AnswerError, grade_answer

logger = logging.getLogger("educonnect.quizzes")

#: Network latency allowance: a submit is accepted up to this long after the deadline.
SUBMIT_GRACE = timedelta(seconds=10)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _deadline(started_at: datetime, time_limit_minutes: int | None) -> datetime | None:
    """When an attempt expires (``None`` for untimed quizzes)."""
    if time_limit_minutes is None:
        return None
    return started_at + timedelta(minutes=time_limit_minutes)


class QuizService:
    """Stateless service; create one per request."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ================================================================== #
    # Helpers
    # ================================================================== #
    @staticmethod
    def _require_student(access: QuizAccess) -> None:
        if access.role != MemberRole.STUDENT:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only students can take quizzes")

    async def load_full(self, quiz_id: uuid.UUID) -> Quiz:
        """Reload a quiz with questions and options (and fresh server-side columns)."""
        stmt = (
            select(Quiz)
            .options(selectinload(Quiz.questions).selectinload(QuizQuestion.options))
            .where(Quiz.id == quiz_id)
            .execution_options(populate_existing=True)
        )
        quiz = await self.db.scalar(stmt)
        if quiz is None:  # pragma: no cover - callers just wrote / resolved it
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Quiz not found")
        return quiz

    @staticmethod
    def _build_questions(
        quiz_id: uuid.UUID, items: list[QuizQuestionCreate]
    ) -> list[QuizQuestion]:
        """ORM objects for nested questions + options (options keep their list order)."""
        questions: list[QuizQuestion] = []
        for position, item in enumerate(items):
            question = QuizQuestion(
                quiz_id=quiz_id,
                prompt=item.prompt,
                type=item.type,
                points=item.points,
                order_index=item.order_index if item.order_index is not None else position,
            )
            question.options = [
                QuizOption(text=o.text, is_correct=o.is_correct, order_index=i)
                for i, o in enumerate(item.options)
            ]
            questions.append(question)
        return questions

    async def _question_meta(self, quiz_id: uuid.UUID) -> tuple[Decimal, dict[uuid.UUID, int]]:
        """(sum of all question points, question id -> position)."""
        rows = (
            await self.db.execute(
                select(QuizQuestion.id, QuizQuestion.points, QuizQuestion.order_index).where(
                    QuizQuestion.quiz_id == quiz_id
                )
            )
        ).all()
        return sum((r.points for r in rows), Decimal("0")), {r.id: r.order_index for r in rows}

    async def _load_attempt(self, attempt_id: uuid.UUID) -> QuizAttempt:
        """Reload an attempt with its answers and student."""
        stmt = (
            select(QuizAttempt)
            .options(joinedload(QuizAttempt.student), selectinload(QuizAttempt.answers))
            .where(QuizAttempt.id == attempt_id)
            .execution_options(populate_existing=True)
        )
        attempt = await self.db.scalar(stmt)
        if attempt is None:  # pragma: no cover - callers just wrote / resolved it
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")
        return attempt

    async def _result_for(
        self,
        attempt_id: uuid.UUID,
        quiz_id: uuid.UUID,
        time_limit: int | None,
        *,
        include_student: bool,
    ) -> AttemptResult:
        attempt = await self._load_attempt(attempt_id)
        max_score, order = await self._question_meta(quiz_id)
        return self.build_result(
            attempt,
            time_limit=time_limit,
            max_score=max_score,
            order=order,
            include_student=include_student,
        )

    @staticmethod
    def build_result(
        attempt: QuizAttempt,
        *,
        time_limit: int | None,
        max_score: Decimal,
        order: dict[uuid.UUID, int],
        include_student: bool,
    ) -> AttemptResult:
        """API view of an attempt. ``answers`` and ``student`` must be eager-loaded."""
        answers = sorted(attempt.answers, key=lambda a: (order.get(a.question_id, 0), a.question_id))
        return AttemptResult(
            id=attempt.id,
            quiz_id=attempt.quiz_id,
            student_id=attempt.student_id,
            student=UserPublic.model_validate(attempt.student) if include_student else None,
            started_at=attempt.started_at,
            submitted_at=attempt.submitted_at,
            expires_at=_deadline(attempt.started_at, time_limit),
            score=attempt.score,
            max_score=max_score,
            pending_manual_grading=any(a.is_correct is None for a in attempt.answers),
            answers=[AnswerResult.model_validate(a) for a in answers],
        )

    async def _close_expired(
        self,
        quiz_id: uuid.UUID,
        time_limit: int | None,
        student_id: uuid.UUID | None = None,
    ) -> None:
        """Close open attempts whose time (plus grace) ran out: submitted at the deadline, score 0.

        Answers are only stored on submit, so an expired attempt has none. Keeps students
        from being stuck behind a dead open attempt.
        """
        if time_limit is None:
            return
        limit = timedelta(minutes=time_limit)
        conditions: list[Any] = [
            QuizAttempt.quiz_id == quiz_id,
            QuizAttempt.submitted_at.is_(None),
            QuizAttempt.started_at < _now() - limit - SUBMIT_GRACE,
        ]
        if student_id is not None:
            conditions.append(QuizAttempt.student_id == student_id)
        await self.db.execute(
            update(QuizAttempt)
            .where(*conditions)
            .values(submitted_at=QuizAttempt.started_at + limit, score=Decimal("0"))
            .execution_options(synchronize_session=False)
        )
        await self.db.commit()

    # ================================================================== #
    # Quizzes
    # ================================================================== #
    async def list_for_classroom(
        self,
        classroom_id: uuid.UUID,
        *,
        include_drafts: bool,
        published: bool | None,
        limit: int,
        offset: int,
    ) -> Page[QuizSummary]:
        """Newest-first page. Students only ever get published quizzes."""
        conditions: list[Any] = [Quiz.classroom_id == classroom_id]
        if not include_drafts:
            conditions.append(Quiz.published.is_(True))
        elif published is not None:
            conditions.append(Quiz.published.is_(published))

        total = (
            await self.db.scalar(select(func.count()).select_from(Quiz).where(*conditions)) or 0
        )
        rows = (
            await self.db.scalars(
                select(Quiz)
                .where(*conditions)
                .order_by(Quiz.created_at.desc(), Quiz.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return Page[QuizSummary](
            items=[QuizSummary.model_validate(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def create(self, classroom: Classroom, data: QuizCreate) -> Quiz:
        """Create a quiz with its questions (and to-do items when published).

        Raises:
            HTTPException: 403 when the classroom is archived.
        """
        ensure_not_archived(classroom.is_archived)
        quiz = Quiz(
            classroom_id=classroom.id,
            title=data.title,
            description=data.description,
            time_limit_minutes=data.time_limit_minutes,
            due_at=data.due_at,
            published=data.published,
            allow_retake=data.allow_retake,
        )
        self.db.add(quiz)
        await self.db.flush()
        self.db.add_all(self._build_questions(quiz.id, data.questions))
        await self.db.flush()
        if quiz.published:
            await todo_sync.create_for_students(
                self.db,
                classroom_id=classroom.id,
                ref_type=TodoRefType.QUIZ,
                ref_id=quiz.id,
                title=quiz.title,
                due_at=quiz.due_at,
            )
        await self.db.commit()
        return await self.load_full(quiz.id)

    async def update(self, access: QuizAccess, data: QuizUpdate) -> Quiz:
        """Apply a PATCH body and keep to-do items in sync.

        Raises:
            HTTPException: 403 archived; 409 replacing questions or unpublishing after
                attempts exist; 422 a published quiz would have no questions.
        """
        ensure_not_archived(access.classroom.is_archived)
        quiz = access.quiz
        quiz_id = quiz.id

        changes = data.model_dump(exclude_unset=True)
        changes.pop("questions", None)
        new_questions = data.questions
        was_published = quiz.published

        attempts = (
            await self.db.scalar(
                select(func.count()).select_from(QuizAttempt).where(QuizAttempt.quiz_id == quiz_id)
            )
            or 0
        )
        if new_questions is not None and attempts:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Questions cannot be changed after students have started this quiz",
            )
        if was_published and changes.get("published") is False and attempts:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Cannot unpublish: students have already started this quiz",
            )

        for field, value in changes.items():
            setattr(quiz, field, value)
        if new_questions is not None:
            await self.db.execute(
                delete(QuizQuestion)
                .where(QuizQuestion.quiz_id == quiz_id)
                .execution_options(synchronize_session=False)  # options go via ON DELETE CASCADE
            )
            self.db.add_all(self._build_questions(quiz_id, new_questions))
        await self.db.flush()

        if quiz.published:
            question_count = await self.db.scalar(
                select(func.count()).select_from(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id)
            )
            if not question_count:  # the request is rolled back by get_db
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "A published quiz must contain at least one question",
                )

        if quiz.published and not was_published:
            await todo_sync.create_for_students(
                self.db,
                classroom_id=access.classroom.id,
                ref_type=TodoRefType.QUIZ,
                ref_id=quiz_id,
                title=quiz.title,
                due_at=quiz.due_at,
            )
        elif was_published and not quiz.published:
            await todo_sync.delete_for_ref(self.db, ref_type=TodoRefType.QUIZ, ref_id=quiz_id)
        elif quiz.published and ({"title", "due_at"} & changes.keys()):
            await todo_sync.sync_for_ref(
                self.db,
                ref_type=TodoRefType.QUIZ,
                ref_id=quiz_id,
                title=quiz.title,
                due_at=quiz.due_at,
            )

        await self.db.commit()
        return await self.load_full(quiz_id)

    async def delete(self, access: QuizAccess) -> None:
        """Delete a quiz with its questions, attempts, answers and to-do items."""
        ensure_not_archived(access.classroom.is_archived)
        await todo_sync.delete_for_ref(
            self.db, ref_type=TodoRefType.QUIZ, ref_id=access.quiz.id
        )
        await self.db.delete(access.quiz)  # children go through ON DELETE CASCADE
        await self.db.commit()

    # ================================================================== #
    # Attempts (student side)
    # ================================================================== #
    async def start(self, access: QuizAccess) -> tuple[AttemptStart, bool]:
        """Start an attempt, or resume the open one.

        Returns:
            ``(response, created)``: ``created`` is False when an open attempt was resumed.

        Raises:
            HTTPException: 403 not a student / archived, 409 already completed (no retake).
        """
        self._require_student(access)
        ensure_not_archived(access.classroom.is_archived)
        quiz = access.quiz
        quiz_id, student_id = quiz.id, access.user.id
        limit_minutes, allow_retake = quiz.time_limit_minutes, quiz.allow_retake

        await self._close_expired(quiz_id, limit_minutes, student_id)
        attempts = list(
            (
                await self.db.scalars(
                    select(QuizAttempt).where(
                        QuizAttempt.quiz_id == quiz_id, QuizAttempt.student_id == student_id
                    )
                )
            ).all()
        )
        attempt = next((a for a in attempts if a.submitted_at is None), None)
        created = False
        if attempt is None:
            if attempts and not allow_retake:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "You have already completed this quiz"
                )
            attempt = QuizAttempt(quiz_id=quiz_id, student_id=student_id, started_at=_now())
            self.db.add(attempt)
            try:
                await self.db.commit()
                created = True
            except IntegrityError:  # a concurrent /start won: resume its attempt
                await self.db.rollback()
                attempt = await self.db.scalar(
                    select(QuizAttempt).where(
                        QuizAttempt.quiz_id == quiz_id,
                        QuizAttempt.student_id == student_id,
                        QuizAttempt.submitted_at.is_(None),
                    )
                )
                if attempt is None:
                    raise HTTPException(
                        status.HTTP_409_CONFLICT, "Could not start the quiz, please retry"
                    ) from None

        attempt_id, started_at = attempt.id, attempt.started_at
        view = QuizStudentRead.model_validate(await self.load_full(quiz_id))
        return (
            AttemptStart(
                attempt_id=attempt_id,
                quiz_id=quiz_id,
                started_at=started_at,
                expires_at=_deadline(started_at, limit_minutes),
                quiz=view,
            ),
            created,
        )

    async def submit(self, access: QuizAccess, data: AttemptSubmit) -> AttemptResult:
        """Submit the open attempt: auto-grade, store one result row per question.

        Raises:
            HTTPException: 403 not a student / archived, 409 no open attempt or time limit
                exceeded, 422 an answer does not fit its question.
        """
        self._require_student(access)
        ensure_not_archived(access.classroom.is_archived)
        quiz = access.quiz
        quiz_id, student_id, limit_minutes = quiz.id, access.user.id, quiz.time_limit_minutes

        # FOR UPDATE: a concurrent double submit waits, then finds no open attempt (409).
        attempt = await self.db.scalar(
            select(QuizAttempt)
            .where(
                QuizAttempt.quiz_id == quiz_id,
                QuizAttempt.student_id == student_id,
                QuizAttempt.submitted_at.is_(None),
            )
            .with_for_update()
        )
        if attempt is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "No quiz attempt in progress. Start the quiz first."
            )
        attempt_id = attempt.id

        now = _now()
        deadline = _deadline(attempt.started_at, limit_minutes)
        if deadline is not None and now > deadline + SUBMIT_GRACE:
            # The attempt itself is closed (score 0) on the next start / my-attempt / results call.
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "The time limit has passed. This attempt can no longer be submitted.",
            )

        questions = list(
            (
                await self.db.scalars(
                    select(QuizQuestion)
                    .options(selectinload(QuizQuestion.options))
                    .where(QuizQuestion.quiz_id == quiz_id)
                    .order_by(QuizQuestion.order_index, QuizQuestion.id)
                )
            ).all()
        )
        known = {q.id for q in questions}
        given = {}
        for answer in data.answers:
            if answer.question_id not in known:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"Question {answer.question_id} does not belong to this quiz",
                )
            given[answer.question_id] = answer

        total = Decimal("0")
        rows: list[QuizAnswer] = []
        for question in questions:
            answer = given.get(question.id)
            try:
                graded = grade_answer(
                    question,
                    answer.selected_option_id if answer else None,
                    answer.answer_text if answer else None,
                )
            except AnswerError as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, f"Question {question.id}: {exc}"
                ) from exc
            if graded.points is not None:
                total += graded.points
            rows.append(
                QuizAnswer(
                    attempt_id=attempt_id,
                    question_id=question.id,
                    answer_text=graded.answer_text,
                    selected_option_id=graded.selected_option_id,
                    is_correct=graded.is_correct,
                    points_awarded=graded.points,
                )
            )

        attempt.submitted_at = now
        attempt.score = total
        self.db.add_all(rows)
        await self.db.commit()
        return await self._result_for(attempt_id, quiz_id, limit_minutes, include_student=False)

    async def my_attempt(self, access: QuizAccess) -> MyAttemptRead:
        """The caller's latest attempt plus whether they may (re)start."""
        self._require_student(access)
        quiz = access.quiz
        quiz_id, student_id = quiz.id, access.user.id
        limit_minutes, allow_retake = quiz.time_limit_minutes, quiz.allow_retake

        await self._close_expired(quiz_id, limit_minutes, student_id)
        rows = (
            await self.db.execute(
                select(QuizAttempt.id, QuizAttempt.submitted_at)
                .where(QuizAttempt.quiz_id == quiz_id, QuizAttempt.student_id == student_id)
                .order_by(QuizAttempt.started_at.desc(), QuizAttempt.id)
            )
        ).all()

        has_open = any(r.submitted_at is None for r in rows)
        can_start = not access.classroom.is_archived and (
            not rows or has_open or allow_retake
        )
        result = (
            await self._result_for(rows[0].id, quiz_id, limit_minutes, include_student=False)
            if rows
            else None
        )
        return MyAttemptRead(attempt=result, attempts_used=len(rows), can_start=can_start)

    # ================================================================== #
    # Teacher side
    # ================================================================== #
    async def results(self, access: QuizAccess, *, limit: int, offset: int) -> QuizResults:
        """All attempts of current students (sorted by name, newest attempt first) + statistics."""
        quiz = access.quiz
        quiz_id, classroom_id, limit_minutes = quiz.id, access.classroom.id, quiz.time_limit_minutes
        await self._close_expired(quiz_id, limit_minutes)

        is_current_student = and_(
            ClassroomMember.classroom_id == classroom_id,
            ClassroomMember.user_id == QuizAttempt.student_id,
            ClassroomMember.role == MemberRole.STUDENT,
        )

        def count_attempts(*extra: Any) -> Any:  # noqa: ANN401
            return (
                select(func.count())
                .select_from(QuizAttempt)
                .join(ClassroomMember, is_current_student)
                .where(QuizAttempt.quiz_id == quiz_id, *extra)
            )

        total = await self.db.scalar(count_attempts()) or 0
        submitted = await self.db.scalar(count_attempts(QuizAttempt.submitted_at.is_not(None))) or 0
        attempted = (
            await self.db.scalar(
                select(func.count(func.distinct(QuizAttempt.student_id)))
                .select_from(QuizAttempt)
                .join(ClassroomMember, is_current_student)
                .where(QuizAttempt.quiz_id == quiz_id)
            )
            or 0
        )
        students = len(await todo_sync.active_student_ids(self.db, classroom_id))

        best = (
            select(func.max(QuizAttempt.score).label("best"))
            .select_from(QuizAttempt)
            .join(ClassroomMember, is_current_student)
            .where(QuizAttempt.quiz_id == quiz_id, QuizAttempt.submitted_at.is_not(None))
            .group_by(QuizAttempt.student_id)
            .subquery()
        )
        average = await self.db.scalar(select(func.avg(best.c.best)))

        attempts = (
            await self.db.scalars(
                select(QuizAttempt)
                .join(ClassroomMember, is_current_student)
                .join(User, User.id == QuizAttempt.student_id)
                .options(contains_eager(QuizAttempt.student), selectinload(QuizAttempt.answers))
                .where(QuizAttempt.quiz_id == quiz_id)
                .order_by(User.full_name, QuizAttempt.started_at.desc(), QuizAttempt.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()

        max_score, order = await self._question_meta(quiz_id)
        return QuizResults(
            quiz_id=quiz_id,
            attempt_count=total,
            submitted_count=submitted,
            not_attempted_count=max(students - attempted, 0),
            average_score=round(float(average), 2) if average is not None else None,
            max_score=max_score,
            limit=limit,
            offset=offset,
            attempts=[
                self.build_result(
                    a,
                    time_limit=limit_minutes,
                    max_score=max_score,
                    order=order,
                    include_student=True,
                )
                for a in attempts
            ],
        )

    async def regrade_answer(
        self,
        access: QuizAccess,
        attempt_id: uuid.UUID,
        question_id: uuid.UUID,
        data: GradeAnswer,
    ) -> AttemptResult:
        """Set the points of one answer (manual grading / teacher override), then re-total the score.

        ``is_correct`` becomes true only for full points.

        Raises:
            HTTPException: 403 archived, 404 unknown attempt/answer, 409 attempt not submitted,
                422 more points than the question is worth.
        """
        ensure_not_archived(access.classroom.is_archived)
        quiz_id, limit_minutes = access.quiz.id, access.quiz.time_limit_minutes

        attempt = await self.db.scalar(
            select(QuizAttempt)
            .where(QuizAttempt.id == attempt_id, QuizAttempt.quiz_id == quiz_id)
            .with_for_update()
        )
        if attempt is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")
        if attempt.submitted_at is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "This attempt has not been submitted yet")

        answer = await self.db.scalar(
            select(QuizAnswer).where(
                QuizAnswer.attempt_id == attempt_id, QuizAnswer.question_id == question_id
            )
        )
        question = await self.db.get(QuizQuestion, question_id)
        if answer is None or question is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Answer not found")
        if data.points_awarded > question.points:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"This question is worth at most {question.points} points",
            )

        answer.points_awarded = data.points_awarded
        answer.is_correct = data.points_awarded >= question.points
        await self.db.flush()
        attempt.score = await self.db.scalar(
            select(func.coalesce(func.sum(QuizAnswer.points_awarded), 0)).where(
                QuizAnswer.attempt_id == attempt_id
            )
        )
        await self.db.commit()
        return await self._result_for(attempt_id, quiz_id, limit_minutes, include_student=True)