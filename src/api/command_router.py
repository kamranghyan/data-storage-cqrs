"""
Command Router — /api/commands/*

All endpoints here change state. They:
  1. Parse the request into a command dataclass
  2. Pass it to the command bus
  3. Return the result

No query logic here. No reading from Elasticsearch or Redis.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session

from src.db.postgres import get_db
from src.commands.bus import dispatch
from src.commands.models import CreateProductCommand, PlaceOrderCommand, OrderItemInput

router = APIRouter(prefix="/api/commands", tags=["Commands (Write Side)"])


# ── Request Schemas (Pydantic for HTTP validation) ────────────────────────────

class CreateProductRequest(BaseModel):
    name: str
    category: str
    price: float
    stock: int


class OrderItemRequest(BaseModel):
    product_id: str
    quantity: int


class PlaceOrderRequest(BaseModel):
    customer_id: str
    items: List[OrderItemRequest]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/create-product", status_code=201)
def create_product(body: CreateProductRequest, db: Session = Depends(get_db)):
    """
    Create a new product in the catalog.

    Write flow:
      PostgreSQL (source of truth) → Redis Stream event → Elasticsearch (async)
    """
    cmd = CreateProductCommand(
        name=body.name,
        category=body.category,
        price=body.price,
        stock=body.stock,
    )
    return dispatch(cmd, db)


@router.post("/place-order", status_code=201)
def place_order(body: PlaceOrderRequest, db: Session = Depends(get_db)):
    """
    Place an order for a customer.

    Write flow:
      Validate stock in PostgreSQL → Decrement stock → Redis Stream event → Redis projection (async)

    Returns 400 if any product is out of stock.
    """
    try:
        cmd = PlaceOrderCommand(
            customer_id=body.customer_id,
            items=[
                OrderItemInput(product_id=i.product_id, quantity=i.quantity)
                for i in body.items
            ],
        )
        return dispatch(cmd, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
