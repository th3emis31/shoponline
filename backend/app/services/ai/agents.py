"""The seven assistants. Each gathers FACTS from the shop's own data, then either the built-in
rules or an AI model turns them into labelled advice. Nothing here changes the shop."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...config import settings
from ...models import (AIMemory, AITask, AnalyticsEvent, BusinessDecision, Order, OrderItem, Product,
                       SupportTicket, WaitlistSignup)
from .. import admin, analytics, campaigns, support
from ..shop import ShopError
from . import providers

LABELS = ("FACT", "ASSUMPTION", "ESTIMATE", "HYPOTHESIS")
DRAFT_MARK = "--- DRAFT ---"  # lines after this are draft text (a reply, ad copy), not claims
AGENTS = {
    "research": "Research: what to validate next about customers and products",
    "product": "Product: margins, pricing and the 35% gate for one product",
    "marketing": "Marketing: honest ad angles and copy for one product",
    "analytics": "Analytics: what the funnel and campaigns say",
    "customer": "Customer: draft a reply to a support message",
    "inventory": "Inventory: stock cover and what to reorder",
    "seo": "SEO: page title and description for one product",
}
NEEDS_PRODUCT = ("product", "marketing", "seo")

SYSTEM = (
    "You are an assistant for NOVAHAUS, a small UK online shop selling calm, well-made desk and small-space "
    "organisation products. Be honest and specific. Never invent reviews, scarcity, discounts or specifications. "
    "Every line you write MUST start with exactly one label: FACT:, ASSUMPTION:, ESTIMATE: or HYPOTHESIS:. "
    "FACT only for things stated in the data given to you. If you write draft text (a reply or ad copy), put it "
    f"after a line containing only '{DRAFT_MARK}'. Keep it under 250 words. British English."
)

_gbp = lambda p: f"£{p / 100:,.2f}"  # noqa: E731


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _since(days: int) -> datetime:
    return _now() - timedelta(days=days)


def _units_sold(db: Session, product_id: str, days: int = 30) -> int:
    return db.scalar(select(func.coalesce(func.sum(OrderItem.quantity), 0)).join(Order).where(
        OrderItem.product_id == product_id, Order.status.in_(("placed", "paid", "shipped")),
        Order.created_at >= _since(days))) or 0


def _product(db: Session, subject: str) -> Product:
    p = db.get(Product, subject or "")
    if p is None:
        raise ShopError("Pick a product for this assistant.", 400)
    return p


# ---------------------------------------------------------------- facts + rules per agent

def product_agent(db: Session, subject: str) -> tuple[list[str], list[str]]:
    p = _product(db, subject)
    ue = admin.economics(p)
    costs_known = (p.supplier_cost if p.is_dropship else p.landed_cost) > 0
    facts = [
        f"FACT: {p.name}: price {_gbp(p.price)} inc. VAT, fulfilment {p.fulfilment}.",
        f"FACT: Units sold in the last 30 days: {_units_sold(db, p.id)}.",
        f"ESTIMATE: Contribution before ads {_gbp(ue.contribution_pre_ads)} per sale "
        f"({ue.contribution_margin:.0%} of the ex-VAT price), from the cost figures entered.",
    ]
    out = list(facts)
    if not costs_known:
        out.append("ASSUMPTION: No real supplier cost is entered yet, so every margin figure is a placeholder.")
    gate = settings.min_contribution_margin
    if ue.contribution_margin >= gate:
        out.append(f"FACT: Passes the {gate:.0%} margin gate (Blueprint section D, gate 2).")
    else:
        out.append(f"FACT: Fails the {gate:.0%} margin gate. Do not advertise it until cost or price changes.")
    if ue.break_even_roas:
        out.append(f"ESTIMATE: Break-even ROAS {ue.break_even_roas:.2f}×. Ads must return more than this to make money.")
    out.append("HYPOTHESIS: A bundle or a free-delivery threshold nudge raises average order value more than a price cut would.")
    return facts, out


def marketing_agent(db: Session, subject: str) -> tuple[list[str], list[str]]:
    p = _product(db, subject)
    delivery = p.delivery_estimate or "standard UK delivery"
    facts = [
        f"FACT: Product: {p.name}, {_gbp(p.price)} inc. VAT.",
        f"FACT: Free UK delivery over {_gbp(settings.free_shipping_threshold)}; 14-day returns; delivery: {delivery}.",
        "FACT: There are no customer reviews to quote unless they appear in Admin > Reviews as published.",
    ]
    link = f"{settings.public_base_url}/products/{p.id}?utm_source=facebook&utm_campaign={p.id}-test"
    out = facts + [
        "HYPOTHESIS: Angle 1 (problem): a messy desk makes working from home feel worse; this is a quick fix.",
        "HYPOTHESIS: Angle 2 (material): honest materials and exact dimensions, with no mystery plastics.",
        "HYPOTHESIS: Angle 3 (set): the Desk Reset set solves cables, surface and screen height in one go.",
        "ASSUMPTION: Test each angle with a small budget (about £5 a day for 3 to 4 days) before scaling.",
        f"FACT: Use this tracked link so results show in Admin > Campaigns: {link}",
        DRAFT_MARK,
        "Headline: A calmer desk in ten minutes",
        f"Headline: {p.name[:40]}",
        f"Text: {p.name}. {_gbp(p.price)}, free UK delivery over {_gbp(settings.free_shipping_threshold)}, "
        "14-day returns. Designed for small home offices.",
    ]
    return facts, out


def seo_agent(db: Session, subject: str) -> tuple[list[str], list[str]]:
    p = _product(db, subject)
    title = f"{p.name} | NOVAHAUS"
    if len(title) > 60:
        title = f"{p.name[:50].rstrip(' ,+')} | NOVAHAUS"
    desc = (f"{p.name}. {_gbp(p.price)} inc. VAT, free UK delivery over "
            f"{_gbp(settings.free_shipping_threshold)}, 14-day returns.")[:155]
    facts = [f"FACT: Product: {p.name}, {_gbp(p.price)}."]
    out = facts + [
        f"FACT: Suggested title ({len(title)} characters, limit 60): {title}",
        f"FACT: Suggested description ({len(desc)} characters, limit 155): {desc}",
        "HYPOTHESIS: Searchers use words like 'under desk cable tray no drill' or 'desk mat large'. "
        "Check them in Google Search Console once the shop is live.",
        "ASSUMPTION: Add measured dimensions to the page when the sample arrives; they help search and trust.",
    ]
    return facts, out


def analytics_agent(db: Session, subject: str) -> tuple[list[str], list[str]]:
    f = analytics.funnel(db, 30)
    rep = campaigns.report(db, 30)
    facts = [f"FACT: Last 30 days: " + ", ".join(f"{s['type']} {s['count']}" for s in f["steps"]) + "."]
    out = list(facts)
    worst = None
    for s in f["steps"][1:]:
        if s["rate_from_previous"] is not None and (worst is None or s["rate_from_previous"] < worst["rate_from_previous"]):
            worst = s
    if f["steps"][0]["count"] < 100:
        out.append("ASSUMPTION: Under 100 product views, so any rate here is noise. Get traffic before drawing conclusions.")
    if worst:
        out.append(f"FACT: Biggest drop is into '{worst['type']}' ({worst['rate_from_previous']:.0%} of the step before).")
        hint = {"add_to_cart": "the product page (photos, price clarity, delivery time)",
                "begin_checkout": "the cart (delivery cost surprise, trust)",
                "purchase": "the payment step (payment options, errors)"}.get(worst["type"], "that step")
        out.append(f"HYPOTHESIS: The main friction is {hint}. Watch 5 people use it before changing anything.")
    for c in rep["campaigns"]:
        if c["spend"]:
            out.append(f"ESTIMATE: {c['campaign']}: cost {_gbp(c['spend'])}, {c['orders']} orders, "
                       f"profit after ads {_gbp(c['contribution_after_ads'])}. {c['verdict']}")
    return facts, out


def inventory_agent(db: Session, subject: str) -> tuple[list[str], list[str]]:
    facts, out = [], []
    for p in db.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.name)):
        sold = _units_sold(db, p.id)
        if p.is_dropship:
            facts.append(f"FACT: {p.name}: dropship, no stock held; {sold} sold in 30 days.")
            continue
        facts.append(f"FACT: {p.name}: {p.stock} in stock, reorder point {p.reorder_point}, {sold} sold in 30 days.")
        if sold:
            days = p.stock / (sold / 30)
            out.append(f"ESTIMATE: {p.name}: about {days:.0f} days of stock at the current pace.")
            if days < 21:
                out.append(f"HYPOTHESIS: Reorder {p.name} soon; typical supplier lead time is 2 to 3 weeks (ASSUMPTION).")
        elif p.stock <= p.reorder_point:
            out.append(f"FACT: {p.name} is at or below its reorder point, but has had no sales. Don't reorder until demand shows.")
    out.append("FACT: Reorders are raised by the automation within your limits and appear in Admin > Approvals.")
    return facts, facts + out


def customer_agent(db: Session, subject: str) -> tuple[list[str], list[str]]:
    try:
        t = db.get(SupportTicket, int(subject))
    except (TypeError, ValueError):
        t = None
    if t is None:
        raise ShopError("Pick a customer message for this assistant.", 400)
    key = {"order": "where_is_order", "return": "return_how", "product": "product_question"}.get(t.topic, "product_question")
    if "damag" in t.message.lower() or "broken" in t.message.lower() or "faulty" in t.message.lower():
        key = "damaged"
    facts = [f"FACT: Topic: {support.TOPICS.get(t.topic, t.topic)}. Customer message: {t.message[:1000]}"]
    order = db.get(Order, t.order_id) if t.order_id else None
    if order is not None and order.customer_email.lower() == t.email:
        facts.append(f"FACT: Their order {order.id[:8]} is '{order.status}', total {_gbp(order.total)}.")
    elif t.order_id:
        facts.append("FACT: The order number given doesn't match their email. Don't share order details.")
    out = facts + [f"ASSUMPTION: Template '{support.TEMPLATES[key][0]}' fits this message. Check before sending.",
                   DRAFT_MARK, support.template_text(db, key, t)]
    return facts, out


def research_agent(db: Session, subject: str) -> tuple[list[str], list[str]]:
    wl = dict(db.execute(select(WaitlistSignup.product_id, func.count()).group_by(WaitlistSignup.product_id)).all())
    views = dict(db.execute(select(AnalyticsEvent.product_id, func.count()).where(
        AnalyticsEvent.type == "view_product", AnalyticsEvent.created_at >= _since(30)).group_by(AnalyticsEvent.product_id)).all())
    facts, interest = [], []
    for p in db.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.name)):
        v, w = views.get(p.id, 0), wl.get(p.id, 0)
        facts.append(f"FACT: {p.name}: {v} views (30 days), {w} waitlist sign-ups.")
        interest.append((v + 10 * w, p.name))
    best = max(interest) if interest else (0, "")
    top = f"{best[1]} (views plus 10 per waitlist sign-up)" if best[0] > 0 else ""
    out = facts + [
        "HYPOTHESIS: Remote workers in small UK flats will pay for a tidy, calm desk (Blueprint persona 1). "
        "Test: 5 short interviews, asking what they tried before and what it cost.",
        "HYPOTHESIS: 'No drilling' matters to renters. Test: two ad versions, with and without 'no drilling', and compare click rates.",
        "HYPOTHESIS: The bundle sells better than single items once there are reviews. Test: bundle share of orders after the first 10 reviews.",
        "ASSUMPTION: Competitor prices change often. Check the top 3 on Amazon UK monthly and write them down in the decision log.",
    ]
    if top:
        out.append(f"FACT: Most interest so far: {top}")
    return facts, out


RUNNERS = {"research": research_agent, "product": product_agent, "marketing": marketing_agent,
           "analytics": analytics_agent, "customer": customer_agent, "inventory": inventory_agent, "seo": seo_agent}


# ---------------------------------------------------------------- labels, memory, running

def enforce_labels(text: str) -> str:
    """Every claim line must carry a label; unlabelled AI lines become HYPOTHESIS (unverified)."""
    out, in_draft = [], False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == DRAFT_MARK:
            in_draft = True
            out.append(line)
            continue
        if in_draft or line.startswith("#"):
            out.append(raw.rstrip())
            continue
        bare = line.lstrip("-*• ").replace("**", "")
        for lab in LABELS:
            for form in (f"{lab}:", f"[{lab}]", f"({lab})"):
                if bare.upper().startswith(form):
                    out.append(f"{lab}: {bare[len(form):].strip()}")
                    break
            else:
                continue
            break
        else:
            out.append(f"HYPOTHESIS (unlabelled by the AI, treat as unverified): {bare}")
    return "\n".join(out)


def memory_context(db: Session, limit: int = 5) -> str:
    rows = db.scalars(select(AIMemory).order_by(AIMemory.updated_at.desc()).limit(limit)).all()
    return "\n".join(f"- {m.key}: {m.value[:300]}" for m in rows)


def run(db: Session, agent: str, subject: str = "", actor: str | None = None) -> AITask:
    if agent not in RUNNERS:
        raise ShopError("Unknown assistant", 404)
    facts, rules_out = RUNNERS[agent](db, subject)
    provider = providers.name()
    task = AITask(agent=agent, subject=subject or "", provider=provider, created_by=actor, created_at=_now())
    db.add(task)
    db.flush()
    if provider == "rules":
        task.output = enforce_labels("\n".join(rules_out))
        return task
    memory = memory_context(db)
    prompt = (f"Task: {AGENTS[agent]}.\n\nShop data (these are the only FACTS you have):\n" + "\n".join(facts)
              + (f"\n\nDecisions the owner already approved:\n{memory}" if memory else "")
              + "\n\nWrite your advice now, every line labelled.")
    if agent == "customer":
        prompt += f" End with '{DRAFT_MARK}' and a short, kind reply the owner can send."
    try:
        task.output = enforce_labels(providers.generate(db, SYSTEM, prompt, task.id))
        task.provider = provider
    except providers.ProviderError as exc:
        # Safe fallback: the built-in rules, with the reason shown.
        task.provider = "rules"
        task.error = str(exc)
        task.output = enforce_labels("\n".join([f"FACT: The AI service wasn't used ({exc}). Built-in rules were used instead."]
                                               + rules_out))
    return task


def decide(db: Session, task_id: int, approve: bool, actor: str | None, note: str = "") -> AITask:
    task = db.get(AITask, task_id)
    if task is None:
        raise ShopError("Not found", 404)
    if task.status != "draft":
        raise ShopError(f"Already {task.status}", 409)
    task.status = "approved" if approve else "rejected"
    task.decided_by, task.decided_at, task.decision_note = actor, _now(), note.strip()
    if approve:
        title = f"{AGENTS[task.agent].split(':')[0]}" + (f" ({task.subject})" if task.subject else "")
        db.add(BusinessDecision(title=title, decision=task.output[:4000], reason=note.strip(),
                                evidence=f"AI task #{task.id} via {task.provider}", ai_task_id=task.id,
                                decided_by=actor, created_at=_now()))
        key = f"{task.agent}:{task.subject or 'general'}"
        mem = db.get(AIMemory, key)
        summary = task.output.split(DRAFT_MARK)[0].strip()[:1500]
        if mem is None:
            db.add(AIMemory(key=key, value=summary, source=f"ai_task:{task.id}", updated_at=_now()))
        else:
            mem.value, mem.source, mem.updated_at = summary, f"ai_task:{task.id}", _now()
    return task


def add_decision(db: Session, title: str, decision: str, reason: str, evidence: str, actor: str | None) -> BusinessDecision:
    d = BusinessDecision(title=title.strip(), decision=decision.strip(), reason=reason.strip(),
                         evidence=evidence.strip(), decided_by=actor, created_at=_now())
    db.add(d)
    return d
