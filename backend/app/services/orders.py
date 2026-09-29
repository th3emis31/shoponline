"""Race-safe order state changes and stock bookkeeping.

Every change is a conditional UPDATE ("only if the order is still in state X"),
so two things happening at once (a webhook, the automation, an admin click,
two server processes) can never both apply. Stock moves only through
`release_stock` / `reserve_stock`, which flip the order's `stock_reserved`
flag first, so stock can't be released or reserved twice.

Callers commit (or roll back on error).
"""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import Order, OrderItem, Product
from .shop import ShopError


def move(db: Session, order_id: str, from_statuses: set[str] | tuple[str, ...], to_status: str, **values) -> bool:
    """Change status only if the order is still in one of `from_statuses`."""
    res = db.execute(
        update(Order)
        .where(Order.id == order_id, Order.status.in_(tuple(from_statuses)))
        .values(status=to_status, **values)
        .execution_options(synchronize_session="fetch")
    )
    return res.rowcount == 1


def _items(db: Session, order_id: str) -> list[OrderItem]:
    return list(db.scalars(select(OrderItem).where(OrderItem.order_id == order_id)))


def release_stock(db: Session, order_id: str) -> bool:
    """Put the order's items back in stock, at most once. Returns True if released."""
    res = db.execute(
        update(Order)
        .where(Order.id == order_id, Order.stock_reserved.is_(True))
        .values(stock_reserved=False)
        .execution_options(synchronize_session="fetch")
    )
    if res.rowcount != 1:
        return False
    for item in _items(db, order_id):
        db.execute(update(Product).where(Product.id == item.product_id)
                   .values(stock=Product.stock + item.quantity))
    return True


def reserve_stock(db: Session, order_id: str) -> bool:
    """Take the order's items out of stock again (e.g. a late payment accepted after
    review). All or nothing: raises ShopError(409) if any item is short; the
    caller must roll back. Returns False if stock was already reserved."""
    res = db.execute(
        update(Order)
        .where(Order.id == order_id, Order.stock_reserved.is_(False))
        .values(stock_reserved=True)
        .execution_options(synchronize_session="fetch")
    )
    if res.rowcount != 1:
        return False
    for item in _items(db, order_id):
        r = db.execute(update(Product)
                       .where(Product.id == item.product_id, Product.stock >= item.quantity)
                       .values(stock=Product.stock - item.quantity))
        if r.rowcount != 1:
            raise ShopError(f"Not enough stock for {item.name} to fulfil this order", 409)
    return True
