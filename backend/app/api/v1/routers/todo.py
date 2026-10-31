"""To-do endpoints.

GET   /todo           explicit items + derived pending assignments/quizzes
PATCH /todo/{id}      {"is_done": true|false}
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.db.session import get_db
from app.schemas.common import Message
from app.schemas.todo import TodoList, TodoMark, TodoRead
from app.services.todo_service import TodoService

router = APIRouter()


def get_todo_service(db: Annotated[AsyncSession, Depends(get_db)]) -> TodoService:
    """Build the per-request service (shares the request's DB session)."""
    return TodoService(db)


Service = Annotated[TodoService, Depends(get_todo_service)]


@router.get(
    "",
    response_model=TodoList,
    summary="My to-do list",
)
async def list_todo(
    user: CurrentUser,
    service: Service,
    is_done: Annotated[
        bool | None, Query(description="false = still to do, true = done, omitted = all")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TodoList:
    """Open items first, soonest due first. Published assignments/quizzes of your classrooms
    that are missing from your list are added automatically. Work you already turned in
    shows as done. ``pending_count`` / ``overdue_count`` cover all your items."""
    return await service.list_for_user(user.id, is_done=is_done, limit=limit, offset=offset)


@router.patch(
    "/{todo_id}",
    response_model=TodoRead,
    summary="Mark a to-do item done / not done",
    responses={404: {"model": Message, "description": "Not your item, or it no longer applies"}},
)
async def update_todo(
    todo_id: uuid.UUID, body: TodoMark, user: CurrentUser, service: Service
) -> TodoRead:
    """Work that is already turned in always stays done, whatever you send."""
    return await service.mark(user.id, todo_id, body.is_done)