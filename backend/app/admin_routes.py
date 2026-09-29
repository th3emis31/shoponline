import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_session
from .ratelimit import limit
from .security import require_admin, require_owner
from .models import DailyReport, PurchaseOrder, Recommendation, SupplierOrder, WaitlistSignup
from .services import admin, analytics, auth, automation, shop
from .services.auth import Principal

# Sign-in endpoints are public; everything else needs a signed-in admin.
public = APIRouter(prefix="/api/admin")
router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


@public.post("/login", dependencies=[Depends(limit("login", 20, 600))])
def login(body: LoginIn, db: Session = Depends(get_session)):
    try:
        token, user, expires = auth.login(db, body.email, body.password)
    except auth.AuthError as exc:
        raise HTTPException(401, str(exc)) from exc
    admin.audit(db, "admin.login", user.email, actor=user.email)
    db.commit()
    return {"token": token, "email": user.email, "role": user.role, "expires_at": expires}


@public.post("/logout", status_code=204)
def logout(x_admin_token: str = Header(default=""), db: Session = Depends(get_session)):
    if x_admin_token:
        auth.logout(db, x_admin_token)


class StatusIn(BaseModel):
    status: str = Field(min_length=1, max_length=20)
    note: str = Field(default="", max_length=500)


class ProductPatch(BaseModel):
    price: int | None = Field(default=None, ge=1, le=10_000_00)
    stock: int | None = Field(default=None, ge=0, le=100_000)
    active: bool | None = None
    landed_cost: int | None = Field(default=None, ge=0, le=10_000_00)
    shipping_cost: int | None = Field(default=None, ge=0, le=10_000_00)
    packaging_cost: int | None = Field(default=None, ge=0, le=10_000_00)
    fulfilment: Literal["stock", "dropship"] | None = None
    supplier_name: str | None = Field(default=None, max_length=200)
    supplier_url: str | None = Field(default=None, max_length=1000)
    supplier_cost: int | None = Field(default=None, ge=0, le=10_000_00)
    delivery_estimate: str | None = Field(default=None, max_length=100)
    note: str = Field(default="", max_length=500)

    @field_validator("supplier_url")
    @classmethod
    def http_only(cls, v: str | None) -> str | None:
        # Only real web links (never javascript: etc.), since admins click them.
        if v and not v.lower().startswith(("https://", "http://")):
            raise ValueError("Supplier link must start with https://")
        return v.strip() if v else v


def next_for(o, role: str) -> list[str]:
    options = admin.TRANSITIONS.get(o.status, set())
    if role != "owner":
        options = {s for s in options if (o.status, s) in admin.STAFF_TRANSITIONS}
    return sorted(options)


def admin_order(o, role: str = "owner") -> dict:
    return {**shop.order_view(o), "customer_name": o.customer_name, "customer_email": o.customer_email,
            "shipping_address": o.shipping_address, "paid_at": o.paid_at,
            "next_statuses": next_for(o, role)}


@router.get("/me")
def me(principal: Principal = Depends(require_admin)):
    return {"actor": principal.actor, "role": principal.role}


@router.get("/orders")
def orders(status: str | None = None, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_session),
           principal: Principal = Depends(require_admin)):
    return [admin_order(o, principal.role) for o in admin.list_orders(db, status, limit)]


@router.get("/orders/{order_id}")
def order(order_id: str, db: Session = Depends(get_session), principal: Principal = Depends(require_admin)):
    o = db.get(admin.Order, order_id)
    if o is None:
        raise shop.ShopError("Order not found", 404)
    return admin_order(o, principal.role)


@router.post("/orders/{order_id}/status")
def order_status(order_id: str, body: StatusIn, db: Session = Depends(get_session),
                 principal: Principal = Depends(require_admin)):
    return admin_order(admin.set_order_status(db, order_id, body.status, body.note,
                                              actor=principal.actor, role=principal.role), principal.role)


@router.get("/products", dependencies=[Depends(require_owner)])
def products(db: Session = Depends(get_session)):
    return admin.list_products(db)


