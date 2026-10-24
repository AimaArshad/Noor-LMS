"""Authentication business logic: register, login, refresh (rotation), logout."""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import HTTPException, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    dummy_hash,
    hash_password,
    needs_rehash,
    parse_subject,
    verify_password,
)
from app.models import User
from app.schemas.auth import RegisterRequest, TokenPair
from app.services.token_blacklist import revoke_token

logger = logging.getLogger("educonnect.auth")


def _invalid_credentials() -> HTTPException:
    # Same message for "unknown e-mail" and "wrong password": no account enumeration.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _invalid_refresh(detail: str = "Invalid refresh token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _redis_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication service temporarily unavailable",
    )


class AuthService:
    """Stateless service; create one per request."""

    def __init__(self, db: AsyncSession, redis: Redis) -> None:
        self.db = db
        self.redis = redis

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    async def _get_by_email(self, email: str) -> User | None:
        return await self.db.scalar(select(User).where(User.email == email))

    # ------------------------------------------------------------------ #
    # Register
    # ------------------------------------------------------------------ #
    async def register(self, data: RegisterRequest) -> User:
        """Create a teacher or student account.

        Raises:
            HTTPException: 409 if the e-mail is already registered.
        """
        conflict = HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
        if await self._get_by_email(data.email):
            raise conflict

        user = User(
            email=data.email,
            hashed_password=await asyncio.to_thread(hash_password, data.password),
            full_name=data.full_name,
            role=data.role,  # schema already rejects "admin"
        )
        self.db.add(user)
        try:
            await self.db.commit()
        except IntegrityError as exc:  # concurrent registration with the same e-mail
            await self.db.rollback()
            raise conflict from exc
        await self.db.refresh(user)  # load server-generated created_at / updated_at
        return user

    # ------------------------------------------------------------------ #
    # Login
    # ------------------------------------------------------------------ #
    async def authenticate(self, email: str, password: str) -> User:
        """Validate credentials and return the user.

        Raises:
            HTTPException: 401 for bad credentials, 403 for a deactivated account.
        """
        user = await self._get_by_email(email)
        if user is None:
            await asyncio.to_thread(verify_password, password, dummy_hash())  # equalise timing
            raise _invalid_credentials()

        if not await asyncio.to_thread(verify_password, password, user.hashed_password):
            raise _invalid_credentials()

        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")

        if needs_rehash(user.hashed_password):  # transparently upgrade old hashes
            user.hashed_password = await asyncio.to_thread(hash_password, password)
            await self.db.commit()
        return user

    @staticmethod
    def issue_tokens(user: User) -> TokenPair:
        """Create a fresh access + refresh pair for ``user``."""
        return TokenPair(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def login(self, email: str, password: str) -> TokenPair:
        """Authenticate and return a token pair."""
        user = await self.authenticate(email, password)
        return self.issue_tokens(user)

    # ------------------------------------------------------------------ #
    # Refresh (rotation + reuse detection)
    # ------------------------------------------------------------------ #
    async def refresh(self, refresh_token: str) -> TokenPair:
        """Exchange a valid refresh token for a new pair; the old one is revoked.

        Raises:
            HTTPException: 401 for invalid/expired/reused tokens, 503 if Redis is down.
        """
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
            user_id = parse_subject(payload)
        except TokenError as exc:
            raise _invalid_refresh(exc.message) from exc

        user = await self.db.get(User, user_id)
        if user is None or not user.is_active:
            raise _invalid_refresh("User not found or inactive")

        ttl = payload.exp - int(time.time())
        try:
            first_use = await revoke_token(self.redis, payload.jti or "", ttl)
        except RedisError as exc:
            logger.exception("Redis unavailable during token refresh")
            raise _redis_unavailable() from exc

        if not first_use:
            logger.warning("Refresh token reuse detected for user %s", user.id)
            raise _invalid_refresh("Refresh token has already been used or revoked")

        return self.issue_tokens(user)

    # ------------------------------------------------------------------ #
    # Logout
    # ------------------------------------------------------------------ #
    async def logout(self, refresh_token: str) -> None:
        """Revoke a refresh token. Idempotent: invalid/expired tokens are ignored.

        Raises:
            HTTPException: 503 if Redis is down (the token could not be revoked).
        """
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except TokenError:
            return  # nothing to revoke
        try:
            await revoke_token(self.redis, payload.jti or "", payload.exp - int(time.time()))
        except RedisError as exc:
            logger.exception("Redis unavailable during logout")
            raise _redis_unavailable() from exc