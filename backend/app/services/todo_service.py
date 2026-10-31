"""To-do logic: explicit items merged with derived pending assignments / quizzes.

Derived items are *materialized*: every published assignment/quiz in the student's
classrooms that has no to-do row and no completed work gets one (``ON CONFLICT DO NOTHING``)
the first time ``GET /todo`` runs. So every item has a real id for ``PATCH /todo/{id}``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Assignment,
    AssignmentState,
    Classroom,
    ClassroomMember,
    MemberRole,
    Quiz,
    QuizAttempt,
    Submission,
    TodoItem,
    TodoRefType,
)
from app.schemas.todo import TodoList, TodoRead

_FAR_FUTURE = datetime(9999, 12, 31, tzinfo=timezone.utc)
_INSERT_CHUNK = 1000


def _sort_key(item: TodoRead) -> tuple[Any, ...]:
    """Open items first; earliest due date first; items without a due date last."""
    return (item.is_done, item.due_at is None, item.due_at or _FAR_FUTURE, item.created_at, str(item.id))


class TodoService:
    """Stateless service; create one per request."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    async def _student_classrooms(self, user_id: uuid.UUID) -> dict[uuid.UUID, str]:
        """Active (non-archived) classrooms where the user is a STUDENT: id -> name."""
        rows = await self.db.execute(
            select(Classroom.id, Classroom.name)
            .join(ClassroomMember, ClassroomMember.classroom_id == Classroom.id)
            .where(
                ClassroomMember.user_id == user_id,
                ClassroomMember.role == MemberRole.STUDENT,
                Classroom.is_archived.is_(False),
            )
        )
        return {row.id: row.name for row in rows.all()}

    async def _materialize(self, user_id: uuid.UUID, classroom_ids: list[uuid.UUID]) -> None:
        """Insert to-do rows for pending work that has none yet (idempotent)."""
        if not classroom_ids:
            return

        a_has_row = (
            select(TodoItem.id)
            .where(
                TodoItem.user_id == user_id,
                TodoItem.ref_type == TodoRefType.ASSIGNMENT,
                TodoItem.ref_id == Assignment.id,
            )
            .exists()
        )
        a_done = (
            select(Submission.id)
            .where(Submission.assignment_id == Assignment.id, Submission.student_id == user_id)
            .exists()
        )
        q_has_row = (
            select(TodoItem.id)
            .where(
                TodoItem.user_id == user_id,
                TodoItem.ref_type == TodoRefType.QUIZ,
                TodoItem.ref_id == Quiz.id,
            )
            .exists()
        )
        q_done = (
            select(QuizAttempt.id)
            .where(
                QuizAttempt.quiz_id == Quiz.id,
                QuizAttempt.student_id == user_id,
                QuizAttempt.submitted_at.is_not(None),
            )
            .exists()
        )

        assignments = await self.db.execute(
            select(Assignment.id, Assignment.title, Assignment.due_at).where(
                Assignment.classroom_id.in_(classroom_ids),
                Assignment.state == AssignmentState.PUBLISHED,
                ~a_has_row,
                ~a_done,
            )
        )
        quizzes = await self.db.execute(
            select(Quiz.id, Quiz.title, Quiz.due_at).where(
                Quiz.classroom_id.in_(classroom_ids),
                Quiz.published.is_(True),
                ~q_has_row,
                ~q_done,
            )
        )

        rows: list[dict[str, Any]] = [
            self._new_row(user_id, TodoRefType.ASSIGNMENT, r.id, r.title, r.due_at)
            for r in assignments.all()
        ] + [
            self._new_row(user_id, TodoRefType.QUIZ, r.id, r.title, r.due_at) for r in quizzes.all()
        ]
        if not rows:
            return
        for i in range(0, len(rows), _INSERT_CHUNK):
            await self.db.execute(
                pg_insert(TodoItem)
                .values(rows[i : i + _INSERT_CHUNK])
                .on_conflict_do_nothing(index_elements=["user_id", "ref_type", "ref_id"])
            )
        await self.db.commit()

    @staticmethod
    def _new_row(
        user_id: uuid.UUID,
        ref_type: TodoRefType,
        ref_id: uuid.UUID,
        title: str,
        due_at: datetime | None,
    ) -> dict[str, Any]:
        return {
            "id": uuid.uuid4(),
            "user_id": user_id,
            "title": title,
            "due_at": due_at,
            "ref_type": ref_type,
            "ref_id": ref_id,
            "is_done": False,
        }

    async def _build(
        self,
        user_id: uuid.UUID,
        rows: list[TodoItem],
        classrooms: dict[uuid.UUID, str],
    ) -> list[TodoRead]:
        """API views for ``rows``. Rows whose target is gone / draft / outside the student's
        active classrooms are skipped."""
        a_ids = {r.ref_id for r in rows if r.ref_type == TodoRefType.ASSIGNMENT and r.ref_id}
        q_ids = {r.ref_id for r in rows if r.ref_type == TodoRefType.QUIZ and r.ref_id}

        assignments: dict[uuid.UUID, Any] = {}
        done_assignments: set[uuid.UUID] = set()
        if a_ids:
            found = await self.db.execute(
                select(
                    Assignment.id,
                    Assignment.classroom_id,
                    Assignment.state,
                    Assignment.title,
                    Assignment.due_at,
                ).where(Assignment.id.in_(a_ids))
            )
            assignments = {r.id: r for r in found.all()}
            done_assignments = set(
                (
                    await self.db.scalars(
                        select(Submission.assignment_id).where(
                            Submission.student_id == user_id, Submission.assignment_id.in_(a_ids)
                        )
                    )
                ).all()
            )

        quizzes: dict[uuid.UUID, Any] = {}
        done_quizzes: set[uuid.UUID] = set()
        if q_ids:
            found = await self.db.execute(
                select(Quiz.id, Quiz.classroom_id, Quiz.published, Quiz.title, Quiz.due_at).where(
                    Quiz.id.in_(q_ids)
                )
            )
            quizzes = {r.id: r for r in found.all()}
            done_quizzes = set(
                (
                    await self.db.scalars(
                        select(QuizAttempt.quiz_id).where(
                            QuizAttempt.student_id == user_id,
                            QuizAttempt.quiz_id.in_(q_ids),
                            QuizAttempt.submitted_at.is_not(None),
                        )
                    )
                ).all()
            )

        now = datetime.now(timezone.utc)
        views: list[TodoRead] = []
        for row in rows:
            classroom_id: uuid.UUID | None = None
            link: str | None = None
            completed = False
            title, due_at = row.title, row.due_at

            if row.ref_type == TodoRefType.ASSIGNMENT:
                target = assignments.get(row.ref_id)
                if (
                    target is None
                    or target.state != AssignmentState.PUBLISHED
                    or target.classroom_id not in classrooms
                ):
                    continue
                title, due_at, classroom_id = target.title, target.due_at, target.classroom_id
                completed = row.ref_id in done_assignments
                link = f"/classrooms/{classroom_id}/assignments/{row.ref_id}"
            elif row.ref_type == TodoRefType.QUIZ:
                target = quizzes.get(row.ref_id)
                if target is None or not target.published or target.classroom_id not in classrooms:
                    continue
                title, due_at, classroom_id = target.title, target.due_at, target.classroom_id
                completed = row.ref_id in done_quizzes
                link = f"/classrooms/{classroom_id}/quizzes/{row.ref_id}"

            is_done = row.is_done or completed
            views.append(
                TodoRead(
                    id=row.id,
                    user_id=row.user_id,
                    title=title,
                    due_at=due_at,
                    ref_type=row.ref_type,
                    ref_id=row.ref_id,
                    is_done=is_done,
                    created_at=row.created_at,
                    classroom_id=classroom_id,
                    classroom_name=classrooms.get(classroom_id) if classroom_id else None,
                    link=link,
                    is_overdue=bool(not is_done and due_at is not None and due_at < now),
                )
            )
        return views

    # ------------------------------------------------------------------ #
    # Queries / commands
    # ------------------------------------------------------------------ #
    async def list_for_user(
        self, user_id: uuid.UUID, *, is_done: bool | None, limit: int, offset: int
    ) -> TodoList:
        """The caller's to-do list: explicit items + derived pending work, soonest due first."""
        classrooms = await self._student_classrooms(user_id)
        await self._materialize(user_id, list(classrooms))

        rows = list(
            (await self.db.scalars(select(TodoItem).where(TodoItem.user_id == user_id))).all()
        )
        views = await self._build(user_id, rows, classrooms)

        pending = sum(1 for v in views if not v.is_done)
        overdue = sum(1 for v in views if v.is_overdue)
        if is_done is not None:
            views = [v for v in views if v.is_done == is_done]
        views.sort(key=_sort_key)
        return TodoList(
            items=views[offset : offset + limit],
            total=len(views),
            limit=limit,
            offset=offset,
            pending_count=pending,
            overdue_count=overdue,
        )

    async def mark(self, user_id: uuid.UUID, todo_id: uuid.UUID, is_done: bool) -> TodoRead:
        """Set the caller's own flag. Work that is already turned in still shows as done.

        Raises:
            HTTPException: 404 when the item is not the caller's, or no longer applies.
        """
        row = await self.db.scalar(
            select(TodoItem).where(TodoItem.id == todo_id, TodoItem.user_id == user_id)
        )
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "To-do item not found")

        row.is_done = is_done
        views = await self._build(user_id, [row], await self._student_classrooms(user_id))
        if not views:  # target deleted / unpublished / classroom left or archived
            raise HTTPException(status.HTTP_404_NOT_FOUND, "To-do item not found")
        await self.db.commit()
        return views[0]