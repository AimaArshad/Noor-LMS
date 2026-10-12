"""Shared building blocks for every Pydantic schema module.

Conventions
-----------
* ``*Create`` / ``*Update`` / request bodies inherit :class:`RequestModel`
  (``extra="forbid"``): unknown fields return 422, which blocks mass-assignment
  attempts such as sending ``"role": "admin"``.
* ``*Update`` bodies inherit :class:`UpdateModel` (PATCH semantics). Services must
  apply them with ``body.model_dump(exclude_unset=True)``.
* ``*Read`` / response models inherit :class:`ORMModel` (``from_attributes=True``).
  Relationship fields in Read schemas (``author``, ``student``, ``user`` ...) must
  be eager-loaded by the service (``selectinload`` / ``joinedload``). Implicit lazy
  loading does not work under ``AsyncSession``.
* ``Decimal`` values are serialized to JSON as numbers (not strings).
* Datetimes accepted from clients must be timezone-aware (``AwareDatetime``).
"""

import uuid
from decimal import Decimal
from typing import Annotated, Any, ClassVar, Generic, TypeVar

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    PlainSerializer,
    StringConstraints,
    model_validator,
)

# --------------------------------------------------------------------------- #
# Base classes
# --------------------------------------------------------------------------- #


class ORMModel(BaseModel):
    """Base for response schemas built from SQLAlchemy objects."""

    model_config = ConfigDict(from_attributes=True)


class RequestModel(BaseModel):
    """Base for request bodies. Unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")


class UpdateModel(RequestModel):
    """Base for PATCH bodies.

    * At least one field must be sent.
    * Fields listed in ``non_nullable`` may be omitted but not set to ``null``
      (their database columns are NOT NULL).
    """

    non_nullable: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _validate_patch(self) -> "UpdateModel":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for name in self.model_fields_set & self.non_nullable:
            if getattr(self, name) is None:
                raise ValueError(f"'{name}' cannot be null")
        return self


# --------------------------------------------------------------------------- #
# String types
# --------------------------------------------------------------------------- #


def blank_to_none(value: Any) -> Any:
    """Strip strings and turn blank ones into ``None`` (for optional text fields)."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _str(max_length: int) -> Any:  # pragma: no cover - helper for aliases below
    return Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)
    ]


# Required, trimmed, non-empty strings.
Str100 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Str200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Str255 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Str1000 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
Body5k = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5_000)]
Body10k = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)]
Body20k = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000)]

# Optional strings: blank input ("" or "   ") becomes None.
OptStr100 = Annotated[Str100 | None, BeforeValidator(blank_to_none)]
OptBody5k = Annotated[Body5k | None, BeforeValidator(blank_to_none)]
OptBody10k = Annotated[Body10k | None, BeforeValidator(blank_to_none)]
OptBody20k = Annotated[Body20k | None, BeforeValidator(blank_to_none)]


def _check_url_or_path(value: str | None) -> str | None:
    """Allow ``http(s)://`` URLs or app-relative paths (``/api/v1/files/...``)."""
    if value is None:
        return value
    if len(value) > 1024:
        raise ValueError("Must be at most 1024 characters")
    if value.startswith("//") or not value.startswith(("http://", "https://", "/")):
        raise ValueError("Must be an http(s) URL or an absolute path starting with '/'")
    return value


OptUrlOrPath = Annotated[
    str | None, BeforeValidator(blank_to_none), AfterValidator(_check_url_or_path)
]


# --------------------------------------------------------------------------- #
# Email / password
# --------------------------------------------------------------------------- #


def _normalise_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 320:
        raise ValueError("Email must be at most 320 characters")
    return value


LowerEmail = Annotated[EmailStr, AfterValidator(_normalise_email)]


def _validate_password(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 bytes (bcrypt limit)")
    if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
        raise ValueError("Password must contain at least one letter and one digit")
    return value


# Passwords are never stripped: leading/trailing spaces are legitimate characters.
Password = Annotated[
    str, StringConstraints(min_length=8, max_length=72), AfterValidator(_validate_password)
]


# --------------------------------------------------------------------------- #
# Numbers (JSON output as float, not string)
# --------------------------------------------------------------------------- #


def _decimal_to_float(value: Decimal) -> float:
    return float(value)


_as_number = PlainSerializer(_decimal_to_float, return_type=float, when_used="json")

#: Any numeric value read from the DB (grades, scores, points).
Score = Annotated[Decimal, _as_number]
#: Positive points for questions (max 9999.99, 2 decimals).
Points = Annotated[Decimal, Field(gt=0, le=Decimal("9999.99"), decimal_places=2), _as_number]
#: A grade given by a teacher (>= 0, 2 decimals).
Grade = Annotated[Decimal, Field(ge=0, le=Decimal("99999.99"), decimal_places=2), _as_number]


# --------------------------------------------------------------------------- #
# Attachments (stored as JSONB lists on assignments/submissions/materials)
# --------------------------------------------------------------------------- #


class AttachmentRef(ORMModel):
    """Reference to an uploaded file (see ``POST /files/upload``)."""

    file_id: uuid.UUID
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]
    mime_type: str | None = Field(default=None, max_length=255)


def _unique_attachments(items: list[AttachmentRef]) -> list[AttachmentRef]:
    ids = [item.file_id for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate attachments are not allowed")
    return items


#: Request-side attachment list: max 20, no duplicates.
AttachmentList = Annotated[
    list[AttachmentRef], Field(max_length=20), AfterValidator(_unique_attachments)
]


def dump_attachments(items: list[AttachmentRef]) -> list[dict[str, Any]]:
    """Convert attachments to JSON-safe dicts for the JSONB column (UUID -> str)."""
    return [item.model_dump(mode="json") for item in items]


# --------------------------------------------------------------------------- #
# Generic responses
# --------------------------------------------------------------------------- #

T = TypeVar("T")


class Message(BaseModel):
    """Simple ``{"detail": "..."}`` response."""

    detail: str


class Page(BaseModel, Generic[T]):
    """Offset-paginated list response."""

    items: list[T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)