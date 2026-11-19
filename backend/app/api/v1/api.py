"""Aggregate router for API v1. Feature routers are included here."""

from fastapi import APIRouter

from app.api.v1.routers import (
    accessibility,
    announcements,
    assignments,
    auth,
    classrooms,
    comments,
    files,
    materials,
    notifications,
    quizzes,
    todo,
    users,
)

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
api_router.include_router(
    quizzes.classroom_router,
    prefix="/classrooms/{classroom_id}/quizzes",
    tags=["quizzes"],
)
api_router.include_router(quizzes.router, prefix="/quizzes", tags=["quizzes"])
api_router.include_router(
    materials.router,
    prefix="/classrooms/{classroom_id}/materials",
    tags=["materials"],
)
api_router.include_router(comments.router, prefix="/comments", tags=["comments"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(todo.router, prefix="/todo", tags=["todo"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(
    accessibility.router, prefix="/accessibility", tags=["accessibility"]
)
api_router.include_router(users.router, prefix="/users", tags=["users"])

# Later steps:
# api_router.include_router(users.router, prefix="/users", tags=["users"])