"""
Query Router — /api/queries/*

All endpoints here are read-only. They:
  1. Build a query dataclass from request params
  2. Call the appropriate query handler
  3. Return the result

No DB writes here. No PostgreSQL access. Pure reads from ES and Redis.
"""

from fastapi import APIRouter
from typing import Optional

from src.queries.models import SearchProductsQuery, GetMyOrdersQuery
from src.queries.handlers import handle_search_products, handle_get_my_orders

router = APIRouter(prefix="/api/queries", tags=["Queries (Read Side)"])


@router.get("/products")
def search_products(
    q: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
):
    """
    Search the product catalog (hits Elasticsearch — NOT PostgreSQL).

    Supports full-text search, category filtering, and price range.
    Data here may be up to ~200ms behind the write model (eventual consistency).
    """
    query = SearchProductsQuery(
        q=q,
        category=category,
        min_price=min_price,
        max_price=max_price,
    )
    return handle_search_products(query)


@router.get("/orders/{customer_id}")
def get_my_orders(customer_id: str):
    """
    Get order history for a customer (hits Redis — NOT PostgreSQL).

    Orders are pre-projected into Redis when 'order.placed' events are processed.
    This is an O(1) read — no joins, no ORM, just a Redis list fetch.
    """
    query = GetMyOrdersQuery(customer_id=customer_id)
    return handle_get_my_orders(query)
