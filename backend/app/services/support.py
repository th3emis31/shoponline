"""Customer support inbox (Blueprint section O): contact form, reply templates,
1-business-day reply target. Every reply is emailed and kept with the ticket."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Order, SupportReply, SupportTicket
from . import emails
from .shop import ShopError

TOPICS = {"order": "My order", "return": "Returns and refunds", "product": "A product question", "other": "Something else"}

# Starting points only: always read the message and edit before sending.
TEMPLATES = {
    "where_is_order": ("Where is my order",
                       "Hi {name},\n\nThanks for your message. Your order {order} is {status}. "
                       "You can check it any time at {shop}/track with your order number and email.\n\n"
                       "If it hasn't arrived by the end of the delivery window, reply here and we'll sort it out.\n\n"
                       "Best wishes,\nNOVAHAUS"),
    "return_how": ("How to return",
                   "Hi {name},\n\nOf course. You can cancel within 14 days of delivery and send the item back "
                   "within 14 days after that. Full steps are here: {shop}/returns\n\n"
                   "Once it's back with us we refund within 14 days, to the card you paid with.\n\n"
                   "Best wishes,\nNOVAHAUS"),
    "damaged": ("Damaged or faulty item",
                "Hi {name},\n\nI'm sorry it arrived like that. Could you reply with a photo of the item and "
                "the packaging? We'll then send a replacement or a full refund, whichever you prefer. "
                "You won't need to pay for any return.\n\nBest wishes,\nNOVAHAUS"),
    "product_question": ("Product question",
                         "Hi {name},\n\nThanks for asking. [Answer here, using measured specs only.]\n\n"
                         "Best wishes,\nNOVAHAUS"),
    "delay": ("Delivery is taking longer",
              "Hi {name},\n\nThank you for your patience. Your order {order} ships directly from our supplier, "
              "and it's taking longer than we'd like. [Give the honest new estimate.] If you'd rather not wait, "
              "reply and we'll cancel and refund it in full.\n\nBest wishes,\nNOVAHAUS"),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def due_after(created: datetime) -> datetime:
    """One business day: Friday's message is due Monday; weekend messages are due Tuesday morning at most."""
    due = created + timedelta(days=1)
    while due.weekday() >= 5:  # Saturday, Sunday
        due += timedelta(days=1)
    return due


def create(db: Session, name: str, email: str, topic: str, message: str, order_id: str | None) -> SupportTicket:
    if topic not in TOPICS:
        raise ShopError("Please pick a topic.")
    order_id = (order_id or "").strip() or None
    now = _now()
    t = SupportTicket(name=name.strip(), email=email.strip().lower(), topic=topic, message=message.strip(),
                      order_id=order_id, created_at=now, due_at=due_after(now))
    db.add(t)
    db.flush()
    emails.queue(db, t.email, "support", 1, f"support1:{t.id}", {"ticket": t})
    return t


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def template_text(db: Session, key: str, ticket: SupportTicket) -> str:
    from ..config import settings
    if key not in TEMPLATES:
        raise ShopError("Unknown template", 404)
    order = db.get(Order, ticket.order_id) if ticket.order_id else None
    # Only use the order when it belongs to the same email (no leaking other people's orders).
    if order is not None and order.customer_email.lower() != ticket.email:
        order = None
    first = (ticket.name.split(" ")[0] if ticket.name.strip() else "") or "there"
    return TEMPLATES[key][1].format(name=first, order=order.id[:8] if order else "(order number)",
                                    status=order.status if order else "(status)", shop=settings.public_base_url)


def reply(db: Session, ticket_id: int, body: str, by: str | None, close: bool = False) -> SupportReply:
    t = db.get(SupportTicket, ticket_id)
    if t is None:
        raise ShopError("Message not found", 404)
    body = body.strip()
    if not body:
        raise ShopError("Write a reply first.")
    r = SupportReply(ticket_id=t.id, body=body, by=by, created_at=_now())
    db.add(r)
    db.flush()
    emails.queue(db, t.email, "support", 2, f"support2:{r.id}", {"ticket": t, "reply": body})
    t.first_reply_at = t.first_reply_at or r.created_at
    t.status = "closed" if close else "replied"
    return r


def set_status(db: Session, ticket_id: int, status: str) -> SupportTicket:
    t = db.get(SupportTicket, ticket_id)
    if t is None:
        raise ShopError("Message not found", 404)
    if status not in ("open", "closed"):
        raise ShopError("Unknown status")
    t.status = status
    return t


def overdue(t: SupportTicket, now: datetime | None = None) -> bool:
    return t.status == "open" and t.first_reply_at is None and _aware(t.due_at) < (now or _now())


def inbox(db: Session, status: str | None = None, limit: int = 200) -> dict:
    q = select(SupportTicket).order_by(SupportTicket.status != "open", SupportTicket.due_at).limit(min(max(limit, 1), 500))
    if status:
        q = q.where(SupportTicket.status == status)
    now = _now()
    tickets = list(db.scalars(q))
    answered = [t for t in db.scalars(select(SupportTicket).where(SupportTicket.first_reply_at.is_not(None))
                                      .order_by(SupportTicket.id.desc()).limit(200))]
    on_time = sum(1 for t in answered if _aware(t.first_reply_at) <= _aware(t.due_at))
    open_count = db.scalar(select(func.count()).select_from(SupportTicket).where(SupportTicket.status == "open")) or 0
    return {
        "open": open_count,
        "overdue": sum(1 for t in tickets if overdue(t, now)),
        "on_time_rate": round(on_time / len(answered), 3) if answered else None,
        "topics": TOPICS,
        "templates": {k: v[0] for k, v in TEMPLATES.items()},
        "tickets": [{
            "id": t.id, "name": t.name, "email": t.email, "order_id": t.order_id, "topic": t.topic,
            "message": t.message, "status": t.status, "due_at": t.due_at, "overdue": overdue(t, now),
            "created_at": t.created_at, "first_reply_at": t.first_reply_at,
            "replies": [{"id": r.id, "body": r.body, "by": r.by, "created_at": r.created_at} for r in t.replies],
        } for t in tickets],
    }


def overdue_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(SupportTicket).where(
        SupportTicket.status == "open", SupportTicket.first_reply_at.is_(None), SupportTicket.due_at < _now())) or 0