@router.patch("/products/{product_id}")
def update_product(product_id: str, body: ProductPatch, db: Session = Depends(get_session),
                   principal: Principal = Depends(require_owner)):
    data = body.model_dump(exclude={"note"})
    return admin.update_product(db, product_id, data, body.note, actor=principal.actor)


@router.get("/funnel", dependencies=[Depends(require_owner)])
def funnel(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_session)):
    return analytics.funnel(db, days)


@router.get("/audit", dependencies=[Depends(require_owner)])
def audit(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_session)):
    return [{"id": a.id, "action": a.action, "target": a.target, "actor": a.actor, "detail": json.loads(a.detail),
             "created_at": a.created_at} for a in admin.audit_log(db, limit)]


# ---------------------------------------------------------------- automation (owner only)

class DecisionIn(BaseModel):
    note: str = Field(default="", max_length=500)


class POStatusIn(BaseModel):
    status: str = Field(min_length=1, max_length=16)


def rec_out(r: Recommendation) -> dict:
    return {"id": r.id, "kind": r.kind, "target": r.target, "payload": json.loads(r.payload),
            "reason": r.reason, "impact": r.impact, "status": r.status, "auto": r.auto,
            "decision_note": r.decision_note, "decided_by": r.decided_by, "decided_at": r.decided_at,
            "result": r.result, "created_at": r.created_at}


@router.get("/automation", dependencies=[Depends(require_owner)])
def automation_status(db: Session = Depends(get_session)):
    return automation.status(db)


@router.post("/automation/run/{job}", dependencies=[Depends(require_owner)])
def automation_run(job: str, db: Session = Depends(get_session)):
    if job not in automation.JOBS:
        raise HTTPException(404, "Unknown job")
    run = automation.run_job(db, job)
    return {"job": run.job, "status": run.status, "message": run.message}


@router.get("/recommendations", dependencies=[Depends(require_owner)])
def recommendations(status: str | None = None, limit: int = Query(100, ge=1, le=500),
                    db: Session = Depends(get_session)):
    q = select(Recommendation).order_by(Recommendation.id.desc()).limit(limit)
    if status:
        q = q.where(Recommendation.status == status)
    return [rec_out(r) for r in db.scalars(q)]


@router.post("/recommendations/{rec_id}/approve")
def approve(rec_id: int, body: DecisionIn, db: Session = Depends(get_session),
            principal: Principal = Depends(require_owner)):
    return rec_out(automation.decide(db, rec_id, True, principal.actor, body.note))


@router.post("/recommendations/{rec_id}/reject")
def reject(rec_id: int, body: DecisionIn, db: Session = Depends(get_session),
           principal: Principal = Depends(require_owner)):
    return rec_out(automation.decide(db, rec_id, False, principal.actor, body.note))


def po_out(po: PurchaseOrder) -> dict:
    return {"id": po.id, "product_id": po.product_id, "quantity": po.quantity, "unit_cost": po.unit_cost,
            "total": po.total, "status": po.status, "recommendation_id": po.recommendation_id,
            "created_at": po.created_at, "updated_at": po.updated_at,
            "next_statuses": sorted(automation.PO_TRANSITIONS.get(po.status, set()))}


@router.get("/purchase-orders", dependencies=[Depends(require_owner)])
def purchase_orders(db: Session = Depends(get_session)):
    return [po_out(po) for po in db.scalars(select(PurchaseOrder).order_by(PurchaseOrder.id.desc()).limit(200))]


@router.post("/purchase-orders/{po_id}/status")
def purchase_order_status(po_id: int, body: POStatusIn, db: Session = Depends(get_session),
                          principal: Principal = Depends(require_owner)):
    return po_out(automation.set_po_status(db, po_id, body.status, principal.actor))


@router.get("/reports/latest", dependencies=[Depends(require_owner)])
def latest_report(db: Session = Depends(get_session)):
    rep = db.scalar(select(DailyReport).order_by(DailyReport.day.desc()).limit(1))
    return {"day": rep.day, "content": rep.content} if rep else {"day": None, "content": None}


