"""Email: transactional messages, marketing flows (Blueprint section I), consent.

Rules (UK PECR / UK GDPR, blueprint "no pre-ticked boxes"):
- Transactional mail (order confirmation, shipped, setup help) always goes: it is
  part of the purchase.
- Marketing mail goes ONLY to people who ticked an unticked box, within what they
  agreed to: waitlist sign-ups agreed to ONE launch email and nothing else.
- Every marketing email carries the sender's identity and a one-click
  unsubscribe; unsubscribing cancels anything still queued.
- In "outbox" mode nothing leaves the server: messages are stored for review.
"""

import hashlib
import hmac
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage as MimeMessage

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..models import EmailMessage, MarketingConsent, Order

MARKETING_CONSENT_TEXT = ("Email me tips for small spaces and occasional offers from NOVAHAUS. "
                          "I can unsubscribe at any time.")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt):
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def _gbp(p: int) -> str:
    return f"£{p / 100:,.2f}"


def _key() -> bytes:
    # Set SECRET_KEY in production. If it is missing there, fall back to a key
    # derived from the (secret) database URL so links can never be forged with
    # a public default. The fixed dev key only applies to local runs.
    if settings.secret_key:
        return settings.secret_key.encode()
    if settings.is_production:
        return hashlib.sha256(("novahaus-links:" + settings.database_url).encode()).digest()
    return b"dev-only-not-secret"


def sign(value: str) -> str:
    return hmac.new(_key(), value.encode(), hashlib.sha256).hexdigest()[:32]


def verify(value: str, token: str) -> bool:
    return hmac.compare_digest(sign(value), token or "")


# ---------------------------------------------------------------- consent

def record_consent(db: Session, email: str, source: str, scope: str, text: str) -> MarketingConsent:
    """Record a positive opt-in. Never downgrades marketing to launch-only."""
    email = email.strip().lower()
    c = db.get(MarketingConsent, email)
    if c is None:
        c = MarketingConsent(email=email, consented=True, source=source, scope=scope, consent_text=text,
                             unsubscribe_token=secrets.token_urlsafe(24), updated_at=_now())
        db.add(c)
    else:
        c.consented = True
        if scope == "marketing" or c.scope != "marketing":
            c.scope, c.source, c.consent_text = scope, source, text
        c.updated_at = _now()
    return c


def may_market(db: Session, email: str, flow: str) -> bool:
    c = db.get(MarketingConsent, email.strip().lower())
    if c is None or not c.consented:
        return False
    return c.scope == "marketing" or flow == "launch"


def unsubscribe(db: Session, token: str) -> str | None:
    c = db.scalar(select(MarketingConsent).where(MarketingConsent.unsubscribe_token == token))
    if c is None:
        return None
    c.consented = False
    c.updated_at = _now()
    db.execute(update(EmailMessage).where(EmailMessage.to_email == c.email, EmailMessage.kind == "marketing",
                                          EmailMessage.status == "queued").values(status="cancelled"))
    db.commit()
    return c.email


# ---------------------------------------------------------------- templates

def _footer_marketing(email: str, db: Session) -> str:
    c = db.get(MarketingConsent, email)
    token = c.unsubscribe_token if c else ""
    addr = f", {settings.shop_address}" if settings.shop_address else ""
    return (f"\n\n--\n{settings.shop_legal_name}{addr}\n"
            f"You're getting this because you asked for it. Unsubscribe with one click: "
            f"{settings.public_base_url}/unsubscribe?token={token}\n")


def _footer_transactional() -> str:
    addr = f", {settings.shop_address}" if settings.shop_address else ""
    return f"\n\n--\n{settings.shop_legal_name}{addr}\nQuestions? Just reply to this email.\n"


def _lines(order: Order) -> str:
    rows = [f"  {i.name} x {i.quantity}: {_gbp(i.unit_price * i.quantity)}" for i in order.items]
    rows.append(f"  Delivery: {'Free' if order.shipping == 0 else _gbp(order.shipping)}")
    rows.append(f"  Total (inc. VAT): {_gbp(order.total)}")
    return "\n".join(rows)


