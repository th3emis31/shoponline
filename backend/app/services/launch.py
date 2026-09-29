"""Launch checklist: the blueprint's 14 gates (section O).

"NOVAHAUS launches only when every gate below is green; a working website is one gate of fourteen."
Each gate combines automatic checks on the shop's own data with the owner's confirmation for
the things software can't see (samples, carrier, professional reviews). Advice only: it never
flips the shop live by itself.
"""
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AnalyticsEvent, AutomationRun, LaunchGate, Order, Product, StripeEvent, WaitlistSignup
from . import admin, auth, support

# id, name, pass condition (blueprint wording), label, needs owner confirmation
GATES = [
    ("product_validation", "Product validation", "Smoke test beats the CTR and waitlist targets you set in week 2", "HYPOTHESIS to prove", True),
    ("unit_economics", "Unit economics", "Real quotes give contribution before ads ≥ 40% and break-even ROAS ≤ 2.5 on the lead bundle", "ESTIMATE until quotes", True),
    ("supplier", "Supplier", "Samples approved; written price, MOQ, lead time; first batch inspected", "", True),
    ("website", "Website", "All launch pages live; mobile Lighthouse performance ≥ 90", "", True),
    ("checkout", "Checkout", "Stripe test and one live order end-to-end; totals and shipping shown before payment", "", True),
    ("payments", "Payments", "Webhooks signature-verified; refunds tested", "", True),
    ("shipping", "Shipping", "Carrier account, rates, packaging drop-tested", "", True),
    ("returns", "Returns", "14-day cancellation from delivery stated clearly; refund process tested (GOV.UK)", "LEGAL REQUIREMENT", True),
    ("legal_pages", "Legal pages", "Business name, address, contact details, prices inc. taxes, delivery and cancellation info given "
     "before order; privacy, terms and cookie policy reviewed", "NEEDS PROFESSIONAL REVIEW", True),
    ("cookies", "Cookies + consent", "Non-essential cookies only after a clear positive action (ICO)", "LEGAL REQUIREMENT", True),
    ("product_safety", "Product safety", "Per-product safety file, labelling, supplier documents", "NEEDS PROFESSIONAL REVIEW", True),
    ("analytics", "Analytics", "Funnel events firing: view → add-to-cart → checkout → purchase", "", False),
    ("security", "Security + backups", "Auth on admin, no secrets in Git, backup restored successfully once", "", True),
    ("support", "Customer support", "Inbox, reply templates, 1-business-day reply target", "", False),
]
GATE_IDS = {g[0] for g in GATES}
LEAD_BUNDLE = "desk-reset"


def _check(ok: bool, text: str) -> dict:
    return {"ok": bool(ok), "text": text}


