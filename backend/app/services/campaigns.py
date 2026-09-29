"""Per-campaign results (Blueprint section I): CTR, CPC, CAC, ROAS and contribution after ads.

Attribution is simple and honest: an order belongs to the campaign in the ad link the
buyer arrived through in that browser tab (last ad click, same session). Anything else
is "direct / unknown". Profit uses the product cost ESTIMATES until supplier quotes.
"""
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AdSpend, AnalyticsEvent, Order, Product
from . import admin

COUNTED = ("placed", "paid", "shipped")
DIRECT = "direct / unknown"
_PART = re.compile(r"[^a-z0-9._-]+")


def normalise(source: str | None, campaign: str | None) -> str | None:
    """'Facebook', 'Desk Reset Oct' -> 'facebook:desk-reset-oct'. None when there's no source."""
    src = _PART.sub("-", (source or "").strip().lower()).strip("-")[:60]
    if not src:
        return None
    name = _PART.sub("-", (campaign or "").strip().lower()).strip("-")[:60] or "none"
    return f"{src}:{name}"


def parse_tag(tag: str | None) -> str | None:
    """Accepts an already-normalised 'source:campaign' tag from the browser, re-normalised."""
    if not tag or ":" not in tag:
        return None
    src, _, name = tag.partition(":")
    return normalise(src, name)


def add_spend(db: Session, campaign: str, day: datetime, spend: int, clicks: int, impressions: int,
              note: str, actor: str | None) -> AdSpend:
    tag = parse_tag(campaign)
    if tag is None:
        raise ValueError("Use the same tag as the ad link, e.g. facebook:desk-reset")
    row = AdSpend(campaign=tag, day=day, spend=spend, clicks=clicks, impressions=impressions,
                  note=note.strip(), created_by=actor)
    db.add(row)
    return row


def _order_contribution(db: Session, order: Order, products: dict[str, Product]) -> int:
    total = 0
    for line in order.items:
        p = products.get(line.product_id)
        if p is not None:
            total += admin.economics(p, price=line.unit_price).contribution_pre_ads * line.quantity
    return total


def report(db: Session, days: int = 30) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows: dict[str, dict] = {}

    def row(tag: str) -> dict:
        return rows.setdefault(tag, {"campaign": tag, "spend": 0, "clicks": 0, "impressions": 0, "visits": 0,
                                     "orders": 0, "revenue": 0, "contribution_pre_ads": 0})

    for tag, spend, clicks, imps in db.execute(
        select(AdSpend.campaign, func.sum(AdSpend.spend), func.sum(AdSpend.clicks), func.sum(AdSpend.impressions))
        .where(AdSpend.day >= since).group_by(AdSpend.campaign)
    ):
        r = row(tag)
        r["spend"], r["clicks"], r["impressions"] = int(spend or 0), int(clicks or 0), int(imps or 0)

    for tag, n in db.execute(
        select(AnalyticsEvent.campaign, func.count()).where(
            AnalyticsEvent.type == "visit", AnalyticsEvent.created_at >= since, AnalyticsEvent.campaign.is_not(None))
        .group_by(AnalyticsEvent.campaign)
    ):
        row(tag)["visits"] = n

    products = {p.id: p for p in db.scalars(select(Product))}
    for o in db.scalars(select(Order).where(Order.status.in_(COUNTED), Order.created_at >= since)):
        r = row(o.campaign or DIRECT)
        r["orders"] += 1
        r["revenue"] += o.total
        r["contribution_pre_ads"] += _order_contribution(db, o, products)

    out = []
    for r in rows.values():
        spend, orders = r["spend"], r["orders"]
        r["ctr"] = round(r["clicks"] / r["impressions"], 4) if r["impressions"] else None
        r["cpc"] = round(spend / r["clicks"]) if r["clicks"] else None
        r["cac"] = round(spend / orders) if orders and spend else None
        r["roas"] = round(r["revenue"] / spend, 2) if spend else None
        r["contribution_after_ads"] = r["contribution_pre_ads"] - spend
        r["verdict"] = _verdict(r)
        out.append(r)
    out.sort(key=lambda r: (r["campaign"] == DIRECT, -r["spend"], r["campaign"]))
    totals = {k: sum(r[k] for r in out) for k in ("spend", "orders", "revenue", "contribution_pre_ads", "contribution_after_ads")}
    return {"days": days, "label": "ESTIMATE", "campaigns": out, "totals": totals}


def _verdict(r: dict) -> str:
    """Plain-English next step, following the blueprint's test rules. Advice only; nothing is changed."""
    if r["campaign"] == DIRECT or not r["spend"]:
        return ""
    if r["orders"] == 0:
        return "No sales yet. Check the ad and product page before spending more." if r["spend"] >= 3000 else "Too early to judge"
    if r["contribution_after_ads"] < 0:
        return "Losing money after ad cost. Pause it or fix the offer."
    if r["orders"] < 5:
        return "Profitable so far, but too few orders to be sure"
    return "Profitable after ad cost. Consider scaling slowly (about 20% more a week)."


def spend_rows(db: Session, limit: int = 100) -> list[AdSpend]:
    return list(db.scalars(select(AdSpend).order_by(AdSpend.day.desc(), AdSpend.id.desc()).limit(limit)))
