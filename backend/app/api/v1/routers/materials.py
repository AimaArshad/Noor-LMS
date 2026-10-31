"""Material endpoints, mounted at /classrooms/{classroom_id}/materials.

POST   /                 post (classroom teacher)
GET    /                 list, newest first (member)
GET    /{material_id}    read one (member)
PATCH  /{material_id}    edit (classroom teacher)
DELETE /{material_id}    delete (classroom teacher)
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.classroom_deps import ClassroomMemberAccess, ClassroomTeacherAccess
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.common import Message, Page
from app.schemas.materials import MaterialCreate, MaterialRead, MaterialUpdate
from app.services.file_service import FileService
from app.services.material_service import MaterialService
from app.services.storage import get_storage

router = APIRouter()


def get_material_service(db: Annotated[AsyncSession, Depends(get_db)]) -> MaterialService:
    """Build the per-request service (shares the request's DB session)."""
    return MaterialService(db, FileService(db, get_storage("local")))


Service = Annotated[MaterialService, Depends(get_material_service)]

_NOT_FOUND = {404: {"model": Message, "description": "Classroom/material not found, or not a member"}}
_FORBIDDEN = {403: {"model": Message, "description": "Not a teacher, or classroom is archived"}}


@router.post(
    "",
    response_model=MaterialRead,
    status_code=status.HTTP_201_CREATED,
    summary="Post a material (classroom teachers)",
    responses={
        **_NOT_FOUND,
        **_FORBIDDEN,
        422: {"model": Message, "description": "Unknown attachment, or one you did not upload"},
    },
)
@limiter.limit("30/minute")
async def create_material(
    request: Request,
    body: MaterialCreate,
    access: ClassroomTeacherAccess,
    service: Service,
) -> MaterialRead:
    """Every student of the classroom gets a ``material_posted`` notification."""
    material = await service.create(access.classroom, access.user, body)
    return MaterialRead.model_validate(material)


@router.get(
    "",
    response_model=Page[MaterialRead],
    summary="List materials (newest first)",
    responses={**_NOT_FOUND},
)
async def list_materials(
    access: ClassroomMemberAccess,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[MaterialRead]:
    return await service.list_for_classroom(access.classroom.id, limit=limit, offset=offset)


@router.get(
    "/{material_id}",
    response_model=MaterialRead,
    summary="Get one material",
    responses={**_NOT_FOUND},
)
async def get_material(
    material_id: uuid.UUID, access: ClassroomMemberAccess, service: Service
) -> MaterialRead:
    material = await service.get(access.classroom.id, material_id)
    return MaterialRead.model_validate(material)


@router.patch(
    "/{material_id}",
    response_model=MaterialRead,
    summary="Edit a material (classroom teachers)",
    responses={**_NOT_FOUND, **_FORBIDDEN},
)
async def update_material(
    material_id: uuid.UUID,
    body: MaterialUpdate,
    access: ClassroomTeacherAccess,
    service: Service,
) -> MaterialRead:
    material = await service.get(access.classroom.id, material_id)
    updated = await service.update(access.classroom, access.user, material, body)
    return MaterialRead.model_validate(updated)


@router.delete(
    "/{material_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a material (classroom teachers)",
    responses={**_NOT_FOUND, **_FORBIDDEN},
)
async def delete_material(
    material_id: uuid.UUID, access: ClassroomTeacherAccess, service: Service
) -> Response:
    material = await service.get(access.classroom.id, material_id)
    await service.delete(access.classroom, material)
    return Response(status_code=status.HTTP_204_NO_CONTENT)