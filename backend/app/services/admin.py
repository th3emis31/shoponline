"""Admin actions. Every write is validated, applied atomically and audited."""

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AdminAudit, Order, Product
from . import analytics, orders, unit_economics
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
# Staff may only ship. Anything involving money (accepting a reviewed payment,
# cancelling) needs the owner.
STAFF_TRANSITIONS = {("placed", "shipped"), ("paid", "shipped")}


def audit(db: Session, action: str, target: str, actor: str | None = None, **detail) -> None:
    db.add(AdminAudit(action=action, target=target, actor=actor, detail=json.dumps(detail, default=str)))


def list_orders(db: Session, status: str | None = None, limit: int = 100) -> list[Order]:
    q = select(Order).order_by(Order.created_at.desc()).limit(min(max(limit, 1), 500))
    if status:
        q = q.where(Order.status == status)
    return list(db.scalars(q))


def set_order_status(db: Session, order_id: str, new_status: str, note: str = "",
                     actor: str | None = None, role: str = "owner") -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise ShopError("Order not found", 404)
    old = order.status
    if new_status not in TRANSITIONS.get(old, set()):
        allowed = ", ".join(sorted(TRANSITIONS.get(old, set()))) or "none"
        raise ShopError(f"Cannot change {old} to {new_status} (allowed: {allowed})", 409)
    if role != "owner" and (old, new_status) not in STAFF_TRANSITIONS:
        raise ShopError("Only the owner can do this", 403)
    if old == "pending_payment" and new_status == "cancelled" and order.stripe_session_id:
        # Close the Stripe checkout first so the customer can't pay a cancelled order.
        from . import payments
        if payments.payments_enabled():
            try:
                payments.expire_session(order.stripe_session_id)
            except Exception as exc:
                raise ShopError("Couldn't close the Stripe checkout (it may just have been paid). "
                                "Wait a minute and check again.", 409) from exc
    try:
        values = {"paid_at": datetime.now(timezone.utc)} if new_status == "paid" else {}
        if not orders.move(db, order.id, {old}, new_status, **values):
            raise ShopError("This order changed meanwhile. Reload and try again.", 409)
        if new_status == "cancelled":
            orders.release_stock(db, order.id)
        if new_status == "paid":
            orders.reserve_stock(db, order.id)  # accepted after review: take the items again
            analytics.record(db, "purchase", commit=False)
            orders.create_supplier_orders(db, order.id)
        audit(db, "order.status", order.id, actor=actor, old=old, new=new_status, note=note)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(order)
    return order


def economics(p: Product, price: int | None = None):
    """Unit economics for a product. Dropship: the supplier's price (incl. delivery to
    the customer) is the whole cost; there is no own shipping or packaging."""
    price = p.price if price is None else price
    if p.is_dropship:
        return unit_economics.calculate(price, p.supplier_cost, 0, 0)
    return unit_economics.calculate(price, p.landed_cost, p.shipping_cost, p.packaging_cost)


def product_row(p: Product) -> dict:
    ue = economics(p)
    return {
        "id": p.id, "name": p.name, "price": p.price, "stock": p.stock, "active": p.active,
        "is_bundle": p.is_bundle, "landed_cost": p.landed_cost, "shipping_cost": p.shipping_cost,
        "packaging_cost": p.packaging_cost, "contribution_pre_ads": ue.contribution_pre_ads,
        "fulfilment": p.fulfilment, "supplier_name": p.supplier_name, "supplier_url": p.supplier_url,
        "supplier_cost": p.supplier_cost, "delivery_estimate": p.delivery_estimate,
        "contribution_margin": ue.contribution_margin, "break_even_roas": ue.break_even_roas,
        "label": "ESTIMATE",
    }


def list_products(db: Session) -> list[dict]:
    return [product_row(p) for p in db.scalars(select(Product).order_by(Product.price))]


EDITABLE = ("price", "stock", "active", "landed_cost", "shipping_cost", "packaging_cost",
            "fulfilment", "supplier_name", "supplier_url", "supplier_cost", "delivery_estimate")


def update_product(db: Session, product_id: str, changes: dict, note: str = "",
                   actor: str | None = None) -> dict:
    p = db.get(Product, product_id)
    if p is None:
        raise ShopError("Product not found", 404)
    changes = {k: v for k, v in changes.items() if k in EDITABLE and v is not None}
    if not changes:
        raise ShopError("No changes given")
    before = {k: getattr(p, k) for k in changes}
    for k, v in changes.items():
        setattr(p, k, v)
    audit(db, "product.update", p.id, actor=actor, before=before, after=changes, note=note)
    db.commit()
    return product_row(p)


def audit_log(db: Session, limit: int = 100) -> list[AdminAudit]:
    return list(db.scalars(select(AdminAudit).order_by(AdminAudit.id.desc()).limit(min(max(limit, 1), 500))))
