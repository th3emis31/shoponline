"""The shop's automation: jobs that run by themselves, and the rules for when
they may act without asking.

Policy ("automatic within limits", NOVAHAUS Blueprint section J):
- Routine, reversible work always runs: closing abandoned checkouts, stock
  checks, backups, the daily report.
- Money and price actions run automatically ONLY within the limits in
  settings (auto_reorder_max, auto_reorder_weekly_max, auto_price_max_pct).
  Anything above a limit waits in Admin > Approvals for a person.
- Automatic price changes only ever RAISE a price to protect the minimum
  margin; the automation never lowers prices.
- Every automatic action is written to the audit log as actor "automation".
"""

import json
import math
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (AnalyticsEvent, AutomationRun, Cart, CartItem, DailyReport, JobLease, Order, Product,
                      PurchaseOrder, Recommendation, SupplierOrder)
from . import payments, unit_economics
from .admin import audit
from .shop import ShopError

ACTOR = "automation"
OPEN_PO = ("approved", "sent")
SALE_STATUSES = ("placed", "paid", "shipped")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _gbp(pence: int) -> str:
    return f"GBP {pence / 100:,.2f}"


# ---------------------------------------------------------------- policy

def auto_decision(db: Session, rec: Recommendation) -> tuple[bool, str]:
    """May the automation carry this out without asking? Returns (yes, why)."""
    data = json.loads(rec.payload)
    if rec.kind == "reorder":
        if rec.impact <= 0:
            return False, "cost unknown (landed cost is 0) - needs a person"
        if rec.impact > settings.auto_reorder_max:
            return False, f"{_gbp(rec.impact)} is above the automatic limit of {_gbp(settings.auto_reorder_max)}"
        week_ago = _now() - timedelta(days=7)
        spent = db.scalar(
            select(func.coalesce(func.sum(Recommendation.impact), 0)).where(
                Recommendation.kind == "reorder", Recommendation.auto.is_(True),
                Recommendation.status == "executed", Recommendation.created_at >= week_ago)
        ) or 0
        if spent + rec.impact > settings.auto_reorder_weekly_max:
            return False, (f"would bring automatic reorders this week to {_gbp(spent + rec.impact)}, "
                           f"above the weekly limit of {_gbp(settings.auto_reorder_weekly_max)}")
        return True, f"within limits ({_gbp(rec.impact)}; this week {_gbp(spent + rec.impact)})"
    if rec.kind == "price_change":
        old, new = data["old_price"], data["new_price"]
        if new < old:
            return False, "automation never lowers prices"
        pct = (new - old) / old * 100
        if pct > settings.auto_price_max_pct:
            return False, f"+{pct:.1f}% is above the automatic limit of +{settings.auto_price_max_pct:g}%"
        return True, f"within limits (+{pct:.1f}%)"
    return False, "unknown kind"


def execute(db: Session, rec: Recommendation, actor: str) -> str:
    """Carry out an approved recommendation. Re-checks the facts first."""
    data = json.loads(rec.payload)
    product = db.get(Product, rec.target)
    if product is None:
        raise ShopError("Product no longer exists", 409)
    if rec.kind == "reorder":
        po = PurchaseOrder(product_id=product.id, quantity=data["quantity"], unit_cost=data["unit_cost"],
                           total=data["quantity"] * data["unit_cost"], status="approved",
                           recommendation_id=rec.id)
        db.add(po)
        db.flush()
        audit(db, "purchase_order.create", str(po.id), actor=actor, product=product.id,
              quantity=po.quantity, total=po.total, recommendation=rec.id)
        return f"Purchase order #{po.id} ready to send: {po.quantity} x {product.name} ({_gbp(po.total)})"
    if rec.kind == "price_change":
        if product.price != data["old_price"]:
            raise ShopError(f"Price changed since this was suggested (now {_gbp(product.price)}); not applied", 409)
        product.price = data["new_price"]
        audit(db, "product.update", product.id, actor=actor, before={"price": data["old_price"]},
              after={"price": data["new_price"]}, note=f"recommendation #{rec.id}: {rec.reason}")
        return f"Price of {product.name} changed {_gbp(data['old_price'])} -> {_gbp(data['new_price'])}"
    raise ShopError("Unknown recommendation kind")


