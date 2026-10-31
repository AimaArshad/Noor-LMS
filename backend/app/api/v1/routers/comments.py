"""Generic comment endpoints for assignments and announcements.

POST   /comments                                  add a comment (classroom member)
GET    /comments?target_type=&target_id=          list a target's comments (classroom member)
DELETE /comments/{comment_id}                     author, or a classroom teacher
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models import CommentTarget
from app.schemas.comments import CommentCreate, CommentRead
from app.schemas.common import Message, Page
from app.services.comment_service import CommentService

router = APIRouter()


def get_comment_service(db: Annotated[AsyncSession, Depends(get_db)]) -> CommentService:
    """Build the per-request service (shares the request's DB session)."""
    return CommentService(db)


Service = Annotated[CommentService, Depends(get_comment_service)]


@router.post(
    "",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Comment on an assignment or announcement",
    responses={
        403: {"model": Message, "description": "Classroom is archived"},
        404: {"model": Message, "description": "Target not found or you are not a member"},
    },
)
@limiter.limit("30/minute")
async def create_comment(
    request: Request, body: CommentCreate, user: CurrentUser, service: Service
) -> CommentRead:
    """Students cannot comment on draft assignments (they get 404)."""
    comment = await service.create(user, body)
    return CommentRead.model_validate(comment)


@router.get(
    "",
    response_model=Page[CommentRead],
    summary="List the comments of one assignment or announcement (oldest first)",
    responses={404: {"model": Message, "description": "Target not found or you are not a member"}},
)
async def list_comments(
    user: CurrentUser,
    service: Service,
    target_type: Annotated[CommentTarget, Query(description="assignment | announcement")],
    target_id: Annotated[uuid.UUID, Query(description="Id of the assignment/announcement")],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[CommentRead]:
    return await service.list_for_target(
        user, target_type, target_id, limit=limit, offset=offset
    )


@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment (author or classroom teacher)",
    responses={
        403: {"model": Message, "description": "Not the author / not a teacher, or classroom archived"},
        404: {"model": Message},
    },
)
async def delete_comment(comment_id: uuid.UUID, user: CurrentUser, service: Service) -> Response:
    await service.delete(user, comment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)