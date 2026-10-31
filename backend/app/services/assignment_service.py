"""Assignment & submission business logic.

Covers: CRUD, publish side effects (to-do items), student submit (+ teacher
notifications), teacher grading and returning (+ student notification).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, joinedload

from app.core.assignment_deps import AssignmentAccess, SubmissionAccess
from app.models import (
    Assignment,
    AssignmentState,
    Classroom,
    ClassroomMember,
    MemberRole,
    Notification,
    Submission,
    SubmissionState,
    TodoItem,
    TodoRefType,
    User,
)
from app.schemas.assignments import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentUpdate,
    GradeSubmission,
    ReturnSubmission,
    SubmissionCreate,
    SubmissionList,
    SubmissionRead,
)
from app.schemas.common import AttachmentRef, Page
from app.services.file_service import FileService
from app.services.guards import ensure_not_archived

logger = logging.getLogger("educonnect.assignments")

_TODO_INSERT_CHUNK = 1000


def _clip(text: str, limit: int = 255) -> str:
    """Shorten ``text`` to ``limit`` characters (Notification.title is VARCHAR(255))."""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _assignment_link(classroom_id: uuid.UUID, assignment_id: uuid.UUID) -> str:
    return f"/classrooms/{classroom_id}/assignments/{assignment_id}"


class AssignmentService:
    """Stateless service; create one per request."""

    def __init__(self, db: AsyncSession, files: FileService) -> None:
        self.db = db
        self.files = files

    # ================================================================== #
    # Helpers
    # ================================================================== #
    async def _resolve_attachments(
        self, user: User, refs: list[AttachmentRef], current: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Canonical JSONB attachments for ``refs``.

        Files already present in ``current`` are kept as they are (so a co-teacher can
        edit an assignment whose files another teacher uploaded). Only NEW file ids go
        through the ownership check in ``FileService.resolve_attachments``.
        """
        kept = {item["file_id"]: item for item in current}
        fresh = [ref for ref in refs if str(ref.file_id) not in kept]
        resolved = {d["file_id"]: d for d in await self.files.resolve_attachments(user, fresh)}
        return [kept.get(str(ref.file_id)) or resolved[str(ref.file_id)] for ref in refs]

    async def _student_ids(self, classroom_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = (
            select(ClassroomMember.user_id)
            .join(User, User.id == ClassroomMember.user_id)
            .where(
                ClassroomMember.classroom_id == classroom_id,
                ClassroomMember.role == MemberRole.STUDENT,
                User.is_active.is_(True),
            )
        )
        return list((await self.db.scalars(stmt)).all())

    async def _teacher_ids(self, classroom_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = (
            select(ClassroomMember.user_id)
            .join(User, User.id == ClassroomMember.user_id)
            .where(
                ClassroomMember.classroom_id == classroom_id,
                ClassroomMember.role == MemberRole.TEACHER,
                User.is_active.is_(True),
            )
        )
        return list((await self.db.scalars(stmt)).all())

    # ---- to-do items ------------------------------------------------- #
    async def _create_todos(self, assignment: Assignment) -> None:
        """One to-do per active student. Idempotent (ON CONFLICT DO NOTHING)."""
        student_ids = await self._student_ids(assignment.classroom_id)
        for i in range(0, len(student_ids), _TODO_INSERT_CHUNK):
            rows = [
                {
                    "id": uuid.uuid4(),
                    "user_id": student_id,
                    "title": assignment.title,
                    "due_at": assignment.due_at,
                    "ref_type": TodoRefType.ASSIGNMENT,
                    "ref_id": assignment.id,
                    "is_done": False,
                }
                for student_id in student_ids[i : i + _TODO_INSERT_CHUNK]
            ]
            await self.db.execute(
                pg_insert(TodoItem)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["user_id", "ref_type", "ref_id"])
            )

    async def _sync_todos(self, assignment: Assignment) -> None:
        await self.db.execute(
            update(TodoItem)
            .where(
                TodoItem.ref_type == TodoRefType.ASSIGNMENT, TodoItem.ref_id == assignment.id
            )
            .values(title=assignment.title, due_at=assignment.due_at)
            .execution_options(synchronize_session=False)
        )

    async def _delete_todos(self, assignment_id: uuid.UUID) -> None:
        await self.db.execute(
            delete(TodoItem)
            .where(
                TodoItem.ref_type == TodoRefType.ASSIGNMENT, TodoItem.ref_id == assignment_id
            )
            .execution_options(synchronize_session=False)
        )

    # ---- presentation ------------------------------------------------ #
    @staticmethod
    def present(submission: Submission, *, hide_unreturned_grade: bool) -> SubmissionRead:
        """Build the API view. Students must not see grades before the work is returned."""
        view = SubmissionRead.model_validate(submission)
        if hide_unreturned_grade and submission.state == SubmissionState.GRADED:
            view = view.model_copy(
                update={
                    "state": SubmissionState.TURNED_IN,
                    "grade": None,
                    "feedback": None,
                    "graded_at": None,
                    "graded_by": None,
                }
            )
        return view

    async def _load_submission(self, submission_id: uuid.UUID) -> Submission:
        """Reload a submission with its student and the server-generated columns."""
        stmt = (
            select(Submission)
            .options(joinedload(Submission.student))
            .where(Submission.id == submission_id)
            .execution_options(populate_existing=True)
        )
        submission = await self.db.scalar(stmt)
        if submission is None:  # pragma: no cover - we just wrote it
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
        return submission

    # ================================================================== #
    # Assignments
    # ================================================================== #
    async def list_for_classroom(
        self,
        access_is_teacher: bool,
        classroom_id: uuid.UUID,
        *,
        state: AssignmentState | None,
        limit: int,
        offset: int,
    ) -> Page[AssignmentRead]:
        """Newest-first page. Students only ever get published assignments."""
        conditions: list[Any] = [Assignment.classroom_id == classroom_id]
        if not access_is_teacher:
            conditions.append(Assignment.state == AssignmentState.PUBLISHED)
        if state is not None:
            conditions.append(Assignment.state == state)

        total = (
            await self.db.scalar(select(func.count()).select_from(Assignment).where(*conditions))
            or 0
        )
        rows = (
            await self.db.scalars(
                select(Assignment)
                .where(*conditions)
                .order_by(Assignment.created_at.desc(), Assignment.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return Page[AssignmentRead](
            items=[AssignmentRead.model_validate(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def create(
        self, classroom: Classroom, user: User, data: AssignmentCreate
    ) -> Assignment:
        """Create an assignment (and to-do items when it is created already published).

        Raises:
            HTTPException: 403 archived classroom, 422 invalid attachment.
        """
        ensure_not_archived(classroom.is_archived)
        attachments = await self.files.resolve_attachments(user, data.attachments)
        assignment = Assignment(
            classroom_id=classroom.id,
            title=data.title,
            description=data.description,
            due_at=data.due_at,
            max_points=data.max_points,
            attachments=attachments,
            state=data.state,
        )
        self.db.add(assignment)
        await self.db.flush()
        if assignment.state == AssignmentState.PUBLISHED:
            await self._create_todos(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)  # server-generated timestamps
        return assignment

    async def update(self, access: AssignmentAccess, data: AssignmentUpdate) -> Assignment:
        """Apply a PATCH body and keep to-do items in sync.

        Raises:
            HTTPException: 403 archived, 409 lowering max_points below an existing grade or
                reverting to draft after submissions exist, 422 invalid attachment.
        """
        assignment = access.assignment
        ensure_not_archived(access.classroom.is_archived)

        changes = data.model_dump(exclude_unset=True)
        changes.pop("attachments", None)  # handled separately (UUID -> JSON-safe dicts)
        was_published = assignment.state == AssignmentState.PUBLISHED
        new_state = changes.get("state", assignment.state)

        if "max_points" in changes:
            over = await self.db.scalar(
                select(func.count())
                .select_from(Submission)
                .where(
                    Submission.assignment_id == assignment.id,
                    Submission.grade > changes["max_points"],
                )
            )
            if over:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "max_points is lower than a grade that was already given",
                )

        if was_published and new_state == AssignmentState.DRAFT:
            has_work = await self.db.scalar(
                select(Submission.id).where(Submission.assignment_id == assignment.id).limit(1)
            )
            if has_work is not None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "Cannot revert to draft: students have already submitted work",
                )

        if data.attachments is not None:
            assignment.attachments = await self._resolve_attachments(
                access.user, data.attachments, assignment.attachments
            )
        for field, value in changes.items():
            setattr(assignment, field, value)
        await self.db.flush()

        now_published = assignment.state == AssignmentState.PUBLISHED
        if now_published and not was_published:
            await self._create_todos(assignment)
        elif was_published and not now_published:
            await self._delete_todos(assignment.id)
        elif now_published and ({"title", "due_at"} & changes.keys()):
            await self._sync_todos(assignment)

        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def delete(self, access: AssignmentAccess) -> None:
        """Delete an assignment with its submissions, to-do items and comments.

        Deleted through the ORM so the ``after_delete`` listener removes its comments;
        submissions go away through ``ON DELETE CASCADE``.
        """
        ensure_not_archived(access.classroom.is_archived)
        await self._delete_todos(access.assignment.id)
        await self.db.delete(access.assignment)
        await self.db.commit()

    # ================================================================== #
    # Submissions (student side)
    # ================================================================== #
    async def submit(self, access: AssignmentAccess, data: SubmissionCreate) -> Submission:
        """Create or update the caller's submission and set it to ``turned_in``.

        Raises:
            HTTPException: 403 not a student / archived, 409 already graded (wait for return),
                409 concurrent duplicate, 422 invalid attachment.
        """
        if access.role != MemberRole.STUDENT:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only students can submit work")
        ensure_not_archived(access.classroom.is_archived)

        user, assignment, classroom = access.user, access.assignment, access.classroom
        # Read everything we need now: a rollback would expire these ORM objects.
        student_id, student_name = user.id, user.full_name
        assignment_id, assignment_title, classroom_id = assignment.id, assignment.title, classroom.id

        submission = await self.db.scalar(
            select(Submission)
            .where(Submission.assignment_id == assignment_id, Submission.student_id == student_id)
            .with_for_update()
        )
        if submission is not None and submission.state == SubmissionState.GRADED:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Your work was graded. You can resubmit after the teacher returns it.",
            )

        attachments = await self._resolve_attachments(
            user, data.attachments, submission.attachments if submission else []
        )
        now = _now()
        if submission is None:
            submission_id = uuid.uuid4()
            self.db.add(
                Submission(
                    id=submission_id,
                    assignment_id=assignment_id,
                    student_id=student_id,
                    content=data.content,
                    attachments=attachments,
                    state=SubmissionState.TURNED_IN,
                    submitted_at=now,
                )
            )
        else:
            submission_id = submission.id
            submission.content = data.content
            submission.attachments = attachments
            submission.state = SubmissionState.TURNED_IN
            submission.submitted_at = now
            submission.grade = None  # a resubmission after "returned" must be graded again
            submission.graded_at = None
            submission.graded_by = None

        for teacher_id in await self._teacher_ids(classroom_id):
            self.db.add(
                Notification(
                    user_id=teacher_id,
                    title=_clip(f"{student_name} turned in {assignment_title}"),
                    body=None,
                    type="submission_turned_in",
                    link=_assignment_link(classroom_id, assignment_id),
                )
            )
        try:
            await self.db.commit()
        except IntegrityError as exc:  # two simultaneous first submissions
            await self.db.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Your submission is being saved, please retry"
            ) from exc
        return await self._load_submission(submission_id)

    async def my_submission(self, access: AssignmentAccess) -> Submission | None:
        """The caller's own submission, or ``None`` if they have not submitted yet."""
        if access.role != MemberRole.STUDENT:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only students have a submission")
        return await self.db.scalar(
            select(Submission)
            .options(joinedload(Submission.student))
            .where(
                Submission.assignment_id == access.assignment.id,
                Submission.student_id == access.user.id,
            )
        )

    # ================================================================== #
    # Submissions (teacher side)
    # ================================================================== #
    async def list_submissions(
        self,
        access: AssignmentAccess,
        *,
        state: SubmissionState | None,
        limit: int,
        offset: int,
    ) -> SubmissionList:
        """Submissions of current students, sorted by name, plus how many have not submitted."""
        assignment_id, classroom_id = access.assignment.id, access.classroom.id
        is_current_student = and_(
            ClassroomMember.classroom_id == classroom_id,
            ClassroomMember.user_id == Submission.student_id,
            ClassroomMember.role == MemberRole.STUDENT,
        )
        conditions: list[Any] = [Submission.assignment_id == assignment_id]
        if state is not None:
            conditions.append(Submission.state == state)

        total = (
            await self.db.scalar(
                select(func.count())
                .select_from(Submission)
                .join(ClassroomMember, is_current_student)
                .where(*conditions)
            )
            or 0
        )
        rows = (
            await self.db.scalars(
                select(Submission)
                .join(ClassroomMember, is_current_student)
                .join(User, User.id == Submission.student_id)
                .options(contains_eager(Submission.student))
                .where(*conditions)
                .order_by(User.full_name, Submission.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()

        students = len(await self._student_ids(classroom_id))
        with_work = (
            await self.db.scalar(
                select(func.count())
                .select_from(Submission)
                .join(ClassroomMember, is_current_student)
                .where(Submission.assignment_id == assignment_id)
            )
            or 0
        )
        return SubmissionList(
            items=[self.present(row, hide_unreturned_grade=False) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
            not_submitted_count=max(students - with_work, 0),
        )

    async def grade(self, access: SubmissionAccess, data: GradeSubmission) -> Submission:
        """Give a grade (and optionally feedback). ``turned_in``/``graded`` become ``graded``;
        a ``returned`` submission stays ``returned`` (the edit is visible immediately).

        Raises:
            HTTPException: 403 archived, 409 nothing submitted, 422 grade above max_points.
        """
        ensure_not_archived(access.classroom.is_archived)
        submission, assignment = access.submission, access.assignment
        if submission.state == SubmissionState.ASSIGNED:
            raise HTTPException(status.HTTP_409_CONFLICT, "The student has not turned in work yet")
        if data.grade > Decimal(assignment.max_points):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Grade cannot exceed the maximum of {assignment.max_points} points",
            )

        submission_id = submission.id
        submission.grade = data.grade
        if "feedback" in data.model_fields_set:
            submission.feedback = data.feedback
        submission.graded_at = _now()
        submission.graded_by = access.user.id
        if submission.state != SubmissionState.RETURNED:
            submission.state = SubmissionState.GRADED
        await self.db.commit()
        return await self._load_submission(submission_id)

    async def return_work(
        self, access: SubmissionAccess, data: ReturnSubmission | None
    ) -> Submission:
        """Return the work to the student (grade and feedback become visible) and notify them.

        Raises:
            HTTPException: 403 archived, 409 nothing submitted or already returned.
        """
        ensure_not_archived(access.classroom.is_archived)
        submission, assignment = access.submission, access.assignment
        if submission.state == SubmissionState.ASSIGNED:
            raise HTTPException(status.HTTP_409_CONFLICT, "The student has not turned in work yet")
        if submission.state == SubmissionState.RETURNED:
            raise HTTPException(status.HTTP_409_CONFLICT, "This work was already returned")

        submission_id, student_id = submission.id, submission.student_id
        if data is not None and "feedback" in data.model_fields_set:
            submission.feedback = data.feedback
        submission.state = SubmissionState.RETURNED

        self.db.add(
            Notification(
                user_id=student_id,
                title=_clip(f"Your work on {assignment.title} was returned"),
                body=None,
                type="submission_returned",
                link=_assignment_link(assignment.classroom_id, assignment.id),
            )
        )
        await self.db.commit()
        return await self._load_submission(submission_id)