def submit(db: Session, rec: Recommendation) -> Recommendation:
    """Save a new recommendation and, if the policy allows, carry it out now."""
    db.add(rec)
    db.flush()
    ok, why = auto_decision(db, rec)
    rec.decision_note = why
    if ok:
        rec.auto = True
        rec.decided_by = ACTOR
        rec.decided_at = _now()
        try:
            rec.result = execute(db, rec, ACTOR)
            rec.status = "executed"
        except ShopError as exc:
            rec.status = "failed"
            rec.result = exc.message
    db.commit()
    return rec


def decide(db: Session, rec_id: int, approve: bool, actor: str, note: str = "") -> Recommendation:
    rec = db.get(Recommendation, rec_id)
    if rec is None:
        raise ShopError("Recommendation not found", 404)
    now = _now()
    new_status = "approved" if approve else "rejected"
    # Claim it atomically: of two simultaneous clicks, only one can win.
    claimed = db.execute(
        update(Recommendation)
        .where(Recommendation.id == rec_id, Recommendation.status == "pending")
        .values(status=new_status, decided_by=actor, decided_at=now,
                decision_note=note or new_status)
        .execution_options(synchronize_session="fetch")
    ).rowcount == 1
    if not claimed:
        db.rollback()
        db.refresh(rec)
        raise ShopError(f"Already {rec.status}", 409)
    if not approve:
        audit(db, "recommendation.reject", str(rec.id), actor=actor, note=note)
        db.commit()
        return rec
    try:
        rec.result = execute(db, rec, actor)
        rec.status = "executed"
        audit(db, "recommendation.approve", str(rec.id), actor=actor, note=note)
        db.commit()
    except ShopError:
        db.rollback()  # also undoes the claim: it stays pending
        raise
    return rec


# ---------------------------------------------------------------- purchase orders

PO_TRANSITIONS = {"approved": {"sent", "cancelled"}, "sent": {"received", "cancelled"}}


def set_po_status(db: Session, po_id: int, status: str, actor: str) -> PurchaseOrder:
    po = db.get(PurchaseOrder, po_id)
    if po is None:
        raise ShopError("Purchase order not found", 404)
    old = po.status
    if status not in PO_TRANSITIONS.get(old, set()):
        raise ShopError(f"Cannot change {old} to {status}", 409)
    moved = db.execute(
        update(PurchaseOrder)
        .where(PurchaseOrder.id == po_id, PurchaseOrder.status == old)
        .values(status=status, updated_at=_now())
        .execution_options(synchronize_session="fetch")
    ).rowcount == 1
    if not moved:  # e.g. a double click: the first one already changed it
        db.rollback()
        raise ShopError("This purchase order changed meanwhile. Reload and try again.", 409)
    if status == "received":
        # SQL-side increment: never loses a sale that happens at the same moment.
        db.execute(update(Product).where(Product.id == po.product_id)
                   .values(stock=Product.stock + po.quantity))
    audit(db, "purchase_order.status", str(po.id), actor=actor, old=old, new=status)
    db.commit()
    db.refresh(po)
    return po


# ---------------------------------------------------------------- jobs

