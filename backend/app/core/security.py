"""Password hashing (bcrypt) and JWT creation/decoding."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Literal

from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.auth import TokenPayload

TokenType = Literal["access", "refresh"]

# 4 rounds is bcrypt's minimum: only used by the test suite to keep it fast.
_BCRYPT_ROUNDS = 4 if settings.ENVIRONMENT == "test" else 12
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=_BCRYPT_ROUNDS)

_BCRYPT_MAX_BYTES = 72


class TokenError(Exception):
    """Raised when a JWT is missing claims, expired, tampered with, or of the wrong type."""

    def __init__(self, message: str = "Invalid token") -> None:
        super().__init__(message)
        self.message = message


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def hash_password(plain: str) -> str:
    """Return the bcrypt hash of ``plain`` (CPU-bound: call via ``to_thread`` in async code)."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time password check. Never raises; returns ``False`` on any problem."""
    if len(plain.encode("utf-8")) > _BCRYPT_MAX_BYTES:
        return False
    try:
        return pwd_context.verify(plain, hashed)
    except ValueError:  # malformed hash
        return False


def needs_rehash(hashed: str) -> bool:
    """True when the stored hash uses outdated parameters and should be upgraded on login."""
    return pwd_context.needs_update(hashed)


@lru_cache
def dummy_hash() -> str:
    """A valid hash used to equalise timing when the e-mail does not exist."""
    return pwd_context.hash("not-a-real-password-0")


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def _create_token(subject: str | uuid.UUID, token_type: TokenType, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(subject),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
        "jti": uuid.uuid4().hex,  # unique id: lets us revoke individual refresh tokens
    }
    return jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str | uuid.UUID, expires_delta: timedelta | None = None) -> str:
    """Create a short-lived access token for ``subject`` (the user id)."""
    lifetime = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_token(subject, "access", lifetime)


def create_refresh_token(subject: str | uuid.UUID, expires_delta: timedelta | None = None) -> str:
    """Create a long-lived refresh token for ``subject`` (the user id)."""
    lifetime = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _create_token(subject, "refresh", lifetime)


def decode_token(token: str, expected_type: TokenType | None = None) -> TokenPayload:
    """Verify signature + expiry and return the claims.

    Args:
        token: Encoded JWT.
        expected_type: When given, the ``type`` claim must match (stops a refresh token
            being used as an access token and vice versa).

    Raises:
        TokenError: For any validation failure.
    """
    try:
        claims = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],  # fixed list: blocks alg=none / confusion
            options={
                "require_exp": True,
                "require_iat": True,
                "require_sub": True,
                "require_jti": True,
            },
        )
        payload = TokenPayload.model_validate(claims)
    except ExpiredSignatureError as exc:
        raise TokenError("Token has expired") from exc
    except (JWTError, ValidationError) as exc:
        raise TokenError("Invalid token") from exc

    if expected_type is not None and payload.type != expected_type:
        raise TokenError(f"Expected a {expected_type} token")
    return payload


def parse_subject(payload: TokenPayload) -> uuid.UUID:
    """Return the user id stored in ``sub``."""
    try:
        return uuid.UUID(payload.sub)
    except ValueError as exc:
        raise TokenError("Invalid token subject") from exc