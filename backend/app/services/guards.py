"""Small cross-module guards shared by services."""

from fastapi import HTTPException, status


def ensure_not_archived(is_archived: bool) -> None:
    """Archived classrooms are read-only.

    Raises:
        HTTPException: 403 when ``is_archived`` is true.
    """
    if is_archived:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This classroom is archived and read-only. Unarchive it to make changes.",
        )