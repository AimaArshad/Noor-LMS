"""Shared SlowAPI rate limiter instance.

Behind a reverse proxy, run uvicorn with ``--proxy-headers`` so the real client
IP is used as the rate-limit key.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=settings.RATE_LIMIT_STORAGE_URI,
)