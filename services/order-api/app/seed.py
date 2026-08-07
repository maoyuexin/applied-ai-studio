from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Inventory, Product


PRODUCTS = [
    {
        "id": "trail-pack",
        "name": "Ridge Trail Pack",
        "description": "Weather-ready 28L day pack with a suspended laptop sleeve.",
        "category": "Carry",
        "price_cents": 8900,
        "image_url": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=85",
        "quantity": 24,
    },
    {
        "id": "steel-bottle",
        "name": "Alpine Steel Bottle",
        "description": "Double-wall insulated bottle for all-day temperature control.",
        "category": "Hydration",
        "price_cents": 3200,
        "image_url": "https://images.unsplash.com/photo-1602143407151-7111542de6e8?auto=format&fit=crop&w=900&q=85",
        "quantity": 42,
    },
    {
        "id": "city-runner",
        "name": "City Runner",
        "description": "Lightweight everyday trainer with a responsive recycled sole.",
        "category": "Footwear",
        "price_cents": 11800,
        "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=85",
        "quantity": 18,
    },
    {
        "id": "studio-headphones",
        "name": "Studio Wireless",
        "description": "Over-ear wireless headphones with adaptive noise control.",
        "category": "Audio",
        "price_cents": 16400,
        "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=85",
        "quantity": 12,
    },
    {
        "id": "field-watch",
        "name": "Field Watch",
        "description": "Minimal stainless watch with a durable woven strap.",
        "category": "Accessories",
        "price_cents": 13600,
        "image_url": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=85",
        "quantity": 16,
    },
    {
        "id": "coast-frames",
        "name": "Coast Frames",
        "description": "Polarized everyday sunglasses with plant-based frames.",
        "category": "Accessories",
        "price_cents": 7400,
        "image_url": "https://images.unsplash.com/photo-1511499767150-a48a237f0083?auto=format&fit=crop&w=900&q=85",
        "quantity": 31,
    },
]


def seed_products(session: Session) -> None:
    if session.scalar(select(func.count(Product.id))):
        return
    for item in PRODUCTS:
        product = Product(
            id=item["id"],
            name=item["name"],
            description=item["description"],
            category=item["category"],
            price_cents=item["price_cents"],
            image_url=item["image_url"],
        )
        product.inventory = Inventory(quantity_available=item["quantity"])
        session.add(product)
    session.commit()
