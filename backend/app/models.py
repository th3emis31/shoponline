import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# All money columns are integer pence, inc. VAT unless named otherwise.


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("stock >= 0", name="stock_non_negative"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    price: Mapped[int] = mapped_column(Integer)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    is_bundle: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Internal cost inputs (ESTIMATES until supplier quotes); never public.
    landed_cost: Mapped[int] = mapped_column(Integer, default=0)
    shipping_cost: Mapped[int] = mapped_column(Integer, default=0)
    packaging_cost: Mapped[int] = mapped_column(Integer, default=0)
    # Automation: when stock falls to reorder_point, suggest ordering reorder_qty.
    reorder_point: Mapped[int] = mapped_column(Integer, default=10, server_default="10")
    reorder_qty: Mapped[int] = mapped_column(Integer, default=20, server_default="20")


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart", cascade="all, delete-orphan", order_by="CartItem.id"
    )


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="qty_positive"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cart_id: Mapped[str] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    cart: Mapped[Cart] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # placed (no payments configured) | pending_payment | paid | shipped | cancelled | payment_review
    status: Mapped[str] = mapped_column(String(20), default="placed")
    customer_name: Mapped[str] = mapped_column(String(200))
    customer_email: Mapped[str] = mapped_column(String(320), index=True)
    shipping_address: Mapped[str] = mapped_column(String(500))
    subtotal: Mapped[int] = mapped_column(Integer)
    shipping: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    stripe_session_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.id"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    # Snapshot at purchase time so later price changes don't alter history.
    name: Mapped[str] = mapped_column(String(200))
    unit_price: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    order: Mapped[Order] = relationship(back_populates="items")


class StripeEvent(Base):
    """Processed webhook event IDs, so a re-delivered event is applied once."""

    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    type: Mapped[str] = mapped_column(String(100))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AnalyticsEvent(Base):
    """Anonymous funnel event. No cookies, IDs or personal data are stored."""

    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    product_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class AdminAudit(Base):
    """Every admin write: what changed, from what, to what, and why."""

    __tablename__ = "admin_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(100))
    # Who did it: an admin's email, or "admin-token" for the shared break-glass token.
    actor: Mapped[str | None] = mapped_column(String(320), nullable=True)
    detail: Mapped[str] = mapped_column(Text)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class AdminUser(Base):
    """A person who can sign in to /admin. Roles: owner (everything) or staff (orders only)."""

    __tablename__ = "admin_users"
    __table_args__ = (CheckConstraint("role IN ('owner', 'staff')", name="admin_role_valid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AdminSession(Base):
    """Signed-in admin session. Only a SHA-256 hash of the token is stored."""

    __tablename__ = "admin_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    user: Mapped[AdminUser] = relationship()


class Recommendation(Base):
    """Something the automation wants to do. Runs by itself only within the limits in settings;
    otherwise it waits for a human in Admin > Approvals."""

    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)  # reorder | price_change
    target: Mapped[str] = mapped_column(String(64))  # product id
    payload: Mapped[str] = mapped_column(Text)  # JSON
    reason: Mapped[str] = mapped_column(Text)
    impact: Mapped[int] = mapped_column(Integer, default=0)  # pence (cost of a reorder, price delta)
    # pending | approved | rejected | executed | failed
    status: Mapped[str] = mapped_column(String(16), index=True, default="pending")
    auto: Mapped[bool] = mapped_column(Boolean, default=False)  # decided by the automation itself
    decision_note: Mapped[str] = mapped_column(Text, default="")
    decided_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class PurchaseOrder(Base):
    """Stock to order from a supplier. 'approved' means ready to send; receiving adds stock."""

    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_cost: Mapped[int] = mapped_column(Integer)  # pence, ESTIMATE until supplier quote
    total: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="approved")  # approved|sent|received|cancelled
    recommendation_id: Mapped[int | None] = mapped_column(ForeignKey("recommendations.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AutomationRun(Base):
    """One run of an automation job, for visibility and scheduling."""

    __tablename__ = "automation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")  # ok | error | skipped
    message: Mapped[str] = mapped_column(Text, default="")


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day: Mapped[str] = mapped_column(String(10), unique=True)  # YYYY-MM-DD (UTC) the report covers
    content: Mapped[str] = mapped_column(Text)  # Markdown
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
