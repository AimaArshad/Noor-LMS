"""Authentication endpoints: /auth/register, /login, /refresh, /logout, /me."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.core.rate_limit import limiter
from app.core.redis import get_redis
from app.db.session import get_db
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenPair
from app.schemas.common import Message
from app.schemas.users import UserRead
from app.services.auth_service import AuthService

router = APIRouter()


def get_auth_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> AuthService:
    """Build the per-request :class:`AuthService`."""
    return AuthService(db, redis)


Service = Annotated[AuthService, Depends(get_auth_service)]


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a teacher or student account",
    responses={409: {"model": Message, "description": "Email already registered"}},
)
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, service: Service) -> UserRead:
    """Self-registration. Only the ``teacher`` and ``student`` roles are allowed."""
    return await service.register(body)  # type: ignore[return-value]


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Log in and receive an access + refresh token",
    responses={
        401: {"model": Message, "description": "Incorrect email or password"},
        403: {"model": Message, "description": "Account is disabled"},
    },
)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, service: Service) -> TokenPair:
    return await service.login(body.email, body.password)


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Rotate tokens using a refresh token",
    responses={401: {"model": Message}, 503: {"model": Message}},
)
@limiter.limit("30/minute")
async def refresh(request: Request, body: RefreshRequest, service: Service) -> TokenPair:
    """The submitted refresh token is revoked and can never be used again."""
    return await service.refresh(body.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a refresh token",
    responses={503: {"model": Message}},
)
@limiter.limit("30/minute")
async def logout(request: Request, body: LogoutRequest, service: Service) -> Response:
    """The client must also discard its access token (valid until it expires)."""
    await service.logout(body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Current authenticated user",
    responses={401: {"model": Message}},
)
async def me(current_user: CurrentUser) -> UserRead:
    return current_user  # type: ignore[return-value]