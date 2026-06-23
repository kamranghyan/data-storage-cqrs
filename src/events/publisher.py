"""
Event Publisher — the bridge between the write side and read side.

After every successful command, handlers call publish_event().
This drops a message onto a Redis Stream, which the projector worker
consumes asynchronously to update Elasticsearch and Redis projections.

This is where eventual consistency begins.
"""

import json
import redis
from src.config import settings

# Single Redis connection reused across the app
_redis = redis.from_url(settings.redis_url, decode_responses=True)


def publish_event(event_type: str, payload: dict) -> None:
    """
    Publish a domain event to the Redis Stream.

    Fields:
      - type: event name (e.g. "product.created", "order.placed")
      - data: JSON-serialized payload
    """
    _redis.xadd(
        settings.stream_key,
        {
            "type": event_type,
            "data": json.dumps(payload),
        }
    )
