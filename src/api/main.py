"""
CQRS E-Commerce Demo — Main FastAPI Application

Two clearly separated router groups:
  /api/commands/* → Write side (PostgreSQL)
  /api/queries/*  → Read side  (Elasticsearch + Redis)

This separation is the core of CQRS visible at the API level.
"""

from fastapi import FastAPI
from src.db.postgres import engine
from src.db.models import Base
from src.api.command_router import router as command_router
from src.api.query_router import router as query_router

app = FastAPI(
    title="CQRS E-Commerce Demo",
    description=(
        "A minimal but realistic CQRS implementation.\n\n"
        "**Write side** → PostgreSQL (consistency, validation)\n\n"
        "**Read side** → Elasticsearch (product search) + Redis (order projections)\n\n"
        "**Sync** → Redis Streams + Projector Worker (eventual consistency)"
    ),
    version="1.0.0",
)

# Create PostgreSQL tables on startup
Base.metadata.create_all(bind=engine)

# Mount the two sides
app.include_router(command_router)
app.include_router(query_router)


@app.get("/", tags=["Health"])
def root():
    return {
        "status": "ok",
        "write_side": "/api/commands",
        "read_side": "/api/queries",
        "docs": "/docs",
    }
