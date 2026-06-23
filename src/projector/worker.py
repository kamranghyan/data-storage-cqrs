"""
Projector Worker — the sync engine between write and read models.

This is a long-running process that:
  1. Reads events from the Redis Stream (using consumer groups for reliability)
  2. Routes each event to the correct projection handler
  3. Updates Elasticsearch (product catalog) and Redis (order projections)

This is the heart of eventual consistency in CQRS.
Run it separately: python -m src.projector.worker
"""

import json
import time
import redis
from elasticsearch import Elasticsearch
from src.config import settings

# Clients
_redis = redis.from_url(settings.redis_url, decode_responses=True)
_es = Elasticsearch(settings.es_url)


# ── Projection Handlers ──────────────────────────────────────────────────────

def on_product_created(payload: dict) -> None:
    """Index a new product document in Elasticsearch."""
    _es.index(
        index=settings.es_index,
        id=payload["id"],
        document={
            "name": payload["name"],
            "category": payload["category"],
            "price": payload["price"],
            "stock": payload["stock"],
        }
    )
    print(f"  [ES] Indexed product: {payload['name']} (id={payload['id']})")


def on_product_stock_updated(payload: dict) -> None:
    """Partial update — only sync the stock field in Elasticsearch."""
    _es.update(
        index=settings.es_index,
        id=payload["id"],
        doc={"stock": payload["stock"]},
    )
    print(f"  [ES] Stock updated: product={payload['id']} stock={payload['stock']}")


def on_order_placed(payload: dict) -> None:
    """
    Build a denormalized order projection in Redis.

    Instead of joining Order + OrderItem tables at query time,
    we pre-build the full order shape here and store it as JSON.
    GetMyOrders then just fetches this — no DB joins needed.
    """
    customer_key = f"orders:{payload['customer_id']}"
    order_summary = {
        "order_id": payload["order_id"],
        "total_price": payload["total_price"],
        "status": payload["status"],
        "items": payload["items"],
    }
    # Push to a Redis list (newest orders first)
    _redis.lpush(customer_key, json.dumps(order_summary))
    print(f"  [Redis] Order projection saved for customer: {payload['customer_id']}")


# ── Event Router ─────────────────────────────────────────────────────────────

_PROJECTIONS = {
    "product.created": on_product_created,
    "product.stock_updated": on_product_stock_updated,
    "order.placed": on_order_placed,
}


def process_event(event_type: str, payload: dict) -> None:
    handler = _PROJECTIONS.get(event_type)
    if handler:
        handler(payload)
    else:
        print(f"  [Projector] No handler for event type: {event_type}")


# ── Bootstrap ────────────────────────────────────────────────────────────────

def bootstrap() -> None:
    """
    Create the Elasticsearch index and Redis consumer group if they don't exist.
    Safe to call on every startup.
    """
    # Elasticsearch index with explicit mappings
    if not _es.indices.exists(index=settings.es_index):
        _es.indices.create(
            index=settings.es_index,
            mappings={
                "properties": {
                    "name":     {"type": "text"},
                    "category": {"type": "keyword"},
                    "price":    {"type": "float"},
                    "stock":    {"type": "integer"},
                }
            }
        )
        print(f"[Bootstrap] Created Elasticsearch index: {settings.es_index}")

    # Redis Stream consumer group (MKSTREAM creates stream if not exists)
    try:
        _redis.xgroup_create(
            settings.stream_key,
            settings.stream_group,
            id="0",
            mkstream=True,
        )
        print(f"[Bootstrap] Created consumer group: {settings.stream_group}")
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" in str(e):
            print(f"[Bootstrap] Consumer group already exists, continuing...")
        else:
            raise


# ── Main Loop ────────────────────────────────────────────────────────────────

def run() -> None:
    print("[Projector] Starting... waiting for events.")
    bootstrap()

    while True:
        try:
            # Block for up to 2 seconds waiting for new messages
            messages = _redis.xreadgroup(
                groupname=settings.stream_group,
                consumername=settings.stream_consumer,
                streams={settings.stream_key: ">"},
                count=10,
                block=2000,
            )

            if not messages:
                continue

            for stream_name, entries in messages:
                for entry_id, fields in entries:
                    event_type = fields.get("type")
                    raw_data = fields.get("data", "{}")

                    try:
                        payload = json.loads(raw_data)
                        print(f"\n[Projector] Event received: {event_type}")
                        process_event(event_type, payload)

                        # Acknowledge — tells Redis this message was processed
                        _redis.xack(settings.stream_key, settings.stream_group, entry_id)

                    except Exception as e:
                        print(f"[Projector] ERROR processing {event_type}: {e}")

        except KeyboardInterrupt:
            print("\n[Projector] Shutting down.")
            break
        except Exception as e:
            print(f"[Projector] Unexpected error: {e}. Retrying in 3s...")
            time.sleep(3)


if __name__ == "__main__":
    run()
