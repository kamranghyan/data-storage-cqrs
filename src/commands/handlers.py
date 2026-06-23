"""
Command Handlers — the write side of CQRS.

Each handler:
  1. Validates the command
  2. Applies business rules
  3. Writes to PostgreSQL (the source of truth)
  4. Emits a domain event so the read side can sync
"""

import uuid
from sqlalchemy.orm import Session
from src.commands.models import CreateProductCommand, PlaceOrderCommand
from src.db.models import Product, Order, OrderItem
from src.events.publisher import publish_event


def handle_create_product(cmd: CreateProductCommand, db: Session) -> dict:
    """
    Creates a product in PostgreSQL, then emits a product.created event.
    The projector will pick up this event and index the product in Elasticsearch.
    """
    product = Product(
        id=str(uuid.uuid4()),
        name=cmd.name,
        category=cmd.category,
        price=cmd.price,
        stock=cmd.stock,
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    # Emit event → triggers Elasticsearch sync via projector
    publish_event("product.created", {
        "id": product.id,
        "name": product.name,
        "category": product.category,
        "price": product.price,
        "stock": product.stock,
    })

    return {"product_id": product.id, "status": "created"}


def handle_place_order(cmd: PlaceOrderCommand, db: Session) -> dict:
    """
    Places an order with stock validation.

    Business rules enforced here (write side):
      - Every product must exist
      - Stock must be sufficient for each item
      - Stock is decremented atomically before commit

    After commit, emits an order.placed event so the projector
    can build a fast Redis read projection for order history queries.
    """
    order_items = []
    total_price = 0.0

    for item_input in cmd.items:
        product = db.get(Product, item_input.product_id)

        if not product:
            raise ValueError(f"Product '{item_input.product_id}' not found")

        if product.stock < item_input.quantity:
            raise ValueError(
                f"Insufficient stock for '{product.name}'. "
                f"Available: {product.stock}, Requested: {item_input.quantity}"
            )

        # Decrement stock — this is the consistency-critical write
        product.stock -= item_input.quantity
        line_total = product.price * item_input.quantity
        total_price += line_total

        order_items.append(OrderItem(
            id=str(uuid.uuid4()),
            product_id=product.id,
            quantity=item_input.quantity,
            unit_price=product.price,
        ))

        # Emit stock update so Elasticsearch stays in sync
        publish_event("product.stock_updated", {
            "id": product.id,
            "stock": product.stock,
        })

    order = Order(
        id=str(uuid.uuid4()),
        customer_id=cmd.customer_id,
        total_price=round(total_price, 2),
        status="confirmed",
    )

    for item in order_items:
        item.order_id = order.id

    db.add(order)
    db.add_all(order_items)
    db.commit()
    db.refresh(order)

    # Emit event → triggers Redis projection update for GetMyOrders query
    publish_event("order.placed", {
        "order_id": order.id,
        "customer_id": order.customer_id,
        "total_price": order.total_price,
        "status": order.status,
        "items": [
            {
                "product_id": i.product_id,
                "quantity": i.quantity,
                "unit_price": i.unit_price,
            }
            for i in order_items
        ],
    })

    return {"order_id": order.id, "total_price": order.total_price, "status": "confirmed"}
