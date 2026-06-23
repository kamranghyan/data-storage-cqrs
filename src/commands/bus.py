"""
Command Bus — the router between commands and their handlers.

Keeps the API layer clean: it only knows about commands, not handlers.
Adding a new command = register one new entry here.
"""

from sqlalchemy.orm import Session
from src.commands.models import CreateProductCommand, PlaceOrderCommand
from src.commands.handlers import handle_create_product, handle_place_order


# Registry: command type → handler function
_HANDLERS = {
    CreateProductCommand: handle_create_product,
    PlaceOrderCommand: handle_place_order,
}


def dispatch(command, db: Session) -> dict:
    """
    Route a command to its registered handler.
    Raises if no handler is registered for the command type.
    """
    handler = _HANDLERS.get(type(command))

    if not handler:
        raise NotImplementedError(f"No handler registered for {type(command).__name__}")

    return handler(command, db)
