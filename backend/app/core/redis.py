"""Shared async Redis client (token blacklist; later Celery/WebSocket helpers)."""

from redis.asyncio import Redis

from app.core.config import settings

# Connections are created lazily, so importing this module never needs Redis to be up.
redis_client: Redis = Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)


async def get_redis() -> Redis:
    """FastAPI dependency returning the shared client."""
    return redis_client


async def close_redis() -> None:
    """Close pooled connections (called on application shutdown)."""
    await redis_client.aclose()