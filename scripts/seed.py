"""
Seed Script — populates the write DB with sample products.

Run after starting all services:
  python -m scripts.seed

This calls the command API directly (not the DB),
so the full CQRS flow runs: PostgreSQL → Event → Elasticsearch.

Make sure the projector worker is running before seeding,
otherwise products won't appear in search queries.
"""

import requests

API_BASE = "http://localhost:8000"

PRODUCTS = [
    {"name": "MacBook Pro 14",       "category": "laptops",      "price": 1999.99, "stock": 10},
    {"name": "Dell XPS 15",          "category": "laptops",      "price": 1599.99, "stock": 5},
    {"name": "Sony WH-1000XM5",      "category": "headphones",   "price": 349.99,  "stock": 20},
    {"name": "Samsung 4K Monitor",   "category": "monitors",     "price": 499.99,  "stock": 8},
    {"name": "Logitech MX Master 3", "category": "accessories",  "price": 99.99,   "stock": 30},
    {"name": "iPad Pro 12.9",        "category": "tablets",      "price": 1099.99, "stock": 15},
    {"name": "Apple AirPods Pro",    "category": "headphones",   "price": 249.99,  "stock": 25},
    {"name": "Keychron K2 Keyboard", "category": "accessories",  "price": 89.99,   "stock": 40},
]


def seed():
    print("Seeding products via command API...\n")

    for product in PRODUCTS:
        response = requests.post(f"{API_BASE}/api/commands/create-product", json=product)

        if response.status_code == 201:
            data = response.json()
            print(f"  ✓ Created: {product['name']} → id={data['product_id']}")
        else:
            print(f"  ✗ Failed: {product['name']} → {response.text}")

    print(f"\nDone. {len(PRODUCTS)} products seeded.")
    print("Wait ~1-2 seconds for the projector to sync to Elasticsearch.")
    print("Then try: GET /api/queries/products?q=laptop")


if __name__ == "__main__":
    seed()
