"""Reusable classroom access dependencies.

Use them in any router whose path contains ``{classroom_id}``::

    @router.post("/{classroom_id}/announcements")
    async def create(access: ClassroomTeacherAccess, ...): ...

* :data:`ClassroomMemberAccess`  - any member (students and teachers), or an admin
* :data:`ClassroomTeacherAccess` - teacher members, or an admin
* :data:`ClassroomOwnerAccess`   - the owner, or an admin

Routes that only know a child id (assignment, submission, ...) call
:func:`resolve_classroom_access` directly (see ``assignment_deps.py``).

Non-members receive ``404`` (not ``403``) so classroom ids cannot be enumerated.
All dependencies share the request's DB session, so ``access.classroom`` and
``access.member`` can be modified/deleted by a service using the same session.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.db.session import get_db
from app.models import Classroom, ClassroomMember, MemberRole, User, UserRole


@dataclass(frozen=True, slots=True)
class ClassroomAccess:
    """The caller's relationship to one classroom."""

    classroom: Classroom
    user: User
    member: ClassroomMember | None  # None only for admins who are not members
    role: MemberRole  # effective role (admins count as teachers)

    @property
    def is_admin(self) -> bool:
        return self.user.role == UserRole.ADMIN

    @property
    def is_teacher(self) -> bool:
        return self.role == MemberRole.TEACHER

    @property
    def is_owner(self) -> bool:
        return self.classroom.owner_id == self.user.id


async def resolve_classroom_access(
    db: AsyncSession, classroom_id: uuid.UUID, user: User
) -> ClassroomAccess:
    """Load the classroom and the caller's membership with a single query.

    Raises:
        HTTPException: 404 if the classroom does not exist or the caller is not a member
            (admins are exempt from the membership requirement).
    """
    stmt = (
        select(Classroom, ClassroomMember)
        .outerjoin(
            ClassroomMember,
            and_(
                ClassroomMember.classroom_id == Classroom.id,
                ClassroomMember.user_id == user.id,
            ),
        )
        .where(Classroom.id == classroom_id)
    )
    row = (await db.execute(stmt)).first()
    not_found = HTTPException(status.HTTP_404_NOT_FOUND, "Classroom not found")
    if row is None:
        raise not_found

    classroom, member = row
    if member is None:
        if user.role != UserRole.ADMIN:
            raise not_found
        role = MemberRole.TEACHER
    else:
        role = member.role
    return ClassroomAccess(classroom=classroom, user=user, member=member, role=role)


async def get_classroom_access(
    classroom_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ClassroomAccess:
    """Dependency form of :func:`resolve_classroom_access` (path param ``classroom_id``)."""
    return await resolve_classroom_access(db, classroom_id, user)


async def require_classroom_member(
    access: Annotated[ClassroomAccess, Depends(get_classroom_access)],
) -> ClassroomAccess:
    """Any member of the classroom (or an admin)."""
    return access


async def require_classroom_teacher(
    access: Annotated[ClassroomAccess, Depends(get_classroom_access)],
) -> ClassroomAccess:
    """A teacher of the classroom (or an admin). Students get 403."""
    if not access.is_teacher:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only classroom teachers can do this")
    return access


async def require_classroom_owner(
    access: Annotated[ClassroomAccess, Depends(get_classroom_access)],
) -> ClassroomAccess:
    """The classroom owner (or an admin). Everyone else gets 403."""
    if not (access.is_owner or access.is_admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the classroom owner can do this")
    return access


ClassroomMemberAccess = Annotated[ClassroomAccess, Depends(require_classroom_member)]
ClassroomTeacherAccess = Annotated[ClassroomAccess, Depends(require_classroom_teacher)]
ClassroomOwnerAccess = Annotated[ClassroomAccess, Depends(require_classroom_owner)]