@router.get("/waitlist", dependencies=[Depends(require_owner)])
def waitlist(db: Session = Depends(get_session)):
    """Smoke-test results: sign-ups per product (the blueprint's product-validation gate)."""
    from sqlalchemy import func
    rows = db.execute(select(WaitlistSignup.product_id, func.count()).group_by(WaitlistSignup.product_id)).all()
    recent = db.scalars(select(WaitlistSignup).order_by(WaitlistSignup.id.desc()).limit(200)).all()
    return {
        "total": sum(n for _, n in rows),
        "by_product": [{"product_id": pid or "(whole shop)", "count": n} for pid, n in sorted(rows, key=lambda r: -r[1])],
        "recent": [{"email": w.email, "product_id": w.product_id, "created_at": w.created_at} for w in recent],
    }


# ---------------------------------------------------------------- dropship supplier orders (owner only)

SUPPLIER_TRANSITIONS = {
    "to_order": {"ordered", "problem"},
    "ordered": {"shipped", "problem"},
    "shipped": {"delivered", "problem"},
    "problem": {"to_order", "ordered", "shipped", "delivered"},
    "delivered": set(),
}


class SupplierOrderIn(BaseModel):
    status: str | None = Field(default=None, max_length=16)
    supplier_ref: str | None = Field(default=None, max_length=200)
    tracking: str | None = Field(default=None, max_length=300)
    note: str | None = Field(default=None, max_length=1000)


def supplier_out(so: SupplierOrder) -> dict:
    from .services import unit_economics
    # Profit ESTIMATE: sale ex VAT, minus supplier price, minus the Stripe fee on this line.
    fee = float(unit_economics.STRIPE_UK_PERCENT) * so.sale_total
    profit = round(so.sale_total / (1 + float(unit_economics.VAT_RATE)) - so.supplier_cost_total - fee)
    return {"id": so.id, "order_id": so.order_id, "product_id": so.product_id, "quantity": so.quantity,
            "supplier_name": so.supplier_name, "supplier_url": so.supplier_url,
            "supplier_cost_total": so.supplier_cost_total, "sale_total": so.sale_total,
            "profit_estimate": profit, "status": so.status, "supplier_ref": so.supplier_ref,
            "tracking": so.tracking, "note": so.note, "created_at": so.created_at,
            "next_statuses": sorted(SUPPLIER_TRANSITIONS.get(so.status, set()))}


@router.get("/supplier-orders", dependencies=[Depends(require_owner)])
def supplier_orders(status: str | None = None, db: Session = Depends(get_session)):
    q = select(SupplierOrder).order_by(SupplierOrder.id.desc()).limit(300)
    if status:
        q = q.where(SupplierOrder.status == status)
    rows = []
    for so in db.scalars(q):
        order = db.get(admin.Order, so.order_id)
        rows.append({**supplier_out(so),
                     # Needed to place the order with the supplier (ship straight to the customer).
                     "ship_to_name": order.customer_name if order else "",
                     "ship_to_address": order.shipping_address if order else ""})
    return rows


@router.post("/supplier-orders/{so_id}")
def update_supplier_order(so_id: int, body: SupplierOrderIn, db: Session = Depends(get_session),
                          principal: Principal = Depends(require_owner)):
    from sqlalchemy import update
    from datetime import datetime, timezone
    so = db.get(SupplierOrder, so_id)
    if so is None:
        raise shop.ShopError("Supplier order not found", 404)
    old = so.status
    values = {k: v for k, v in body.model_dump(exclude={"status"}).items() if v is not None}
    if body.status and body.status != old:
        if body.status not in SUPPLIER_TRANSITIONS.get(old, set()):
            raise shop.ShopError(f"Cannot change {old} to {body.status}", 409)
        values["status"] = body.status
    if not values:
        raise shop.ShopError("No changes given")
    values["updated_at"] = datetime.now(timezone.utc)
    moved = db.execute(update(SupplierOrder).where(SupplierOrder.id == so_id, SupplierOrder.status == old)
                       .values(**values).execution_options(synchronize_session="fetch")).rowcount == 1
    if not moved:
        db.rollback()
        raise shop.ShopError("This supplier order changed meanwhile. Reload and try again.", 409)
    admin.audit(db, "supplier_order.update", str(so_id), actor=principal.actor, old=old,
                **{k: v for k, v in values.items() if k != "updated_at"})
    db.commit()
    db.refresh(so)
    return supplier_out(so)


