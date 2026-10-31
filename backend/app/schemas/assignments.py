"""Assignment and submission schemas."""

import uuid
from datetime import datetime

from pydantic import AwareDatetime, Field, model_validator

from app.models.enums import AssignmentState, SubmissionState
from app.schemas.common import (
    AttachmentList,
    AttachmentRef,
    Grade,
    ORMModel,
    OptBody5k,
    OptBody10k,
    OptBody20k,
    Page,
    RequestModel,
    Score,
    Str255,
    UpdateModel,
)
from app.schemas.users import UserPublic


# ----------------------------------------------------------------- assignments
class AssignmentCreate(RequestModel):
    title: Str255
    description: OptBody10k = None
    due_at: AwareDatetime | None = None
    max_points: int = Field(default=100, gt=0, le=100_000)
    attachments: AttachmentList = Field(default_factory=list)
    state: AssignmentState = AssignmentState.DRAFT


class AssignmentUpdate(UpdateModel):
    non_nullable = frozenset({"title", "max_points", "attachments", "state"})

    title: Str255 | None = None
    description: OptBody10k = None
    due_at: AwareDatetime | None = None
    max_points: int | None = Field(default=None, gt=0, le=100_000)
    attachments: AttachmentList | None = None
    state: AssignmentState | None = None


class AssignmentRead(ORMModel):
    id: uuid.UUID
    classroom_id: uuid.UUID
    title: str
    description: str | None = None
    due_at: datetime | None = None
    max_points: int
    attachments: list[AttachmentRef] = Field(default_factory=list)
    state: AssignmentState
    created_at: datetime
    updated_at: datetime


# ----------------------------------------------------------------- submissions
class SubmissionCreate(RequestModel):
    """Body of ``POST /assignments/{id}/submit``: text, files, or both."""

    content: OptBody20k = None
    attachments: AttachmentList = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_some_work(self) -> "SubmissionCreate":
        if not self.content and not self.attachments:
            raise ValueError("Provide 'content' and/or at least one attachment")
        return self


class SubmissionRead(ORMModel):
    """``student`` requires ``Submission.student`` to be eager-loaded (or leave it None)."""

    id: uuid.UUID
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    student: UserPublic | None = None
    content: str | None = None
    attachments: list[AttachmentRef] = Field(default_factory=list)
    state: SubmissionState
    grade: Score | None = None
    feedback: str | None = None
    submitted_at: datetime | None = None
    graded_at: datetime | None = None
    graded_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class SubmissionList(Page[SubmissionRead]):
    """Teacher view of an assignment's submissions.

    ``not_submitted_count`` = current students who have no submission yet.
    """

    not_submitted_count: int = Field(default=0, ge=0)


class GradeSubmission(RequestModel):
    """Body of ``PATCH /submissions/{id}/grade``.

    The service also verifies ``grade <= assignment.max_points``. Omit ``feedback``
    to keep the existing feedback; send ``null``/blank to clear it.
    """

    grade: Grade
    feedback: OptBody5k = None


class ReturnSubmission(RequestModel):
    """Optional body of ``PATCH /submissions/{id}/return``."""

    feedback: OptBody5k = None


