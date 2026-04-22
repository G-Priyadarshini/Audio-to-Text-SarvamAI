import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
from app.config import settings

_logger = logging.getLogger("icepot")


def _detect_limiter_storage() -> str:
    """Use Redis for rate-limit storage if reachable, else in-memory."""
    try:
        import redis as _redis_sync

        r = _redis_sync.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            socket_connect_timeout=1,
        )
        r.ping()
        r.close()
        return settings.REDIS_URL
    except Exception:
        _logger.warning(
            "Redis not reachable — rate limiter will use in-memory storage"
        )
        return "memory://"


limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_detect_limiter_storage(),
    default_limits=[],
)


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": str(exc.detail),
        },
    )


# Rate limit strings
JOBS_RATE_LIMIT = f"{settings.RATE_LIMIT_JOBS_PER_MINUTE}/minute"
CHUNKS_RATE_LIMIT = f"{settings.RATE_LIMIT_CHUNKS_PER_MINUTE}/minute"