# ---------------------------------------------------------------- team (owner only)

class NewUserIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)
    role: Literal["owner", "staff"] = "staff"


class ActiveIn(BaseModel):
    active: bool


class PasswordIn(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


def _user_out(u) -> dict:
    return {"email": u.email, "role": u.role, "active": u.active, "created_at": u.created_at}


@router.get("/users", dependencies=[Depends(require_owner)])
def users(db: Session = Depends(get_session)):
    from .models import AdminUser
    return [_user_out(u) for u in db.scalars(select(AdminUser).order_by(AdminUser.email))]


@router.post("/users", status_code=201)
def create_user(body: NewUserIn, db: Session = Depends(get_session), principal: Principal = Depends(require_owner)):
    try:
        u = auth.create_user(db, body.email, body.password, body.role)
    except auth.AuthError as exc:
        raise HTTPException(400, str(exc)) from exc
    admin.audit(db, "admin_user.create", u.email, actor=principal.actor, role=u.role)
    db.commit()
    return _user_out(u)


@router.post("/users/{email}/active")
def set_user_active(email: str, body: ActiveIn, db: Session = Depends(get_session),
                    principal: Principal = Depends(require_owner)):
    from .models import AdminUser
    target = auth.normalise_email(email)
    if not body.active:
        if target == principal.actor:
            raise HTTPException(400, "You can't disable your own login.")
        user = db.scalar(select(AdminUser).where(AdminUser.email == target))
        if user and user.role == "owner":
            from sqlalchemy import func
            owners = db.scalar(select(func.count()).select_from(AdminUser).where(
                AdminUser.role == "owner", AdminUser.active.is_(True)))
            if owners <= 1:
                raise HTTPException(400, "This is the last active owner; add another owner first.")
    try:
        auth.set_active(db, target, body.active)
    except auth.AuthError as exc:
        raise HTTPException(404, str(exc)) from exc
    admin.audit(db, "admin_user.active", target, actor=principal.actor, active=body.active)
    db.commit()
    return {"email": target, "active": body.active}


@router.post("/users/{email}/password")
def reset_user_password(email: str, body: PasswordIn, db: Session = Depends(get_session),
                        principal: Principal = Depends(require_owner)):
    target = auth.normalise_email(email)
    try:
        auth.set_password(db, target, body.password)
    except auth.AuthError as exc:
        raise HTTPException(400, str(exc)) from exc
    admin.audit(db, "admin_user.password_reset", target, actor=principal.actor)
    db.commit()
    return {"email": target, "signed_out_everywhere": True}


# ---------------------------------------------------------------- emails (owner only)

@router.get("/emails", dependencies=[Depends(require_owner)])
def email_outbox(status: str | None = None, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_session)):
    from .config import settings
    from .models import EmailMessage, MarketingConsent
    from sqlalchemy import func
    q = select(EmailMessage).order_by(EmailMessage.id.desc()).limit(limit)
    if status:
        q = q.where(EmailMessage.status == status)
    consents = dict(db.execute(select(MarketingConsent.scope, func.count()).where(
        MarketingConsent.consented.is_(True)).group_by(MarketingConsent.scope)).all())
    return {
        "mode": settings.email_mode if settings.smtp_host or settings.email_mode == "outbox" else "outbox",
        "subscribers": {"marketing": consents.get("marketing", 0), "launch_only": consents.get("launch_only", 0)},
        "messages": [{"id": m.id, "to": m.to_email, "subject": m.subject, "body": m.body, "kind": m.kind,
                      "flow": m.flow, "step": m.step, "status": m.status, "error": m.error,
                      "send_after": m.send_after, "sent_at": m.sent_at} for m in db.scalars(q)],
    }


@router.post("/emails/launch")
def send_launch(db: Session = Depends(get_session), principal: Principal = Depends(require_owner)):
    from .services import emails
    n = emails.queue_launch_emails(db)
    admin.audit(db, "email.launch", "waitlist", actor=principal.actor, queued=n)
    db.commit()
    return {"queued": n}


# ---------------------------------------------------------------- reviews (owner and staff)