def review_link(order: Order) -> str:
    return f"{settings.public_base_url}/review/{order.id}?token={sign('review:' + order.id)}"


def render(flow: str, step: int, ctx: dict) -> tuple[str, str]:
    """(subject, body) for each flow step. Plain text: readable everywhere."""
    o = ctx.get("order")
    name = (o.customer_name.split(" ")[0] if o else "") or "there"
    shop = settings.public_base_url
    T = {
        ("order", 1): (f"Your NOVAHAUS order {o.id[:8] if o else ''}",
                       f"Hi {name},\n\nThanks for your order. Here's what you bought:\n\n{_lines(o) if o else ''}\n\n"
                       f"Delivering to: {o.shipping_address if o else ''}\n\nTrack it any time: {shop}/track "
                       f"(order number {o.id if o else ''}).\n\nYou can cancel within 14 days of delivery; "
                       f"see {shop}/returns."),
        ("order", 2): ("Your NOVAHAUS order is on its way",
                       f"Hi {name},\n\nGood news: your order has been sent."
                       + (f"\nTracking: {ctx.get('tracking')}" if ctx.get("tracking") else "")
                       + f"\n\nOrder details: {shop}/track"),
        ("post_purchase", 3): ("Setting up your new desk pieces",
                               f"Hi {name},\n\nA few tips to get the most from your order:\n"
                               "- Clean the desk surface before placing the mat, so it lies flat.\n"
                               "- For the cable tray, check your desk thickness against the fit guide first.\n"
                               "- Route the longest cable first, then clip the rest.\n\n"
                               f"Something not right? Reply to this email or see {shop}/returns."),
        ("post_purchase", 4): ("How is your setup working out?",
                               f"Hi {name},\n\nIf you have a minute, we'd love an honest review: "
                               f"{review_link(o) if o else shop}\n\nGood or bad, it helps other people "
                               "and helps us improve. We publish reviews from verified buyers only."),
        ("post_purchase", 5): ("Completing your desk setup",
                               f"Hi {name},\n\nIf you'd like to finish the look, the Desk Reset set "
                               f"(mat, cable tray and clips) is here: {shop}/products/desk-reset\n\n"
                               "No pressure, and thanks again for your order."),
        ("abandoned", 1): ("You left something at checkout",
                           f"Hi {name},\n\nYour checkout wasn't finished, so we haven't taken any payment. "
                           f"Your items are still available: {shop}/shop"),
        ("abandoned", 2): ("Any questions before you order?",
                           f"Hi {name},\n\nIf something held you back (sizing, delivery, returns), "
                           f"the answers are here: {shop}/faq. Or just reply to this email."),
        ("abandoned", 3): ("Free delivery and easy returns",
                           f"Hi {name},\n\nA reminder: UK delivery is free over £50, and you can cancel "
                           f"within 14 days of delivery. {shop}/shop"),
        ("abandoned", 4): ("Last note from us",
                           f"Hi {name},\n\nThis is our last reminder about your unfinished checkout. "
                           f"If you change your mind, the shop is here: {shop}/shop"),
        ("welcome", 1): ("Welcome to NOVAHAUS",
                         "Hi,\n\nThanks for joining. We make calm, well-made organisation pieces for small UK "
                         f"homes, in honest materials, with exact dimensions. Have a look: {shop}"),
        ("welcome", 2): ("Three fixes for a messy desk",
                         "Hi,\n\n1. Get cables off the floor and under the desk.\n2. Give the desk a calm base "
                         "(a mat hides scratches).\n3. Raise the screen to eye level.\n\n"
                         f"The Desk Reset pieces do exactly this: {shop}/shop"),
        ("welcome", 3): ("Why we name every material",
                         "Hi,\n\nFelt, walnut, oak and steel: we say exactly what things are made of, and we "
                         f"publish measured dimensions. No mystery plastics. {shop}/about"),
        ("welcome", 4): ("The Desk Reset set",
                         f"Hi,\n\nMat, cable tray and clips together cost less than separately: "
                         f"{shop}/products/desk-reset"),
        ("welcome", 5): ("Questions? Just reply",
                         f"Hi,\n\nIf you're unsure about sizes or delivery, reply to this email and a person "
                         f"will answer. Our FAQ: {shop}/faq"),
        ("winback", 1): ("It's been a while",
                         f"Hi {name},\n\nThanks for being a customer. If your setup needs a refresh, "
                         f"here's what's new: {shop}/shop"),
        ("launch", 1): ("NOVAHAUS is open",
                        f"Hi,\n\nYou asked us to tell you when NOVAHAUS opens. It's open now: {shop}\n\n"
                        "This is the one email you signed up for."),
    }
    return T[(flow, step)]


