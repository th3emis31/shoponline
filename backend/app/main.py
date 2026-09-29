from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_session
from .admin_routes import public as admin_public_router
from .admin_routes import router as admin_router
from .models import Order, Product, WaitlistSignup
from .security import require_owner
from .schemas import AddItemIn, CartOut, CheckoutIn, EconomicsOut, OrderOut, ProductOut
from .services import analytics, payments, shop, unit_economics
from .services.shop import ShopError

@asynccontextmanager
async def lifespan(_: FastAPI):
    from . import scheduler
    if settings.automation_enabled:
        scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="NOVAHAUS API", version="0.1.0", lifespan=lifespan)
app.include_router(admin_public_router)
app.include_router(admin_router)


@app.exception_handler(ShopError)
def shop_error_handler(_: Request, exc: ShopError):
    return JSONResponse(status_code=exc.status, content={"error": exc.message})


def to_public(p: Product) -> ProductOut:
    return ProductOut(id=p.id, name=p.name, price=p.price, is_bundle=p.is_bundle, in_stock=p.stock > 0)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/products", response_model=list[ProductOut])
def products(db: Session = Depends(get_session)):
    return [to_public(p) for p in shop.list_products(db)]


@app.get("/api/products/{product_id}", response_model=ProductOut)
def product(product_id: str, db: Session = Depends(get_session)):
    p = db.get(Product, product_id)
    if p is None or not p.active:
        raise ShopError("Product not found", 404)
    return to_public(p)


@app.post("/api/carts", response_model=CartOut, status_code=201)
def create_cart(db: Session = Depends(get_session)):
    return shop.cart_view(shop.create_cart(db))


@app.get("/api/carts/{cart_id}", response_model=CartOut)
def get_cart(cart_id: str, db: Session = Depends(get_session)):
    return shop.cart_view(shop.get_cart(db, cart_id))


@app.post("/api/carts/{cart_id}/items", response_model=CartOut)
def add_item(cart_id: str, body: AddItemIn, db: Session = Depends(get_session)):
    return shop.cart_view(shop.add_item(db, cart_id, body.product_id, body.quantity))


@app.delete("/api/carts/{cart_id}/items/{product_id}", response_model=CartOut)
def remove_item(cart_id: str, product_id: str, db: Session = Depends(get_session)):
    return shop.cart_view(shop.remove_item(db, cart_id, product_id))


@app.post("/api/carts/{cart_id}/checkout", response_model=OrderOut, status_code=201)
def checkout(cart_id: str, body: CheckoutIn, db: Session = Depends(get_session)):
    if not payments.payments_enabled():
        # Development mode: no payment provider configured, order is just placed.
        order = shop.checkout(db, cart_id, body.name, str(body.email), body.address)
        analytics.record(db, "purchase")
        return shop.order_view(order)

    # Stock is reserved now and released if payment fails or the session expires.
    # The cart is kept until Stripe accepts the session, so an outage never loses it.
    order = shop.checkout(db, cart_id, body.name, str(body.email), body.address,
                          status="pending_payment", delete_cart=False)
    try:
        session_id, url = payments.create_checkout_session(order)
    except Exception as exc:
        order.status = "cancelled"
        payments.release_stock(db, order)
        db.commit()
        raise ShopError("Payment provider unavailable, please try again", 502) from exc
    order.stripe_session_id = session_id
    db.delete(shop.get_cart(db, cart_id))
    db.commit()
    return {**shop.order_view(order), "checkout_url": url}


class EventIn(BaseModel):
    type: Literal["view_product", "add_to_cart", "begin_checkout"]
    product_id: str | None = Field(default=None, max_length=64)


@app.post("/api/events", status_code=204)
def track_event(body: EventIn, db: Session = Depends(get_session)):
    # Unknown product IDs are dropped so the table can't be filled with junk.
    product_id = body.product_id if body.product_id and db.get(Product, body.product_id) else None
    analytics.record(db, body.type, product_id)


WAITLIST_CONSENT = ("Email me once when NOVAHAUS launches (or when this product is available). "
                    "No other marketing. I can unsubscribe at any time.")


class WaitlistIn(BaseModel):
    email: EmailStr
    product_id: str | None = Field(default=None, max_length=64)
    consent: bool


@app.post("/api/waitlist", status_code=201)
def join_waitlist(body: WaitlistIn, db: Session = Depends(get_session)):
    # UK rules (PECR/UK GDPR): marketing email needs a clear, positive opt-in.
    if not body.consent:
        raise ShopError("Please tick the box to agree to the launch email.")
    email = str(body.email).strip().lower()
    product_id = body.product_id if body.product_id and db.get(Product, body.product_id) else None
    exists = db.scalar(select(WaitlistSignup).where(
        WaitlistSignup.email == email,
        WaitlistSignup.product_id.is_(None) if product_id is None else WaitlistSignup.product_id == product_id))
    if not exists:
        db.add(WaitlistSignup(email=email, product_id=product_id, consent_text=WAITLIST_CONSENT))
        db.commit()
    # Same answer whether or not the email was already there (no email enumeration).
    return {"ok": True, "message": "Thanks, you're on the list. We'll email you once."}


@app.get("/api/waitlist/consent")
def waitlist_consent():
    return {"text": WAITLIST_CONSENT}


@app.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_session)):
    event = payments.verify_event(await request.body(), request.headers.get("stripe-signature"))
    return {"received": True, "outcome": payments.handle_event(db, event)}


@app.get("/api/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: str, email: str, db: Session = Depends(get_session)):
    # Track order: requires order ID + email (Blueprint section H).
    order = db.get(Order, order_id)
    if order is None or order.customer_email.lower() != email.strip().lower():
        raise ShopError("Order not found", 404)
    return shop.order_view(order)


@app.get("/api/admin/products/{product_id}/economics", response_model=EconomicsOut,
         dependencies=[Depends(require_owner)])
def product_economics(product_id: str, cac: int = 0, db: Session = Depends(get_session)):
    p = db.get(Product, product_id)
    if p is None:
        raise ShopError("Product not found", 404)
    try:
        ue = unit_economics.calculate(p.price, p.landed_cost, p.shipping_cost, p.packaging_cost, cac=cac)
    except ValueError as exc:
        raise ShopError(str(exc)) from exc
    return EconomicsOut(product_id=p.id, **ue.__dict__)
