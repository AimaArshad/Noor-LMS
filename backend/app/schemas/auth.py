"""Authentication schemas."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.enums import UserRole
from app.schemas.common import LowerEmail, Password, RequestModel, Str255


class RegisterRequest(RequestModel):
    """Self-registration. Admin accounts can never be created this way."""

    email: LowerEmail
    password: Password
    full_name: Str255
    role: UserRole = UserRole.STUDENT

    @field_validator("role")
    @classmethod
    def _no_admin_signup(cls, value: UserRole) -> UserRole:
        if value == UserRole.ADMIN:
            raise ValueError("Cannot self-register as admin")
        return value


class LoginRequest(RequestModel):
    """Credentials. The password is not complexity-checked on login."""

    email: LowerEmail
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(RequestModel):
    """Body of ``POST /auth/refresh``."""

    refresh_token: str = Field(min_length=10, max_length=2048)


class LogoutRequest(RequestModel):
    """Body of ``POST /auth/logout`` (revokes the given refresh token)."""

    refresh_token: str = Field(min_length=10, max_length=2048)


class TokenPair(BaseModel):
    """Access + refresh token response."""

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds", ge=1)


class TokenPayload(BaseModel):
    """Decoded JWT claims (internal use by the security layer)."""

    sub: str
    type: Literal["access", "refresh"]
    exp: int
    iat: int | None = None
    jti: str | None = None