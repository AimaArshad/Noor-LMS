"""Comment schemas.

Comments are generic: ``POST /comments`` names its target (assignment or
announcement) in the body, and ``GET /comments`` takes it as query parameters.
"""

import uuid
from datetime import datetime

from app.models.enums import CommentTarget
from app.schemas.common import Body5k, ORMModel, RequestModel, UpdateModel
from app.schemas.users import UserPublic


class CommentCreate(RequestModel):
    """Body of ``POST /comments``."""

    target_type: CommentTarget
    target_id: uuid.UUID
    body: Body5k


class CommentUpdate(UpdateModel):
    """Reserved for a future ``PATCH /comments/{id}`` (not exposed yet)."""

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