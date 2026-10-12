"""Comment schemas.

The target (assignment/announcement) comes from the URL path, so create/update
bodies only contain the text.
"""

import uuid
from datetime import datetime

from app.models.enums import CommentTarget
from app.schemas.common import Body5k, ORMModel, RequestModel, UpdateModel
from app.schemas.users import UserPublic


class CommentCreate(RequestModel):
    body: Body5k


class CommentUpdate(UpdateModel):
    non_nullable = frozenset({"body"})

    body: Body5k | None = None


class CommentRead(ORMModel):
    """``author`` requires ``Comment.author`` to be eager-loaded (or leave it None)."""

    id: uuid.UUID
    author_id: uuid.UUID | None = None
    author: UserPublic | None = None
    target_type: CommentTarget
    target_id: uuid.UUID
    body: str
    created_at: datetime