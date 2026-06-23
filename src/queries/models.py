"""
Queries represent the INTENT to read data — no side effects, ever.

Queries hit the read models (Elasticsearch, Redis) — never PostgreSQL.
This is the key separation in CQRS.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SearchProductsQuery:
    """Full-text search across the product catalog (hits Elasticsearch)."""
    q: Optional[str] = None          # Free-text search term
    category: Optional[str] = None   # Filter by category
    min_price: Optional[float] = None
    max_price: Optional[float] = None


@dataclass
class GetMyOrdersQuery:
    """Fetch order history for a customer (hits Redis projection)."""
    customer_id: str
