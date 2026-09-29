"""Seed the Desk Reset test shortlist (Blueprint sections E/F/L).

Prices inc. VAT and costs are in pence and are ESTIMATES until supplier
quotes arrive. Stock values are placeholders. Safe to re-run: existing
products are left untouched.
"""

from sqlalchemy.orm import Session

from .db import Base, SessionLocal, engine
from .models import Product

PRODUCTS = [
    dict(id="desk-mat", name="Felt + Vegan-Leather Desk Mat, 90×40 cm", price=3200,
         landed_cost=600, shipping_cost=400, packaging_cost=100, stock=50),
    dict(id="cable-tray", name="Clamp-On Under-Desk Cable Tray (steel, no drilling)", price=3400,
         landed_cost=800, shipping_cost=450, packaging_cost=100, stock=50),
    dict(id="cable-clips", name="Walnut + Silicone Cable Clip Set", price=1800,
         landed_cost=300, shipping_cost=250, packaging_cost=50, stock=50),
    dict(id="monitor-riser", name="Oak Monitor Riser with Drawer", price=5900,
         landed_cost=1600, shipping_cost=650, packaging_cost=150, stock=20),
    dict(id="desk-reset", name="Desk Reset Bundle (mat + cable tray + clips)", price=7500,
         landed_cost=1700, shipping_cost=650, packaging_cost=200, stock=20, is_bundle=True),
]


def seed(db: Session) -> int:
    added = 0
    for data in PRODUCTS:
        if db.get(Product, data["id"]) is None:
            db.add(Product(**data))
            added += 1
    db.commit()
    return added


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        print(f"Seeded {seed(session)} new product(s).")