# (flow, step) -> (kind, delay after trigger)
FLOWS = {
    ("order", 1): ("transactional", timedelta(0)),
    ("order", 2): ("transactional", timedelta(0)),
    ("post_purchase", 3): ("transactional", timedelta(days=3)),
    ("post_purchase", 4): ("marketing", timedelta(days=10)),
    ("post_purchase", 5): ("marketing", timedelta(days=21)),
    ("abandoned", 1): ("marketing", timedelta(hours=1)),
    ("abandoned", 2): ("marketing", timedelta(days=1)),
    ("abandoned", 3): ("marketing", timedelta(days=3)),
    ("abandoned", 4): ("marketing", timedelta(days=7)),
    ("welcome", 1): ("marketing", timedelta(0)),
    ("welcome", 2): ("marketing", timedelta(days=2)),
    ("welcome", 3): ("marketing", timedelta(days=4)),
    ("welcome", 4): ("marketing", timedelta(days=7)),
    ("welcome", 5): ("marketing", timedelta(days=10)),
    ("winback", 1): ("marketing", timedelta(0)),
    ("launch", 1): ("marketing", timedelta(0)),
}


def queue(db: Session, to: str, flow: str, step: int, dedupe: str, ctx: dict | None = None,
          start: datetime | None = None) -> EmailMessage | None:
    """Queue one message; idempotent through dedupe_key. Marketing needs consent now
    AND is re-checked at send time."""
    to = to.strip().lower()
    kind, delay = FLOWS[(flow, step)]
    if kind == "marketing" and not may_market(db, to, flow):
        return None
    subject, body = render(flow, step, ctx or {})
    msg = EmailMessage(to_email=to, subject=subject, body=body, kind=kind, flow=flow, step=step,
                       dedupe_key=dedupe, send_after=(start or _now()) + delay, created_at=_now())
    try:
        with db.begin_nested():
            db.add(msg)
    except IntegrityError:
        return None  # already queued earlier
    return msg


# ---------------------------------------------------------------- triggers

def on_order_paid(db: Session, order: Order, marketing_ok: bool = False) -> None:
    queue(db, order.customer_email, "order", 1, f"order1:{order.id}", {"order": order})
    queue(db, order.customer_email, "post_purchase", 3, f"pp3:{order.id}", {"order": order})
    if marketing_ok or may_market(db, order.customer_email, "post_purchase"):
        for step in (4, 5):
            queue(db, order.customer_email, "post_purchase", step, f"pp{step}:{order.id}", {"order": order})


def on_order_shipped(db: Session, order: Order, tracking: str = "") -> None:
    queue(db, order.customer_email, "order", 2, f"order2:{order.id}", {"order": order, "tracking": tracking})


def on_checkout_abandoned(db: Session, order: Order) -> None:
    # One reminder series per person at a time, however many checkouts they abandon.
    active = db.scalar(select(func.count()).select_from(EmailMessage).where(
        EmailMessage.to_email == order.customer_email.strip().lower(),
        EmailMessage.flow == "abandoned", EmailMessage.status == "queued"))
    if active:
        return
    for step in (1, 2, 3, 4):
        queue(db, order.customer_email, "abandoned", step, f"ab{step}:{order.id}", {"order": order},
              start=_aware(order.created_at))


