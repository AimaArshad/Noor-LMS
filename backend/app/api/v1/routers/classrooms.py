"""Classroom endpoints.

POST   /classrooms               create (teacher/admin)
GET    /classrooms               list my classrooms
POST   /classrooms/join          join by code
GET    /classrooms/{id}          details (member)
PATCH  /classrooms/{id}          update (classroom teacher)
DELETE /classrooms/{id}          delete (owner)
POST   /classrooms/{id}/leave    leave (member, not owner)
GET    /classrooms/{id}/people   teachers and students (member)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.classroom_deps import (
    ClassroomMemberAccess,
    ClassroomOwnerAccess,
    ClassroomTeacherAccess,
)
from app.core.deps import require_role
from app.core.pagination import PageParams, PeoplePageParams
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.classrooms import (
    ClassroomCreate,
    ClassroomDetail,
    ClassroomJoin,
    ClassroomPeople,
    ClassroomUpdate,
)
from app.schemas.common import Message
from app.services.classroom_service import ClassroomService

router = APIRouter()


def get_classroom_service(db: Annotated[AsyncSession, Depends(get_db)]) -> ClassroomService:
    """Build the per-request service (shares the request's DB session)."""
    return ClassroomService(db)


Service = Annotated[ClassroomService, Depends(get_classroom_service)]
TeacherUser = Annotated[User, Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))]
# Uses the same dependency as ``TeacherUser``'s siblings, so `get_current_user` runs once.
from app.core.deps import CurrentUser  # noqa: E402

_NOT_FOUND = {404: {"model": Message, "description": "Classroom not found / not a member"}}
_FORBIDDEN = {403: {"model": Message}}


@router.post(
    "",
    response_model=ClassroomDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a classroom (teachers only)",
    responses={**_FORBIDDEN},
)
async def create_classroom(
    body: ClassroomCreate, user: TeacherUser, service: Service
) -> ClassroomDetail:
    """Creates the classroom with a random join code and adds you as its teacher."""
    classroom = await service.create(user, body)
    return service.build_detail(classroom, role=_teacher_role())


@router.get(
    "",
    response_model=list[ClassroomDetail],
    summary="List my classrooms",
    responses={
        200: {
            "headers": {
                "X-Total-Count": {
                    "description": "Total classrooms matching the filter (ignores limit/offset).",
                    "schema": {"type": "integer"},
                }
            }
        }
    },
)
async def list_classrooms(
    response: Response,
    user: CurrentUser,
    service: Service,
    page: PageParams,
    include_archived: Annotated[bool, Query(description="Also return archived classrooms")] = False,
) -> list[ClassroomDetail]:
    """Classrooms you teach or attend, newest first. Join codes are shown only where you teach."""
    rows = await service.list_for_user(
        user, include_archived=include_archived, limit=page.limit, offset=page.offset
    )
    response.headers["X-Total-Count"] = str(
        await service.count_for_user(user, include_archived=include_archived)
    )
    return [service.build_detail(classroom, role) for classroom, role in rows]


# NOTE: declared before "/{classroom_id}" routes for readability.
@router.post(
    "/join",
    response_model=ClassroomDetail,
    summary="Join a classroom with its join code",
    responses={
        403: {"model": Message, "description": "Classroom is archived"},
        404: {"model": Message, "description": "Invalid join code"},
        409: {"model": Message, "description": "Already a member"},
    },
)
@limiter.limit("10/minute")
async def join_classroom(
    request: Request, body: ClassroomJoin, user: CurrentUser, service: Service
) -> ClassroomDetail:
    """Joins you as a **student**. Body: ``{"join_code": "AB3K7QX"}`` (case-insensitive)."""
    classroom = await service.join(user, body.code)
    return service.build_detail(classroom, role=_student_role())


@router.get(
    "/{classroom_id}",
    response_model=ClassroomDetail,
    summary="Get a classroom",
    responses={**_NOT_FOUND},
)
async def get_classroom(access: ClassroomMemberAccess, service: Service) -> ClassroomDetail:
    return service.build_detail(access.classroom, access.role)


@router.patch(
    "/{classroom_id}",
    response_model=ClassroomDetail,
    summary="Update a classroom (classroom teachers)",
    responses={**_NOT_FOUND, **_FORBIDDEN},
)
async def update_classroom(
    body: ClassroomUpdate, access: ClassroomTeacherAccess, service: Service
) -> ClassroomDetail:
    classroom = await service.update(access.classroom, body)
    return service.build_detail(classroom, access.role)


@router.delete(
    "/{classroom_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a classroom (owner only)",
    responses={**_NOT_FOUND, **_FORBIDDEN},
)
async def delete_classroom(access: ClassroomOwnerAccess, service: Service) -> Response:
    """Permanently deletes the classroom and all its members, posts, work and quizzes."""
    await service.delete(access.classroom)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{classroom_id}/leave",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Leave a classroom",
    responses={
        404: {"model": Message},
        409: {"model": Message, "description": "The owner cannot leave"},
    },
)
async def leave_classroom(access: ClassroomMemberAccess, service: Service) -> Response:
    await service.leave(access.classroom, access.user, access.member)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{classroom_id}/people",
    response_model=ClassroomPeople,
    summary="List teachers and students",
    responses={**_NOT_FOUND},
)
async def list_people(
    access: ClassroomMemberAccess, service: Service, page: PeoplePageParams
) -> ClassroomPeople:
    """All teachers, plus one page of students (``students_total`` tells you how many exist)."""
    return await service.list_people(access.classroom, limit=page.limit, offset=page.offset)


# --- tiny helpers (kept at the bottom to keep the endpoint list readable) ---
def _teacher_role():  # noqa: ANN202
    from app.models import MemberRole

    return MemberRole.TEACHER


def _student_role():  # noqa: ANN202
    from app.models import MemberRole

    return MemberRole.STUDENT