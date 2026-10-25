"""Classroom and membership schemas."""

import re
import uuid
from datetime import datetime

from pydantic import AliasChoices, Field, field_validator

from app.models.enums import MemberRole
from app.schemas.common import (
    ORMModel,
    OptStr100,
    RequestModel,
    Str200,
    UpdateModel,
)
from app.schemas.users import UserPublic

_JOIN_CODE_RE = re.compile(r"^[A-Z0-9]{4,16}$")


class ClassroomCreate(RequestModel):
    name: Str200
    section: OptStr100 = None
    subject: OptStr100 = None
    room: OptStr100 = None


class ClassroomUpdate(UpdateModel):
    non_nullable = frozenset({"name", "is_archived"})

    name: Str200 | None = None
    section: OptStr100 = None
    subject: OptStr100 = None
    room: OptStr100 = None
    is_archived: bool | None = None


class ClassroomJoin(RequestModel):
    """Body of ``POST /classrooms/join``: ``{"join_code": "AB3K7QX"}``.

    The legacy key ``code`` is accepted too. The value is normalised to upper case.
    """

    code: str = Field(
        min_length=4,
        max_length=16,
        validation_alias=AliasChoices("join_code", "code"),
        description="The classroom join code (case-insensitive).",
    )

    @field_validator("code")
    @classmethod
    def _normalise_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not _JOIN_CODE_RE.fullmatch(value):
            raise ValueError("Join code must be 4-16 letters/digits")
        return value


class ClassroomRead(ORMModel):
    """Classroom without the join code (safe default for any ORM object)."""

    id: uuid.UUID
    name: str
    section: str | None = None
    subject: str | None = None
    room: str | None = None
    owner_id: uuid.UUID
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime


class ClassroomTeacherRead(ClassroomRead):
    """Classroom including the join code (kept for internal/teacher-only use)."""

    join_code: str


class ClassroomDetail(ClassroomRead):
    """API response for every classroom endpoint.

    * ``my_role``: the caller's role inside this classroom.
    * ``join_code``: only populated for classroom teachers, otherwise ``null``.

    Build it with ``ClassroomService.build_detail``. Do not validate it straight
    from an ORM object, or the join code would leak to students.
    """

    my_role: MemberRole
    join_code: str | None = Field(default=None, description="Visible to classroom teachers only")


class ClassroomMemberRead(ORMModel):
    """A member row. Requires ``ClassroomMember.user`` to be eager-loaded."""

    user: UserPublic
    role: MemberRole
    joined_at: datetime


class ClassroomPeople(ORMModel):
    """Response of ``GET /classrooms/{id}/people``."""

    teachers: list[ClassroomMemberRead] = Field(default_factory=list)
    students: list[ClassroomMemberRead] = Field(default_factory=list)