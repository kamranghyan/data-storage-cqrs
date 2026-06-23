"""
Query Handlers — the read side of CQRS.

Critical rule: these handlers NEVER touch PostgreSQL.
They only read from the optimized read models:
  - Elasticsearch for product search
  - Redis for order projections

This is what makes queries fast — no joins, no ORM overhead,
data is already shaped for the response.
"""

import json
import redis
from elasticsearch import Elasticsearch
from src.queries.models import SearchProductsQuery, GetMyOrdersQuery
from src.config import settings

_redis = redis.from_url(settings.redis_url, decode_responses=True)
_es = Elasticsearch(settings.es_url)


def handle_search_products(query: SearchProductsQuery) -> dict:
    """
    Search the product catalog using Elasticsearch.

    Supports:
      - Full-text search on product name
      - Filter by category
      - Filter by price range

    All of these would be expensive on PostgreSQL at scale.
    Elasticsearch handles them natively with inverted indexes.
    """
    must_clauses = []
    filter_clauses = []

    # Full-text search on product name
    if query.q:
        must_clauses.append({
            "match": {"name": {"query": query.q, "fuzziness": "AUTO"}}
        })

    # Exact filter on category (keyword field — no tokenization)
    if query.category:
        filter_clauses.append({
            "term": {"category": query.category}
        })

    # Price range filter
    price_range = {}
    if query.min_price is not None:
        price_range["gte"] = query.min_price
    if query.max_price is not None:
        price_range["lte"] = query.max_price
    if price_range:
        filter_clauses.append({"range": {"price": price_range}})

    # Build the final ES query
    es_query = {
        "bool": {
            "must": must_clauses or [{"match_all": {}}],
            "filter": filter_clauses,
        }
    }

    response = _es.search(
        index=settings.es_index,
        query=es_query,
        size=20,
    )

    products = [
        {
            "id": hit["_id"],
            **hit["_source"],
        }
        for hit in response["hits"]["hits"]
    ]

    return {
        "total": response["hits"]["total"]["value"],
        "products": products,
    }


def handle_get_my_orders(query: GetMyOrdersQuery) -> dict:
    """
    Fetch order history for a customer from the Redis projection.

    The projector pre-built these when 'order.placed' events were processed.
    No DB joins needed — the full order shape is already stored.

    This is the trade-off: we accept eventual consistency in exchange
    for O(1) read performance.
    """
    customer_key = f"orders:{query.customer_id}"

    # Fetch all orders for this customer (newest first, LPUSH order)
    raw_orders = _redis.lrange(customer_key, 0, -1)

    orders = [json.loads(o) for o in raw_orders]

    return {
        "customer_id": query.customer_id,
        "total_orders": len(orders),
        "orders": orders,
    }
