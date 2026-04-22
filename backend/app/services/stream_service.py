import json
import logging
from typing import AsyncIterator
from redis.asyncio import Redis

logger = logging.getLogger("icepot")


class StreamService:
    """Manages real-time streaming state via Redis pub/sub."""

    def __init__(self, redis: Redis):
        self.redis = redis

    async def publish_partial(
        self, job_id: str, partial_data: dict
    ) -> None:
        """Publish a partial transcript update."""
        channel = f"stream:{job_id}"
        message = json.dumps(partial_data)

        # Store in Redis list (for reconnection)
        await self.redis.rpush(f"stream_history:{job_id}", message)
        await self.redis.expire(f"stream_history:{job_id}", 7200)

        # Publish to channel
        await self.redis.publish(channel, message)

    async def publish_complete(self, job_id: str) -> None:
        """Signal that streaming is complete."""
        channel = f"stream:{job_id}"
        message = json.dumps({"type": "complete"})
        await self.redis.publish(channel, message)

    async def publish_status(self, job_id: str, data: dict) -> None:
        """Publish a status event (e.g. sarvam_job_submitted)."""
        channel = f"stream:{job_id}"
        message = json.dumps(data)
        # Store in history for reconnection
        await self.redis.rpush(f"stream_history:{job_id}", message)
        await self.redis.expire(f"stream_history:{job_id}", 7200)
        await self.redis.publish(channel, message)

    async def publish_error(self, job_id: str, error: str) -> None:
        """Signal an error during streaming."""
        channel = f"stream:{job_id}"
        message = json.dumps({"type": "error", "error": error})
        await self.redis.publish(channel, message)

    async def get_history(self, job_id: str) -> list:
        """Get all partial transcripts for a job (for reconnection)."""
        key = f"stream_history:{job_id}"
        items = await self.redis.lrange(key, 0, -1)
        return [json.loads(item) for item in items]

    async def subscribe(
        self, job_id: str
    ) -> AsyncIterator[dict]:
        """
        Subscribe to streaming updates for a job.
        Yields partial transcript dicts as they arrive.
        """
        channel = f"stream:{job_id}"
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    yield data
                    if data.get("type") in ("complete", "error"):
                        break
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    async def cleanup(self, job_id: str) -> None:
        """Clean up stream data."""
        await self.redis.delete(f"stream_history:{job_id}")
