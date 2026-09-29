"""Verified-purchase reviews (Blueprint sections G and H: social proof only once it is real).

- Only buyers can review: the link in their order email is signed per order.
- Only products in that order, only once each, only after payment.
- Moderation can reject only for a fixed reason; never for being negative.
- Public pages show nothing until at least one review is published.
"""
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Order, Review
from . import emails
from .shop import ShopError

# "placed" only exists when payments are off (local runs); production never creates it.
REVIEWABLE = ("placed", "paid", "shipped")
REJECT_REASONS = {
    "personal_data": "Contains personal details (address, phone, email)",
    "offensive": "Offensive or abusive language",
    "not_about_product": "Not about the product (e.g. only about delivery by a third party)",
    "spam": "Spam or advertising",
}


def _order(db: Session, order_id: str, token: str) -> Order:
    order = db.get(Order, order_id)
    # Same message for a wrong token and an unknown order: reveals nothing.
    if order is None or not emails.verify("review:" + order_id, token):
        raise ShopError("This review link isn't valid.", 404)
    if order.status not in REVIEWABLE:
        raise ShopError("You can review this order once it has been paid.", 409)
    return order


def display_name(full_name: str) -> str:
    parts = [p for p in full_name.strip().split() if p]
    if not parts:
        return "Verified buyer"
    first = parts[0][:30]
    return f"{first} {parts[-1][0].upper()}." if len(parts) > 1 else first


def form(db: Session, order_id: str, token: str) -> dict:
    order = _order(db, order_id, token)
    done = set(db.scalars(select(Review.product_id).where(Review.order_id == order.id)))
    seen, items = set(), []
    for line in order.items:
        if line.product_id in seen:
            continue
        seen.add(line.product_id)
        items.append({"product_id": line.product_id, "name": line.name, "reviewed": line.product_id in done})
    return {"order_id": order.id, "display_name": display_name(order.customer_name), "items": items}


def submit(db: Session, order_id: str, token: str, product_id: str, rating: int, title: str, body: str) -> Review:
    order = _order(db, order_id, token)
    if product_id not in {line.product_id for line in order.items}:
        raise ShopError("That product isn't in this order.", 400)
    review = Review(order_id=order.id, product_id=product_id, rating=rating, title=title.strip(),
                    body=body.strip(), display_name=display_name(order.customer_name))
    try:
        with db.begin_nested():
            db.add(review)
    except IntegrityError:
        raise ShopError("You've already reviewed this product. Thank you!", 409) from None
    return review


def summary(db: Session, product_id: str) -> dict:
    """Published reviews only. count == 0 means: show nothing, claim nothing."""
    rows = list(db.scalars(select(Review).where(Review.product_id == product_id, Review.status == "published")
                           .order_by(Review.published_at.desc(), Review.id.desc()).limit(50)))
    count, avg = db.execute(select(func.count(), func.avg(Review.rating))
                            .where(Review.product_id == product_id, Review.status == "published")).one()
    return {
        "count": count or 0,
        "average": round(float(avg), 1) if count else None,
        "reviews": [{"id": r.id, "rating": r.rating, "title": r.title, "body": r.body, "name": r.display_name,
                     "date": r.published_at or r.created_at, "verified": True} for r in rows],
    }


def moderate(db: Session, review_id: int, action: str, reason: str = "") -> Review:
    r = db.get(Review, review_id)
    if r is None:
        raise ShopError("Review not found", 404)
    if action == "publish":
        r.status, r.reject_reason = "published", ""
        r.published_at = r.published_at or datetime.now(timezone.utc)
    elif action == "reject":
        if reason not in REJECT_REASONS:
            raise ShopError("Pick a reason. Reviews can't be rejected just for being negative.", 400)
        r.status, r.reject_reason, r.published_at = "rejected", reason, None
    else:
        raise ShopError("Unknown action", 400)
    return r


def admin_list(db: Session, status: str | None = None, limit: int = 200) -> list[Review]:
    q = select(Review).order_by(Review.id.desc()).limit(min(max(limit, 1), 500))
    if status:
        q = q.where(Review.status == status)
    return list(db.scalars(q))
