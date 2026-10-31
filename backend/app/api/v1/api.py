"""Aggregate router for API v1. Feature routers are included here."""

from fastapi import APIRouter

from app.api.v1.routers import announcements, assignments, auth, classrooms, comments, files

api_router = APIRouter()


@api_router.get("/ping", tags=["meta"], summary="API v1 placeholder")
async def ping() -> dict[str, str]:
    """Placeholder endpoint proving the v1 router is mounted."""
    return {"message": "pong", "version": "v1"}


api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(classrooms.router, prefix="/classrooms", tags=["classrooms"])
# Prefixes containing {classroom_id} are read by the classroom access dependencies.
api_router.include_router(
    announcements.router,
    prefix="/classrooms/{classroom_id}/announcements",
    tags=["announcements"],
)
api_router.include_router(
    assignments.classroom_router,
    prefix="/classrooms/{classroom_id}/assignments",
    tags=["assignments"],
)
api_router.include_router(assignments.router, prefix="/assignments", tags=["assignments"])
api_router.include_router(assignments.submissions_router, prefix="/submissions", tags=["submissions"])
api_router.include_router(comments.router, prefix="/comments", tags=["comments"])
api_router.include_router(files.router, prefix="/files", tags=["files"])

# Later steps:
# api_router.include_router(users.router, prefix="/users", tags=["users"])

