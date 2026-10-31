"""Access dependencies for ``/quizzes/{quiz_id}`` routes.

The route carries no ``classroom_id``, so the dependency loads the quiz, finds its
classroom and applies the normal classroom rules:

* non-members (and students looking at an unpublished quiz) get ``404``
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
from app.models import Classroom, MemberRole, Quiz, User


@dataclass(frozen=True, slots=True)
class QuizAccess:
    """The caller's relationship to one quiz."""

    quiz: Quiz
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


async def get_quiz_access(
    quiz_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QuizAccess:
    """Resolve a quiz the caller is allowed to see.

    Raises:
        HTTPException: 404 when it does not exist, the caller is not in its classroom,
            or it is unpublished and the caller is not a teacher.
    """
    not_found = HTTPException(status.HTTP_404_NOT_FOUND, "Quiz not found")
    quiz = await db.get(Quiz, quiz_id)
    if quiz is None:
        raise not_found
    try:
        access = await resolve_classroom_access(db, quiz.classroom_id, user)
    except HTTPException as exc:
        raise not_found from exc
    if not access.is_teacher and not quiz.published:
        raise not_found
    return QuizAccess(quiz=quiz, classroom_access=access)


async def require_quiz_teacher(
    access: Annotated[QuizAccess, Depends(get_quiz_access)],
) -> QuizAccess:
    """A teacher of the quiz's classroom (or an admin). Students get 403."""
    if not access.is_teacher:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only classroom teachers can do this")
    return access


QuizMemberAccess = Annotated[QuizAccess, Depends(get_quiz_access)]
QuizTeacherAccess = Annotated[QuizAccess, Depends(require_quiz_teacher)]