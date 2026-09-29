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
