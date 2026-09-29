import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import get_session
from .security import require_admin, require_owner
from .services import admin, analytics, auth, shop
from .services.auth import Principal

# Sign-in endpoints are public; everything else needs a signed-in admin.
public = APIRouter(prefix="/api/admin")
router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


@public.post("/login")
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
    note: str = Field(default="", max_length=500)


def admin_order(o) -> dict:
    return {**shop.order_view(o), "customer_name": o.customer_name, "customer_email": o.customer_email,
            "shipping_address": o.shipping_address, "paid_at": o.paid_at,
            "next_statuses": sorted(admin.TRANSITIONS.get(o.status, set()))}


@router.get("/me")
def me(principal: Principal = Depends(require_admin)):
    return {"actor": principal.actor, "role": principal.role}


@router.get("/orders")
def orders(status: str | None = None, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_session)):
    return [admin_order(o) for o in admin.list_orders(db, status, limit)]


@router.get("/orders/{order_id}")
def order(order_id: str, db: Session = Depends(get_session)):
    o = db.get(admin.Order, order_id)
    if o is None:
        raise shop.ShopError("Order not found", 404)
    return admin_order(o)


@router.post("/orders/{order_id}/status")
def order_status(order_id: str, body: StatusIn, db: Session = Depends(get_session),
                 principal: Principal = Depends(require_admin)):
    return admin_order(admin.set_order_status(db, order_id, body.status, body.note, actor=principal.actor))


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
