"""Stripe hosted Checkout + verified webhooks (Blueprint sections H, K, O).

Card data never touches our server. Every state change comes from a
signature-verified webhook, is checked against the order total, and is
applied at most once per Stripe event ID.
"""

import json
from datetime import datetime, timedelta, timezone

import stripe
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Order, Product, StripeEvent
from . import analytics
from .shop import ShopError

CURRENCY = "gbp"


def payments_enabled() -> bool:
    return bool(settings.stripe_secret_key)


def _stripe_client() -> stripe.StripeClient:
    return stripe.StripeClient(settings.stripe_secret_key)


def create_checkout_session(order: Order) -> tuple[str, str]:
    """Create a hosted Checkout Session; returns (session_id, url)."""
    expires = datetime.now(timezone.utc) + timedelta(minutes=max(30, settings.checkout_expiry_minutes))
    params = {
        "mode": "payment",
        "client_reference_id": order.id,
        "customer_email": order.customer_email,
        "metadata": {"order_id": order.id},
        "expires_at": int(expires.timestamp()),
        "line_items": [
            {
                "quantity": item.quantity,
                "price_data": {
                    "currency": CURRENCY,
                    "unit_amount": item.unit_price,
                    "product_data": {"name": item.name},
                },
            }
            for item in order.items
        ],
        "shipping_options": [
            {
                "shipping_rate_data": {
                    "type": "fixed_amount",
                    "display_name": "Standard UK delivery",
                    "fixed_amount": {"amount": order.shipping, "currency": CURRENCY},
                }
            }
        ],
        "success_url": f"{settings.public_base_url}/order/{order.id}?paid=1",
        "cancel_url": f"{settings.public_base_url}/cart",
    }
    session = _stripe_client().v1.checkout.sessions.create(
        params, options={"idempotency_key": f"checkout-{order.id}"}
    )
    return session.id, session.url


def retrieve_session(session_id: str) -> dict:
    """Current state of a Checkout Session from Stripe, as a plain dict."""
    session = _stripe_client().v1.checkout.sessions.retrieve(session_id)
    return {
        "id": session.id,
        "status": session.status,  # open | complete | expired
        "payment_status": session.payment_status,  # paid | unpaid | no_payment_required
        "amount_total": session.amount_total,
        "currency": session.currency,
    }


def expire_session(session_id: str) -> None:
    """Close a still-open Checkout Session so it can no longer be paid."""
    _stripe_client().v1.checkout.sessions.expire(session_id)


def reconcile_pending(db: Session, order: Order) -> str:
    """Settle an old pending_payment order against Stripe's own record.

    Safe by construction: an order is only cancelled after Stripe confirms the
    session is expired (or we expire it ourselves, so it can't be paid later).
    Any Stripe error leaves the order untouched for the next run.
    """
    if order.status != "pending_payment" or not order.stripe_session_id:
        return "skipped"
    session = retrieve_session(order.stripe_session_id)
    if session["status"] == "complete" and session["payment_status"] == "paid":
        _mark_paid(db, order, session)
        db.commit()
        return order.status  # paid, or payment_review on mismatch
    if session["status"] == "open":
        expire_session(order.stripe_session_id)
    order.status = "cancelled"
    release_stock(db, order)
    db.commit()
    return "cancelled"


def release_stock(db: Session, order: Order) -> None:
    for item in order.items:
        db.execute(
            update(Product).where(Product.id == item.product_id)
            .values(stock=Product.stock + item.quantity)
        )


def verify_event(payload: bytes, signature: str | None) -> dict:
    if not settings.stripe_webhook_secret:
        raise ShopError("Webhooks are not configured", 503)
    try:
        stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
    except (stripe.SignatureVerificationError, ValueError) as exc:
        raise ShopError("Invalid webhook signature", 400) from exc
    return json.loads(payload)


def _order_for_session(db: Session, session: dict) -> Order | None:
    order_id = session.get("client_reference_id") or (session.get("metadata") or {}).get("order_id")
    order = db.get(Order, order_id) if order_id else None
    if order is None and session.get("id"):
        order = db.scalar(select(Order).where(Order.stripe_session_id == session["id"]))
    return order


def _mark_paid(db: Session, order: Order, session: dict) -> None:
    if order.status == "cancelled":
        # Money arrived for an order already cancelled (stock released):
        # never ship or ignore it silently — a human must review / refund.
        order.status = "payment_review"
        return
    if order.status != "pending_payment":
        return
    amount_ok = session.get("amount_total") == order.total
    currency_ok = (session.get("currency") or "").lower() == CURRENCY
    if amount_ok and currency_ok:
        order.status = "paid"
        order.paid_at = datetime.now(timezone.utc)
        analytics.record(db, "purchase", commit=False)
    else:
        # Never ship on a mismatched amount; a human must review.
        order.status = "payment_review"


def handle_event(db: Session, event: dict) -> str:
    """Apply a verified event. Returns a short outcome string."""
    event_id, event_type = event.get("id"), event.get("type", "")
    if not event_id:
        raise ShopError("Event has no id")
    if db.get(StripeEvent, event_id) is not None:
        return "duplicate"

    session = (event.get("data") or {}).get("object") or {}
    order = _order_for_session(db, session) if event_type.startswith("checkout.session.") else None
    outcome = "ignored"

    try:
        if order is not None:
            if event_type == "checkout.session.completed":
                if session.get("payment_status") == "paid":
                    _mark_paid(db, order, session)
                outcome = order.status
            elif event_type == "checkout.session.async_payment_succeeded":
                _mark_paid(db, order, session)
                outcome = order.status
            elif event_type in ("checkout.session.expired", "checkout.session.async_payment_failed"):
                if order.status == "pending_payment":
                    order.status = "cancelled"
                    release_stock(db, order)
                outcome = order.status
        db.add(StripeEvent(id=event_id, type=event_type))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return outcome