def on_newsletter_signup(db: Session, email: str) -> None:
    for step in (1, 2, 3, 4, 5):
        queue(db, email, "welcome", step, f"welcome{step}:{email.strip().lower()}")


def queue_launch_emails(db: Session) -> int:
    n = 0
    for c in db.scalars(select(MarketingConsent).where(MarketingConsent.consented.is_(True))):
        if queue(db, c.email, "launch", 1, f"launch:{c.email}"):
            n += 1
    db.commit()
    return n


def queue_winbacks(db: Session, days: int = 90) -> int:
    """Customers whose most recent order is `days` old and who agreed to marketing."""
    cutoff = _now() - timedelta(days=days)
    last = dict(db.execute(select(Order.customer_email, func.max(Order.created_at))
                           .where(Order.status.in_(("placed", "paid", "shipped")))
                           .group_by(Order.customer_email)).all())
    n = 0
    for email, when in last.items():
        if _aware(when) <= cutoff and queue(db, email, "winback", 1, f"winback:{email}:{_aware(when):%Y%m%d}"):
            n += 1
    db.commit()
    return n


# ---------------------------------------------------------------- sending

def _still_wanted(db: Session, msg: EmailMessage) -> tuple[bool, str]:
    if msg.kind == "marketing" and not may_market(db, msg.to_email, msg.flow):
        return False, "no marketing consent (or unsubscribed)"
    if msg.flow == "abandoned":
        order_id = msg.dedupe_key.split(":", 1)[1]
        abandoned = db.get(Order, order_id)
        bought = db.scalar(select(func.count()).select_from(Order).where(
            Order.customer_email == msg.to_email, Order.status.in_(("placed", "paid", "shipped")),
            Order.created_at >= (abandoned.created_at if abandoned else _now())))
        if bought:
            return False, "customer completed an order since"
    return True, ""


def _smtp_send(msg: EmailMessage) -> None:
    m = MimeMessage()
    m["From"], m["To"], m["Subject"] = settings.email_from, msg.to_email, msg.subject
    if msg.kind == "marketing":
        c_token = msg.body.rsplit("token=", 1)[-1].strip() if "token=" in msg.body else ""
        if c_token:
            m["List-Unsubscribe"] = f"<{settings.public_base_url}/unsubscribe?token={c_token}>"
    m.set_content(msg.body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
        s.starttls()
        if settings.smtp_user:
            s.login(settings.smtp_user, settings.smtp_password)
        s.send_message(m)


def send_due(db: Session, limit: int = 50) -> str:
    now = _now()
    due = db.scalars(select(EmailMessage).where(EmailMessage.status == "queued", EmailMessage.send_after <= now)
                     .order_by(EmailMessage.send_after).limit(limit)).all()
    counts: dict[str, int] = {}
    for msg in due:
        ok, why = _still_wanted(db, msg)
        if not ok:
            msg.status, msg.error = "skipped", why
        else:
            if msg.kind == "marketing" and "Unsubscribe" not in msg.body:
                msg.body += _footer_marketing(msg.to_email, db)
            elif msg.kind == "transactional" and "Questions? Just reply" not in msg.body:
                msg.body += _footer_transactional()
            if settings.email_mode == "smtp" and settings.smtp_host:
                try:
                    msg.attempts += 1
                    _smtp_send(msg)
                    msg.status, msg.sent_at = "sent", _now()
                except Exception as exc:  # retried next run, up to 5 attempts
                    msg.error = f"{type(exc).__name__}: {exc}"
                    if msg.attempts >= 5:
                        msg.status = "failed"
            else:
                msg.status, msg.sent_at = "outbox", _now()
        counts[msg.status] = counts.get(msg.status, 0) + 1
        db.commit()
    return f"emails: {counts or 'nothing due'}"
