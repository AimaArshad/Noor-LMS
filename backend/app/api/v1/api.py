"""Aggregate router for API v1. Feature routers are included here."""

from fastapi import APIRouter

from app.api.v1.routers import auth

api_router = APIRouter()


@api_router.get("/ping", tags=["meta"], summary="API v1 placeholder")
async def ping() -> dict[str, str]:
    """Placeholder endpoint proving the v1 router is mounted."""
    return {"message": "pong", "version": "v1"}


api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Later steps:
# api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
# api_router.include_router(users.router, prefix="/users", tags=["users"])


# Later steps:
# api_router.include_router(users.router, prefix="/users", tags=["users"])
# api_router.include_router(classrooms.router, prefix="/classrooms", tags=["classrooms"])