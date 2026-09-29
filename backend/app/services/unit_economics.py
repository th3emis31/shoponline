"""Unit economics model (NOVAHAUS Blueprint section L).

All inputs and outputs are in pence. Revenue is ex-VAT so the model still
holds once the business is VAT-registered. Cost inputs are ESTIMATES until
supplier quotes replace them.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

VAT_RATE = Decimal("0.20")
STRIPE_UK_PERCENT = Decimal("0.015")  # FACT: Stripe UK cards 1.5% + 20p
STRIPE_UK_FIXED = Decimal("20")
RETURN_LABEL = Decimal("400")  # ASSUMPTION: £4 return label
DEFAULT_RETURN_RATE = Decimal("0.05")  # ASSUMPTION


def _pence(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class UnitEconomics:
    net_revenue: int
    payment_fee: int
    returns_allowance: int
    contribution_pre_ads: int
    contribution_margin: float
    break_even_roas: float | None  # None when contribution <= 0 (never profitable)
    contribution_post_ads: int


def payment_fee(price_inc_vat: int) -> Decimal:
    return Decimal(price_inc_vat) * STRIPE_UK_PERCENT + STRIPE_UK_FIXED


def calculate(
    price: int,
    landed_cost: int,
    shipping: int,
    packaging: int,
    return_rate: Decimal | float = DEFAULT_RETURN_RATE,
    cac: int = 0,
) -> UnitEconomics:
    values = {"price": price, "landed_cost": landed_cost, "shipping": shipping,
              "packaging": packaging, "cac": cac}
    for name, v in values.items():
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise ValueError(f"{name} must be a non-negative integer (pence)")
    rate = Decimal(str(return_rate))
    if not Decimal(0) <= rate <= Decimal(1):
        raise ValueError("return_rate must be between 0 and 1")

    net_revenue = Decimal(price) / (1 + VAT_RATE)
    fee = payment_fee(price)
    returns_allowance = rate * (Decimal(shipping) + Decimal(landed_cost) / 2 + RETURN_LABEL)
    cm = net_revenue - landed_cost - shipping - packaging - fee - returns_allowance

    return UnitEconomics(
        net_revenue=_pence(net_revenue),
        payment_fee=_pence(fee),
        returns_allowance=_pence(returns_allowance),
        contribution_pre_ads=_pence(cm),
        contribution_margin=float(cm / net_revenue) if net_revenue > 0 else 0.0,
        break_even_roas=float(Decimal(price) / cm) if cm > 0 else None,
        contribution_post_ads=_pence(cm - cac),
    )
