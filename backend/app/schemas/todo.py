"""To-do item schemas."""

import uuid
from datetime import datetime

from pydantic import AwareDatetime, Field, model_validator

from app.models.enums import TodoRefType
from app.schemas.common import ORMModel, Page, RequestModel, Str255, UpdateModel


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
    """Reserved for editing personal items (not exposed yet)."""

    non_nullable = frozenset({"title", "is_done"})

    is_done: bool | None = None
    title: Str255 | None = None
    due_at: AwareDatetime | None = None


class TodoMark(RequestModel):
    """Body of ``PATCH /todo/{id}``: ``{"is_done": true}``."""

    is_done: bool


class TodoRead(ORMModel):
    """One to-do entry.

    * ``is_done`` is true when the student marked it OR the work is already turned in.
    * Title and due date of assignment/quiz items always mirror the assignment/quiz.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    due_at: datetime | None = None
    ref_type: TodoRefType | None = None
    ref_id: uuid.UUID | None = None
    is_done: bool
    created_at: datetime
    classroom_id: uuid.UUID | None = None
    classroom_name: str | None = None
    link: str | None = Field(default=None, description="App route of the assignment/quiz")
    is_overdue: bool = False


class TodoList(Page[TodoRead]):
    """A page of to-do items plus counters computed over ALL of the user's items."""

    pending_count: int = Field(default=0, ge=0)
    overdue_count: int = Field(default=0, ge=0)