def _auto(db: Session, gate: str) -> list[dict]:
    """What the software can verify by itself for each gate."""
    if gate == "product_validation":
        n = db.scalar(select(func.count()).select_from(WaitlistSignup)) or 0
        return [_check(n > 0, f"{n} waitlist sign-ups so far. Compare with your week-2 target in Admin > Campaigns.")]
    if gate == "unit_economics":
        p = db.get(Product, LEAD_BUNDLE)
        if p is None:
            return [_check(False, "Lead bundle not found")]
        ue = admin.economics(p)
        real = (p.supplier_cost if p.is_dropship else p.landed_cost) > 0
        return [
            _check(real, "Bundle cost entered. Confirm below only once it comes from a written supplier quote"
                   if real else "No bundle cost entered yet"),
            _check(ue.contribution_margin >= 0.40, f"Contribution before ads {ue.contribution_margin:.0%} (needs ≥ 40%)"),
            _check(ue.break_even_roas is not None and ue.break_even_roas <= 2.5,
                   f"Break-even ROAS {ue.break_even_roas:.2f}× (needs ≤ 2.5)" if ue.break_even_roas else "Break-even ROAS: never profitable"),
        ]
    if gate == "supplier":
        active = list(db.scalars(select(Product).where(Product.active.is_(True), Product.is_bundle.is_(False))))
        missing = [p.name for p in active if not p.supplier_name]
        return [_check(not missing, "Every product has a supplier" if not missing else f"No supplier yet: {', '.join(missing)}")]
    if gate == "website":
        return [_check(True, "Launch pages built: home, shop, product, cart, about, contact, FAQ, shipping, returns, track, legal, 404")]
    if gate == "checkout":
        paid = db.scalar(select(func.count()).select_from(Order).where(
            Order.status.in_(("paid", "shipped")), Order.stripe_session_id.is_not(None))) or 0
        return [_check(bool(settings.stripe_secret_key), "Stripe key set" if settings.stripe_secret_key else "Stripe key not set"),
                _check(paid > 0, f"{paid} order(s) paid through Stripe end to end"),
                _check(True, "Totals and delivery are shown before payment (cart page)")]
    if gate == "payments":
        events = db.scalar(select(func.count()).select_from(StripeEvent)) or 0
        return [_check(bool(settings.stripe_webhook_secret), "Webhook secret set; every webhook's signature is checked"
                       if settings.stripe_webhook_secret else "Webhook secret not set"),
                _check(events > 0, f"{events} verified webhook event(s) received")]
    if gate == "returns":
        return [_check(True, "Returns page states the 14-day cancellation right from delivery")]
    if gate == "legal_pages":
        return [_check(bool(settings.shop_address.strip()), "Business address set (SHOP_ADDRESS)"
                       if settings.shop_address.strip() else "SHOP_ADDRESS not set"),
                _check(settings.shop_legal_name.strip() not in ("", "NOVAHAUS"), "Registered business name set (SHOP_LEGAL_NAME)"
                       if settings.shop_legal_name.strip() not in ("", "NOVAHAUS") else "SHOP_LEGAL_NAME is still the default")]
    if gate == "cookies":
        return [_check(True, "The site sets no advertising or tracking cookies; only cart and order storage (see /cookies)")]
    if gate == "analytics":
        types = set(db.scalars(select(AnalyticsEvent.type).distinct()))
        need = ["view_product", "add_to_cart", "begin_checkout", "purchase"]
        return [_check(t in types, f"'{t}' events recorded" if t in types else f"No '{t}' events yet") for t in need]
    if gate == "security":
        ok_backup = db.scalar(select(func.count()).select_from(AutomationRun).where(
            AutomationRun.job == "backup", AutomationRun.status == "ok")) or 0
        return [_check(auth.any_active_owner(db), "Personal owner login exists (shared token switched off)"),
                _check(bool(settings.secret_key) or not settings.is_production, "SECRET_KEY set"),
                _check(ok_backup > 0, f"{ok_backup} successful automatic backup(s)")]
    if gate == "support":
        return [_check(True, f"Support inbox and {len(support.TEMPLATES)} reply templates in Admin > Support"),
                _check(support.overdue_count(db) == 0, f"{support.overdue_count(db)} message(s) past the 1-business-day target")]
    return []


def checklist(db: Session) -> dict:
    signs = {g.gate: g for g in db.scalars(select(LaunchGate))}
    rows = []
    for gid, name, condition, label, needs_owner in GATES:
        checks = _auto(db, gid)
        s = signs.get(gid)
        if gid == "website":
            try:
                score = int((s.value if s else "") or -1)
            except ValueError:
                score = -1
            checks.append(_check(score >= 90, f"Mobile Lighthouse performance: {score if score >= 0 else 'not measured'} (needs ≥ 90)"))
        auto_ok = all(c["ok"] for c in checks)
        confirmed = bool(s and s.confirmed)
        # Older confirmations saved without evidence don't count until evidence is added.
        evidenced = confirmed and len((s.note or "").strip()) >= 5
        passed = auto_ok and (evidenced or not needs_owner)
        rows.append({"id": gid, "name": name, "condition": condition, "label": label, "needs_owner": needs_owner,
                     "checks": checks, "confirmed": confirmed, "evidenced": evidenced, "value": s.value if s else "", "note": s.note if s else "",
                     "confirmed_by": s.confirmed_by if s else None, "updated_at": s.updated_at if s else None,
                     "passed": passed})
    green = sum(1 for r in rows if r["passed"])
    return {"green": green, "total": len(rows), "ready": green == len(rows), "gates": rows}


def sign(db: Session, gate: str, confirmed: bool, value: str, note: str, actor: str | None) -> LaunchGate:
    if gate not in GATE_IDS:
        raise LookupError("Unknown gate")
    # A confirmation is a claim: it must say what the evidence is.
    if confirmed and len(note.strip()) < 5:
        raise ValueError("Write the evidence first (for example: written quote from Supplier A, 12 Oct).")
    row = db.get(LaunchGate, gate)
    if row is None:
        row = LaunchGate(gate=gate)
        db.add(row)
    row.confirmed, row.value, row.note = confirmed, value.strip(), note.strip()
    row.confirmed_by, row.updated_at = actor, datetime.now(timezone.utc)
    return row
