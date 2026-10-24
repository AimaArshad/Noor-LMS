"""Reusable FastAPI dependencies: authentication and role-based access control."""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenError, decode_token, parse_subject
from app.db.session import get_db
from app.models import User, UserRole

# auto_error=False so a missing header gives 401 (older FastAPI versions return 403).
bearer_scheme = HTTPBearer(auto_error=False, description="Paste the access token (no 'Bearer ' prefix).")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the authenticated user from the ``Authorization: Bearer`` access token.

    Raises:
        HTTPException: 401 when the token is missing/invalid/expired or the user is
            unknown or deactivated.
    """
    if credentials is None:
        raise _unauthorized("Not authenticated")
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user_id = parse_subject(payload)
    except TokenError as exc:
        raise _unauthorized(exc.message) from exc

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("User not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole) -> Callable[..., Awaitable[User]]:
    """Dependency factory restricting an endpoint to the given global roles.

    Admins are NOT implicitly allowed; include ``UserRole.ADMIN`` explicitly::

        @router.post("/x", dependencies=[Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))])
        async def create_x(user: User = Depends(require_role(UserRole.TEACHER))): ...
    """
    if not roles:
        raise ValueError("require_role() needs at least one role")
    allowed = frozenset(roles)

    async def _checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return user

    return _checker