def job_close_abandoned_checkouts(db: Session) -> str:
    if not payments.payments_enabled():
        return "skipped: payments are off"
    cutoff = _now() - timedelta(minutes=settings.pending_payment_timeout_minutes)
    orders = [o for o in db.scalars(select(Order).where(Order.status == "pending_payment"))
              if _aware(o.created_at) < cutoff]
    results = {}
    for order in orders:
        try:
            outcome = payments.reconcile_pending(db, order)
            if outcome != "skipped":
                audit(db, "order.reconcile", order.id, actor=ACTOR, outcome=outcome)
                db.commit()
            results[outcome] = results.get(outcome, 0) + 1
        except Exception as exc:  # Stripe down etc.: leave the order for next time
            db.rollback()
            results["error"] = results.get("error", 0) + 1
            results.setdefault("errors", []).append(f"{order.id}: {exc}")
    return f"checked {len(orders)} old unpaid checkout(s): {results or 'nothing to do'}"


def job_low_stock(db: Session) -> str:
    created = []
    for p in db.scalars(select(Product).where(Product.active.is_(True))):
        if p.is_dropship or p.stock > p.reorder_point:
            continue  # dropship products have no stock of our own
        open_po = db.scalar(select(func.count()).select_from(PurchaseOrder).where(
            PurchaseOrder.product_id == p.id, PurchaseOrder.status.in_(OPEN_PO)))
        pending = db.scalar(select(func.count()).select_from(Recommendation).where(
            Recommendation.target == p.id, Recommendation.kind == "reorder",
            Recommendation.status == "pending"))
        if open_po or pending:
            continue
        qty = max(p.reorder_qty, 1)
        rec = submit(db, Recommendation(
            kind="reorder", target=p.id,
            payload=json.dumps({"quantity": qty, "unit_cost": p.landed_cost}),
            reason=(f"{p.name}: stock {p.stock} is at or below the reorder point {p.reorder_point}. "
                    f"Suggest ordering {qty} at the ESTIMATED landed cost {_gbp(p.landed_cost)} each."),
            impact=qty * p.landed_cost))
        created.append(f"{p.id} ({rec.status})")
    return f"reorders: {', '.join(created)}" if created else "all stock above reorder points"


def price_for_margin(p: Product, min_margin: float) -> int | None:
    """Lowest price (rounded up to 50p) that meets min_margin, or None if unreachable."""
    from .admin import economics
    price = p.price
    for _ in range(400):  # up to +GBP 200 in 50p steps
        ue = economics(p, price)
        if ue.contribution_margin >= min_margin:
            return price
        price = int(math.floor(price / 50) * 50) + 50
    return None


def job_margin_guard(db: Session) -> str:
    created = []
    from .admin import economics
    for p in db.scalars(select(Product).where(Product.active.is_(True))):
        if p.is_dropship and p.supplier_cost <= 0:
            continue  # supplier price not entered yet: nothing to judge
        ue = economics(p)
        if ue.contribution_margin >= settings.min_contribution_margin:
            continue
        pending = db.scalar(select(func.count()).select_from(Recommendation).where(
            Recommendation.target == p.id, Recommendation.kind == "price_change",
            Recommendation.status == "pending"))
        if pending:
            continue
        new_price = price_for_margin(p, settings.min_contribution_margin)
        if new_price is None or new_price == p.price:
            continue
        rec = submit(db, Recommendation(
            kind="price_change", target=p.id,
            payload=json.dumps({"old_price": p.price, "new_price": new_price}),
            reason=(f"{p.name}: contribution margin {ue.contribution_margin:.0%} is below the "
                    f"{settings.min_contribution_margin:.0%} minimum (blueprint gate 2). "
                    f"{_gbp(new_price)} restores it. Based on ESTIMATED costs."),
            impact=new_price - p.price))
        created.append(f"{p.id} ({rec.status})")
    return f"price suggestions: {', '.join(created)}" if created else "all margins at or above minimum"


def job_backup(db: Session) -> str:
    from .. import backup  # local import: backup imports settings at module load
    try:
        path = backup.create_backup()
    except backup.BackupError as exc:
        if "not found on PATH" in str(exc):
            # Hosted PostgreSQL (e.g. Neon) without pg_dump on the server: the database
            # provider's own point-in-time restore is the backup there.
            return f"skipped: {exc} The database provider's own backups apply."
        raise
    counts = backup.verify_backup(path)
    note = ""
    if settings.backup_keep > 0:
        removed = backup.prune(settings.backup_keep)
        note = f"; kept newest {settings.backup_keep}, removed {len(removed)} older" if removed else ""
    return f"saved and verified {path.name} {counts}{note}"


