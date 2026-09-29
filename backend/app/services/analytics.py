"""Anonymous conversion funnel (Blueprint sections I and O).

Only the event type, an optional product ID and a timestamp are stored:
no cookies, no visitor IDs, no personal data, so no consent banner is
needed for it. Purchases are recorded server-side, never by the browser.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AnalyticsEvent

CLIENT_EVENTS = ("view_product", "add_to_cart", "begin_checkout")
FUNNEL = (*CLIENT_EVENTS, "purchase")
# "visit" = arrived through an ad link; stores only the campaign tag, for per-campaign results.
OTHER_EVENTS = ("visit",)


def record(db: Session, event_type: str, product_id: str | None = None, commit: bool = True,
           campaign: str | None = None) -> None:
    if event_type not in FUNNEL and event_type not in OTHER_EVENTS:
        raise ValueError(f"Unknown event type: {event_type}")
    db.add(AnalyticsEvent(type=event_type, product_id=product_id, campaign=campaign))
    if commit:
        db.commit()


def funnel(db: Session, days: int = 30) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(AnalyticsEvent.type, func.count())
        .where(AnalyticsEvent.created_at >= since)
        .group_by(AnalyticsEvent.type)
    ).all()
    counts = {t: 0 for t in FUNNEL}
    counts.update({t: n for t, n in rows if t in counts})
    steps = []
    prev = None
    for t in FUNNEL:
        rate = round(counts[t] / counts[prev], 4) if prev and counts[prev] else None
        steps.append({"type": t, "count": counts[t], "rate_from_previous": rate})
        prev = t
    first = counts[FUNNEL[0]]
    overall = round(counts["purchase"] / first, 4) if first else None
    return {"days": days, "steps": steps, "overall_conversion": overall}
