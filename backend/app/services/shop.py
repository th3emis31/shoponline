"""Cart, checkout and order logic. Raises ShopError with an HTTP status."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Cart, CartItem, Order, OrderItem, Product


class ShopError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def shipping_for(subtotal: int) -> int:
    if subtotal == 0 or subtotal >= settings.free_shipping_threshold:
        return 0
    return settings.shipping_fee


def get_cart(db: Session, cart_id: str) -> Cart:
    cart = db.get(Cart, cart_id)
    if cart is None:
        raise ShopError("Cart not found", 404)
    return cart


def cart_view(cart: Cart) -> dict:
    lines = [
        {
            "product_id": i.product_id,
            "name": i.product.name,
            "unit_price": i.product.price,
            "quantity": i.quantity,
            "line_total": i.product.price * i.quantity,
        }
        for i in cart.items
    ]
    subtotal = sum(line["line_total"] for line in lines)
    shipping = shipping_for(subtotal)
    return {"id": cart.id, "items": lines, "subtotal": subtotal,
            "shipping": shipping, "total": subtotal + shipping}


def create_cart(db: Session) -> Cart:
    cart = Cart()
    db.add(cart)
    db.commit()
    return cart


def add_item(db: Session, cart_id: str, product_id: str, quantity: int) -> Cart:
    cart = get_cart(db, cart_id)
    product = db.get(Product, product_id)
    if product is None or not product.active:
        raise ShopError("Product not found", 404)
    item = next((i for i in cart.items if i.product_id == product_id), None)
    new_qty = (item.quantity if item else 0) + quantity
    if new_qty > settings.max_qty_per_item:
        raise ShopError(f"Maximum {settings.max_qty_per_item} per item")
    if new_qty > product.stock:
        raise ShopError("Not enough stock", 409)
    if item:
        item.quantity = new_qty
    else:
        cart.items.append(CartItem(product_id=product_id, quantity=quantity))
    db.commit()
    db.refresh(cart)
    return cart


def remove_item(db: Session, cart_id: str, product_id: str) -> Cart:
    cart = get_cart(db, cart_id)
    cart.items = [i for i in cart.items if i.product_id != product_id]
    db.commit()
    db.refresh(cart)
    return cart


def checkout(db: Session, cart_id: str, name: str, email: str, address: str,
             status: str = "placed", delete_cart: bool = True) -> Order:
    cart = get_cart(db, cart_id)
    view = cart_view(cart)
    if not view["items"]:
        raise ShopError("Cart is empty")

    try:
        # Atomic conditional decrement: never oversells, even under concurrency.
        for line in view["items"]:
            result = db.execute(
                update(Product)
                .where(Product.id == line["product_id"], Product.stock >= line["quantity"],
                       Product.active.is_(True))
                .values(stock=Product.stock - line["quantity"])
            )
            if result.rowcount != 1:
                raise ShopError(f"Not enough stock for {line['name']}", 409)

        order = Order(
            status=status, customer_name=name, customer_email=email, shipping_address=address,
            subtotal=view["subtotal"], shipping=view["shipping"], total=view["total"],
            items=[OrderItem(product_id=l["product_id"], name=l["name"],
                             unit_price=l["unit_price"], quantity=l["quantity"])
                   for l in view["items"]],
        )
        db.add(order)
        if delete_cart:
            db.delete(cart)
        db.commit()
    except Exception:
        db.rollback()  # all-or-nothing: no partial stock deduction
        raise
    return order


def order_view(order: Order) -> dict:
    lines = [{"product_id": i.product_id, "name": i.name, "unit_price": i.unit_price,
              "quantity": i.quantity, "line_total": i.unit_price * i.quantity}
             for i in order.items]
    return {"id": order.id, "status": order.status, "items": lines,
            "subtotal": order.subtotal, "shipping": order.shipping,
            "total": order.total, "created_at": order.created_at}


def list_products(db: Session) -> list[Product]:
    return list(db.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.price)))
