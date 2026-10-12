"""To-do item schemas."""

import uuid
from datetime import datetime

from pydantic import AwareDatetime, model_validator

from app.models.enums import TodoRefType
from app.schemas.common import ORMModel, RequestModel, Str255, UpdateModel


class TodoCreate(RequestModel):
    """Create a personal item (no ref) or a derived item (ref_type + ref_id together)."""

    title: Str255
    due_at: AwareDatetime | None = None
    ref_type: TodoRefType | None = None
    ref_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _ref_pair(self) -> "TodoCreate":
        if (self.ref_type is None) != (self.ref_id is None):
            raise ValueError("'ref_type' and 'ref_id' must be provided together")
        return self


class TodoUpdate(UpdateModel):
    """Body of ``PATCH /todo/{id}`` (typically ``{"is_done": true}``)."""

    non_nullable = frozenset({"title", "is_done"})

    is_done: bool | None = None
    title: Str255 | None = None
    due_at: AwareDatetime | None = None


class TodoRead(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    due_at: datetime | None = None
    ref_type: TodoRefType | None = None
    ref_id: uuid.UUID | None = None
    is_done: bool
    created_at: datetime