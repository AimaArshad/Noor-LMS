"""Refresh-token revocation list stored in Redis (entries expire with the token)."""

from redis.asyncio import Redis

_KEY = "auth:revoked:{jti}"


async def revoke_token(redis: Redis, jti: str, ttl_seconds: int) -> bool:
    """Atomically mark a token id as revoked.

    Returns:
        ``True`` if this call revoked it, ``False`` if it was already revoked
        (i.e. the token is being reused). ``SET NX`` makes rotation race-free.

    Raises:
        redis.exceptions.RedisError: When Redis is unreachable.
    """
    result = await redis.set(_KEY.format(jti=jti), "1", ex=max(int(ttl_seconds), 1), nx=True)
    return bool(result)