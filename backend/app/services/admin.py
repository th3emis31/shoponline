"""Admin actions. Every write is validated, applied atomically and audited."""

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AdminAudit, Order, Product
from . import analytics, unit_economics
from .payments import release_stock
from .shop import ShopError

# Allowed manual status changes. Paid orders are never cancelled here:
# refunds must be issued in the Stripe dashboard first.
TRANSITIONS: dict[str, set[str]] = {
    "placed": {"shipped", "cancelled"},
    "pending_payment": {"cancelled"},
    "payment_review": {"paid", "cancelled"},
    "paid": {"shipped"},
    "shipped": set(),
    "cancelled": set(),
}
STOCK_HOLDING = {"placed", "pending_payment", "payment_review"}


def audit(db: Session, action: str, target: str, **detail) -> None:
    db.add(AdminAudit(action=action, target=target, detail=json.dumps(detail, default=str)))


def list_orders(db: Session, status: str | None = None, limit: int = 100) -> list[Order]:
    q = select(Order).order_by(Order.created_at.desc()).limit(min(max(limit, 1), 500))
    if status:
        q = q.where(Order.status == status)
    return list(db.scalars(q))


def set_order_status(db: Session, order_id: str, new_status: str, note: str = "") -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise ShopError("Order not found", 404)
    old = order.status
    if new_status not in TRANSITIONS.get(old, set()):
        allowed = ", ".join(sorted(TRANSITIONS.get(old, set()))) or "none"
        raise ShopError(f"Cannot change {old} to {new_status} (allowed: {allowed})", 409)
    try:
        if new_status == "cancelled" and old in STOCK_HOLDING:
            release_stock(db, order)
        if new_status == "paid":
            order.paid_at = datetime.now(timezone.utc)
            analytics.record(db, "purchase", commit=False)
        order.status = new_status
        audit(db, "order.status", order.id, old=old, new=new_status, note=note)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return order


def product_row(p: Product) -> dict:
    ue = unit_economics.calculate(p.price, p.landed_cost, p.shipping_cost, p.packaging_cost)
    return {
        "id": p.id, "name": p.name, "price": p.price, "stock": p.stock, "active": p.active,
        "is_bundle": p.is_bundle, "landed_cost": p.landed_cost, "shipping_cost": p.shipping_cost,
        "packaging_cost": p.packaging_cost, "contribution_pre_ads": ue.contribution_pre_ads,
        "contribution_margin": ue.contribution_margin, "break_even_roas": ue.break_even_roas,
        "label": "ESTIMATE",
    }


def list_products(db: Session) -> list[dict]:
    return [product_row(p) for p in db.scalars(select(Product).order_by(Product.price))]


EDITABLE = ("price", "stock", "active", "landed_cost", "shipping_cost", "packaging_cost")


def update_product(db: Session, product_id: str, changes: dict, note: str = "") -> dict:
    p = db.get(Product, product_id)
    if p is None:
        raise ShopError("Product not found", 404)
    changes = {k: v for k, v in changes.items() if k in EDITABLE and v is not None}
    if not changes:
        raise ShopError("No changes given")
    before = {k: getattr(p, k) for k in changes}
    for k, v in changes.items():
        setattr(p, k, v)
    audit(db, "product.update", p.id, before=before, after=changes, note=note)
    db.commit()
    return product_row(p)


def audit_log(db: Session, limit: int = 100) -> list[AdminAudit]:
    return list(db.scalars(select(AdminAudit).order_by(AdminAudit.id.desc()).limit(min(max(limit, 1), 500))))