def job_cleanup(db: Session) -> str:
    """Remove carts nobody has touched for cart_ttl_days (they hold no stock)."""
    cutoff = _now() - timedelta(days=settings.cart_ttl_days)
    old = select(Cart.id).where(Cart.created_at < cutoff)
    db.execute(delete(CartItem).where(CartItem.cart_id.in_(old)))  # explicit: SQLite doesn't cascade
    n = db.execute(delete(Cart).where(Cart.created_at < cutoff)).rowcount
    db.commit()
    return f"removed {n} old cart(s)"


def build_report(db: Session, day: datetime) -> str:
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    in_day = (Order.created_at >= start) & (Order.created_at < end)
    orders = db.scalars(select(Order).where(in_day, Order.status.in_(SALE_STATUSES))).all()
    revenue = sum(o.total for o in orders)
    contribution = 0
    for o in orders:
        for item in o.items:
            p = db.get(Product, item.product_id)
            if p:
                from .admin import economics
                contribution += economics(p, item.unit_price).contribution_pre_ads * item.quantity
    events = dict(db.execute(select(AnalyticsEvent.type, func.count()).where(
        AnalyticsEvent.created_at >= start, AnalyticsEvent.created_at < end).group_by(AnalyticsEvent.type)).all())
    low = [p for p in db.scalars(select(Product).where(Product.active.is_(True)))
           if not p.is_dropship and p.stock <= p.reorder_point]
    to_buy = db.scalar(select(func.count()).select_from(SupplierOrder).where(SupplierOrder.status == "to_order"))
    pending = db.scalar(select(func.count()).select_from(Recommendation).where(Recommendation.status == "pending"))
    review = db.scalar(select(func.count()).select_from(Order).where(Order.status == "payment_review"))
    to_ship = db.scalar(select(func.count()).select_from(Order).where(Order.status.in_(("paid", "placed"))))
    errors = db.scalars(select(AutomationRun).where(AutomationRun.status == "error",
                                                    AutomationRun.started_at >= start)).all()
    views = events.get("view_product", 0)
    conv = f"{len(orders) / views:.1%}" if views else "n/a"
    lines = [
        f"# NOVAHAUS daily report: {start:%Y-%m-%d} (UTC)",
        "",
        "## Sales",
        f"- Orders: {len(orders)}",
        f"- Revenue (inc. VAT): {_gbp(revenue)}",
        f"- Contribution before ads (ESTIMATE): {_gbp(contribution)}",
        f"- Product views: {views}, add to cart: {events.get('add_to_cart', 0)}, "
        f"checkouts: {events.get('begin_checkout', 0)}, purchases: {events.get('purchase', 0)} "
        f"(view to order: {conv})",
        "",
        "## Needs attention",
        f"- Orders to ship: {to_ship}",
        f"- Supplier orders to place (dropship): {to_buy}",
        f"- Payments to review: {review}",
        f"- Approvals waiting: {pending}",
        f"- Low stock: {', '.join(f'{p.name} ({p.stock})' for p in low) or 'none'}",
        f"- Automation errors: {len(errors)}" + (f" ({'; '.join(e.job for e in errors)})" if errors else ""),
    ]
    return "\n".join(lines)


def job_daily_report(db: Session) -> str:
    yesterday = _now() - timedelta(days=1)
    key = f"{yesterday:%Y-%m-%d}"
    if db.scalar(select(DailyReport).where(DailyReport.day == key)):
        return f"report for {key} already exists"
    db.add(DailyReport(day=key, content=build_report(db, yesterday)))
    db.commit()
    return f"report for {key} written"


