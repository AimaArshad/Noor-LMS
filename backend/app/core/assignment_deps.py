"""Access dependencies for ``/assignments/{assignment_id}`` and ``/submissions/{submission_id}``.

These routes carry no ``classroom_id``, so the dependency loads the child row,
finds its classroom and applies the normal classroom rules:

* non-members (and students looking at a DRAFT assignment) get ``404``
* members without enough rights get ``403``
"""

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.classroom_deps import ClassroomAccess, resolve_classroom_access
from app.core.deps import CurrentUser
from app.db.session import get_db
from app.models import Assignment, AssignmentState, Classroom, MemberRole, Submission, User


@dataclass(frozen=True, slots=True)
class AssignmentAccess:
    """The caller's relationship to one assignment."""

    assignment: Assignment
    classroom_access: ClassroomAccess

    @property
    def classroom(self) -> Classroom:
        return self.classroom_access.classroom

    @property
    def user(self) -> User:
        return self.classroom_access.user

    @property
    def role(self) -> MemberRole:
        return self.classroom_access.role

    @property
    def is_teacher(self) -> bool:
        return self.classroom_access.is_teacher


@dataclass(frozen=True, slots=True)
class SubmissionAccess:
    """A teacher's access to one submission."""

    submission: Submission
    assignment: Assignment
    classroom_access: ClassroomAccess

    @property
    def classroom(self) -> Classroom:
        return self.classroom_access.classroom

    @property
    def user(self) -> User:
        return self.classroom_access.user


async def get_assignment_access(
    assignment_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssignmentAccess:
    """Resolve an assignment the caller is allowed to see.

    Raises:
        HTTPException: 404 when it does not exist, the caller is not in its classroom,
            or it is a draft and the caller is not a teacher.
    """
    not_found = HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    assignment = await db.get(Assignment, assignment_id)
    if assignment is None:
        raise not_found
    try:
        access = await resolve_classroom_access(db, assignment.classroom_id, user)
    except HTTPException as exc:
        raise not_found from exc
    if not access.is_teacher and assignment.state != AssignmentState.PUBLISHED:
        raise not_found
    return AssignmentAccess(assignment=assignment, classroom_access=access)


async def require_assignment_teacher(
    access: Annotated[AssignmentAccess, Depends(get_assignment_access)],
) -> AssignmentAccess:
    """A teacher of the assignment's classroom (or an admin). Students get 403."""
    if not access.is_teacher:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only classroom teachers can do this")
    return access


async def require_submission_teacher(
    submission_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubmissionAccess:
    """Resolve a submission for a teacher of its classroom (or an admin)."""
    not_found = HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
    submission = await db.get(Submission, submission_id)
    if submission is None:
        raise not_found
    assignment = await db.get(Assignment, submission.assignment_id)
    if assignment is None:  # pragma: no cover - FK guarantees it exists
        raise not_found
    try:
        access = await resolve_classroom_access(db, assignment.classroom_id, user)
    except HTTPException as exc:
        raise not_found from exc
    if not access.is_teacher:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only classroom teachers can do this")
    return SubmissionAccess(submission=submission, assignment=assignment, classroom_access=access)


AssignmentMemberAccess = Annotated[AssignmentAccess, Depends(get_assignment_access)]
AssignmentTeacherAccess = Annotated[AssignmentAccess, Depends(require_assignment_teacher)]
SubmissionTeacherAccess = Annotated[SubmissionAccess, Depends(require_submission_teacher)]