"""User profile and accessibility-settings endpoints.

GET  /users/me/accessibility   read own accessibility settings
PATCH /users/me/accessibility  update own accessibility settings (partial)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.db.session import get_db
from app.schemas.accessibility import AccessibilitySettingsRead, AccessibilitySettingsUpdate
from app.services.accessibility_service import AccessibilityService

router = APIRouter()


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> AccessibilityService:
    return AccessibilityService(db)


Service = Annotated[AccessibilityService, Depends(_get_service)]


@router.get(
    "/me/accessibility",
    response_model=AccessibilitySettingsRead,
    summary="Get own accessibility settings",
)
async def get_accessibility_settings(
    user: CurrentUser,
    service: Service,
) -> AccessibilitySettingsRead:
    """Return the authenticated user's accessibility preferences.

    If the user has never customised their settings, default values are
    returned (all features off, speed 1.0).  No row is written to the DB.
    """
    return await service.get_or_default(user.id)


@router.patch(
    "/me/accessibility",
    response_model=AccessibilitySettingsRead,
    summary="Update own accessibility settings (partial)",
)
async def update_accessibility_settings(
    body: AccessibilitySettingsUpdate,
    user: CurrentUser,
    service: Service,
) -> AccessibilitySettingsRead:
    """Partially update the authenticated user's accessibility preferences.

    At least one field must be supplied. Unknown fields are rejected (422).
    Speed must be between 0.50 and 2.00 with up to two decimal places.
    """
    return await service.upsert(user.id, body)