# name -> (function, kind, value): kind "every" = minutes between runs; "daily" = UTC hour
JOBS = {
    "close_abandoned_checkouts": (job_close_abandoned_checkouts, "every", 15),
    "low_stock": (job_low_stock, "every", 60),
    "margin_guard": (job_margin_guard, "every", 360),
    "backup": (job_backup, "daily", lambda: settings.backup_hour),
    "daily_report": (job_daily_report, "daily", lambda: settings.report_hour),
    "cleanup": (job_cleanup, "daily", lambda: 3),
    "send_emails": (lambda db: _emails().send_due(db), "every", 5),
    "winback_emails": (lambda db: f"queued {_emails().queue_winbacks(db)} win-back email(s)", "daily", lambda: 9),
}


def _emails():
    from . import emails
    return emails

LEASE = timedelta(minutes=30)


def _acquire(db: Session, job: str, holder: str) -> bool:
    """Take the job's lease; False if another runner holds a live one."""
    now = _now()
    taken = db.execute(update(JobLease).where(JobLease.job == job, JobLease.expires_at < now)
                       .values(holder=holder, expires_at=now + LEASE)).rowcount == 1
    if taken:
        db.commit()
        return True
    try:
        db.add(JobLease(job=job, holder=holder, expires_at=now + LEASE))
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


def _release(db: Session, job: str, holder: str) -> None:
    db.execute(delete(JobLease).where(JobLease.job == job, JobLease.holder == holder))
    db.commit()


def _last_run(db: Session, job: str) -> AutomationRun | None:
    return db.scalar(select(AutomationRun).where(AutomationRun.job == job)
                     .order_by(AutomationRun.started_at.desc()).limit(1))


def is_due(db: Session, job: str, now: datetime) -> bool:
    _, kind, value = JOBS[job]
    last = _last_run(db, job)
    last_at = _aware(last.started_at) if last else None
    if kind == "every":
        return last_at is None or now - last_at >= timedelta(minutes=value)
    hour = value()
    return now.hour >= hour and (last_at is None or last_at.date() < now.date())


def run_job(db: Session, job: str) -> AutomationRun:
    fn = JOBS[job][0]
    holder = uuid.uuid4().hex
    if not _acquire(db, job, holder):
        run = AutomationRun(job=job, started_at=_now(), finished_at=_now(), status="skipped",
                            message="skipped: already running elsewhere")
        db.add(run)
        db.commit()
        return run
    run = AutomationRun(job=job, started_at=_now())
    db.add(run)
    db.commit()
    try:
        message = fn(db)
        run.status = "skipped" if message.startswith("skipped") else "ok"
        run.message = message
    except Exception as exc:  # a failing job never stops the shop or other jobs
        db.rollback()
        run = db.merge(run)
        run.status = "error"
        run.message = f"{type(exc).__name__}: {exc}"
    run.finished_at = _now()
    db.commit()
    try:
        _release(db, job, holder)
    except Exception:
        db.rollback()  # the lease simply expires
    return run


def run_due_jobs(db: Session, now: datetime | None = None) -> list[AutomationRun]:
    now = now or _now()
    return [run_job(db, job) for job in JOBS if is_due(db, job, now)]


def status(db: Session) -> dict:
    jobs = []
    for name, (_, kind, value) in JOBS.items():
        last = _last_run(db, name)
        schedule = f"every {value} min" if kind == "every" else f"daily after {value():02d}:00 UTC"
        jobs.append({"job": name, "schedule": schedule,
                     "last_run": last.started_at if last else None,
                     "last_status": last.status if last else None,
                     "last_message": last.message if last else None})
    return {
        "enabled": settings.automation_enabled,
        "limits": {
            "auto_reorder_max": settings.auto_reorder_max,
            "auto_reorder_weekly_max": settings.auto_reorder_weekly_max,
            "auto_price_max_pct": settings.auto_price_max_pct,
            "min_contribution_margin": settings.min_contribution_margin,
        },
        "jobs": jobs,
    }
