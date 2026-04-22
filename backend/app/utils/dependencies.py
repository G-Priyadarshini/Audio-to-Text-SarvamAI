from typing import Optional
from fastapi import Depends, Request
from app.services.upload_service import UploadService
from app.services.stream_service import StreamService


async def get_redis(request: Request):
    """Get Redis connection from app state.  Returns None when Redis is unavailable."""
    return getattr(request.app.state, "redis", None)


async def get_upload_service(
    redis=Depends(get_redis),
) -> UploadService:
    return UploadService(redis)  # UploadService handles redis=None via filesystem


async def get_stream_service(
    redis=Depends(get_redis),
) -> StreamService:
    if redis is None:
        raise RuntimeError(
            "Streaming requires Redis. Please start Redis and restart the server."
        )
    return StreamService(redis)
