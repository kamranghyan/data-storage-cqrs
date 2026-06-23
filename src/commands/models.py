"""
Commands represent the INTENT to change system state.

They are plain dataclasses — no business logic here.
Each command maps to exactly one handler.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class CreateProductCommand:
    """Issued when an admin adds a new product to the catalog."""
    name: str
    category: str
    price: float
    stock: int


@dataclass
class OrderItemInput:
    product_id: str
    quantity: int


@dataclass
class PlaceOrderCommand:
    """Issued when a customer places an order."""
    customer_id: str
    items: List[OrderItemInput]