@router.get("/reviews")
def list_reviews(status: str | None = None, db: Session = Depends(get_session)):
    from .services import reviews
    from .models import Product
    names = dict(db.execute(select(Product.id, Product.name)).all())
    return {
        "reasons": reviews.REJECT_REASONS,
        "reviews": [{"id": r.id, "order_id": r.order_id, "product_id": r.product_id,
                     "product": names.get(r.product_id, r.product_id), "rating": r.rating, "title": r.title,
                     "body": r.body, "name": r.display_name, "status": r.status,
                     "reject_reason": r.reject_reason, "created_at": r.created_at}
                    for r in reviews.admin_list(db, status)],
    }


class ModerateIn(BaseModel):
    action: Literal["publish", "reject"]
    reason: str = Field(default="", max_length=40)


@router.post("/reviews/{review_id}")
def moderate_review(review_id: int, body: ModerateIn, db: Session = Depends(get_session),
                    principal: Principal = Depends(require_admin)):
    from .services import reviews
    r = reviews.moderate(db, review_id, body.action, body.reason)
    admin.audit(db, f"review.{body.action}", str(review_id), actor=principal.actor,
                rating=r.rating, reason=body.reason)
    db.commit()
    return {"id": r.id, "status": r.status}


# ---------------------------------------------------------------- campaigns (owner only)

@router.get("/campaigns", dependencies=[Depends(require_owner)])
def campaign_report(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_session)):
    from .services import campaigns
    return {**campaigns.report(db, days),
            "spend_rows": [{"id": r.id, "campaign": r.campaign, "day": r.day, "spend": r.spend, "clicks": r.clicks,
                            "impressions": r.impressions, "note": r.note, "created_by": r.created_by}
                           for r in campaigns.spend_rows(db)]}


class SpendIn(BaseModel):
    campaign: str = Field(min_length=3, max_length=130)
    day: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    spend: int = Field(ge=0, le=10_000_00)
    clicks: int = Field(default=0, ge=0, le=10_000_000)
    impressions: int = Field(default=0, ge=0, le=1_000_000_000)
    note: str = Field(default="", max_length=200)


@router.post("/campaigns/spend", status_code=201)
def add_spend(body: SpendIn, db: Session = Depends(get_session), principal: Principal = Depends(require_owner)):
    from datetime import datetime, timezone
    from .services import campaigns
    try:
        day = datetime.strptime(body.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        row = campaigns.add_spend(db, body.campaign, day, body.spend, body.clicks, body.impressions,
                                  body.note, principal.actor)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    admin.audit(db, "campaign.spend", row.campaign, actor=principal.actor, day=body.day, spend=body.spend)
    db.commit()
    return {"id": row.id, "campaign": row.campaign}


# ---------------------------------------------------------------- support inbox (owner and staff)

@router.get("/support")
def support_inbox(status: str | None = None, db: Session = Depends(get_session)):
    from .services import support
    return support.inbox(db, status)


@router.get("/support/{ticket_id}/template/{key}")
def support_template(ticket_id: int, key: str, db: Session = Depends(get_session)):
    from .models import SupportTicket
    from .services import support
    t = db.get(SupportTicket, ticket_id)
    if t is None:
        raise HTTPException(404, "Message not found")
    return {"text": support.template_text(db, key, t)}


class SupportReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)
    close: bool = False


@router.post("/support/{ticket_id}/reply", status_code=201)
def support_reply(ticket_id: int, body: SupportReplyIn, db: Session = Depends(get_session),
                  principal: Principal = Depends(require_admin)):
    from .services import support
    r = support.reply(db, ticket_id, body.body, principal.actor, body.close)
    admin.audit(db, "support.reply", str(ticket_id), actor=principal.actor, closed=body.close)
    db.commit()
    return {"id": r.id}


class SupportStatusIn(BaseModel):
    status: Literal["open", "closed"]


@router.post("/support/{ticket_id}/status")
def support_status(ticket_id: int, body: SupportStatusIn, db: Session = Depends(get_session),
                   principal: Principal = Depends(require_admin)):
    from .services import support
    t = support.set_status(db, ticket_id, body.status)
    admin.audit(db, f"support.{body.status}", str(ticket_id), actor=principal.actor)
    db.commit()
    return {"id": t.id, "status": t.status}
