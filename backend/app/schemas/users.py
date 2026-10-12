"""User schemas."""

import uuid
from datetime import datetime

from pydantic import Field

from app.models.enums import UserRole
from app.schemas.common import (
    LowerEmail,
    ORMModel,
    OptUrlOrPath,
    Password,
    RequestModel,
    Str255,
    UpdateModel,
)


class UserCreate(RequestModel):
    """Create a user (used by admins / seeding; self-signup uses ``RegisterRequest``)."""

    email: LowerEmail
    password: Password
    full_name: Str255
    role: UserRole = UserRole.STUDENT


class UserUpdate(UpdateModel):
    """Self-service profile update (``PATCH /users/me``). Role cannot be changed here."""

    non_nullable = frozenset({"full_name"})

    full_name: Str255 | None = None
    avatar_url: OptUrlOrPath = None


class UserRead(ORMModel):
    """Full profile. Only returned to the user themselves (or admins)."""

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    avatar_url: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class UserPublic(ORMModel):
    """Minimal profile safe to show to classmates (no email)."""

    id: uuid.UUID
    full_name: str
    avatar_url: str | None = None
    role: UserRole = Field(description="Global platform role")