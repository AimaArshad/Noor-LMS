"""Announcement endpoints, mounted at /classrooms/{classroom_id}/announcements.

POST   /                   post (classroom teacher)
GET    /                   list, newest first (member)
GET    /{announcement_id}  read one (member)
PATCH  /{announcement_id}  edit (classroom teacher)
DELETE /{announcement_id}  delete (classroom teacher)
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.classroom_deps import ClassroomMemberAccess, ClassroomTeacherAccess
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.announcements import AnnouncementCreate, AnnouncementRead, AnnouncementUpdate
from app.schemas.common import Message, Page
from app.services.announcement_service import AnnouncementService

router = APIRouter()


def get_announcement_service(db: Annotated[AsyncSession, Depends(get_db)]) -> AnnouncementService:
    """Build the per-request service (shares the request's DB session)."""
    return AnnouncementService(db)


Service = Annotated[AnnouncementService, Depends(get_announcement_service)]

_NOT_FOUND = {404: {"model": Message, "description": "Classroom/announcement not found, or not a member"}}
_FORBIDDEN = {403: {"model": Message, "description": "Not a teacher, or classroom is archived"}}


@router.post(
    "",
    response_model=AnnouncementRead,
    status_code=status.HTTP_201_CREATED,
    summary="Post an announcement (classroom teachers)",
    responses={**_NOT_FOUND, **_FORBIDDEN},
)
@limiter.limit("30/minute")
async def create_announcement(
    request: Request,
    body: AnnouncementCreate,
    access: ClassroomTeacherAccess,
    service: Service,
) -> AnnouncementRead:
    announcement = await service.create(access.classroom, access.user, body)
    return AnnouncementRead.model_validate(announcement)


@router.get(
    "",
    response_model=Page[AnnouncementRead],
    summary="List announcements (newest first)",
    responses={**_NOT_FOUND},
)
async def list_announcements(
    access: ClassroomMemberAccess,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AnnouncementRead]:
    return await service.list_for_classroom(access.classroom.id, limit=limit, offset=offset)


@router.get(
    "/{announcement_id}",
    response_model=AnnouncementRead,
    summary="Get one announcement",
    responses={**_NOT_FOUND},
)
async def get_announcement(
    announcement_id: uuid.UUID, access: ClassroomMemberAccess, service: Service
) -> AnnouncementRead:
    announcement = await service.get(access.classroom.id, announcement_id)
    return AnnouncementRead.model_validate(announcement)


@router.patch(
    "/{announcement_id}",
    response_model=AnnouncementRead,
    summary="Edit an announcement (classroom teachers)",
    responses={**_NOT_FOUND, **_FORBIDDEN},
)
async def update_announcement(
    announcement_id: uuid.UUID,
    body: AnnouncementUpdate,
    access: ClassroomTeacherAccess,
    service: Service,
) -> AnnouncementRead:
    announcement = await service.get(access.classroom.id, announcement_id)
    updated = await service.update(access.classroom, announcement, body)
    return AnnouncementRead.model_validate(updated)


@router.delete(
    "/{announcement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an announcement and its comments (classroom teachers)",
    responses={**_NOT_FOUND, **_FORBIDDEN},
)
async def delete_announcement(
    announcement_id: uuid.UUID, access: ClassroomTeacherAccess, service: Service
) -> Response:
    announcement = await service.get(access.classroom.id, announcement_id)
    await service.delete(access.classroom, announcement)
    return Response(status_code=status.HTTP_204_NO_CONTENT)