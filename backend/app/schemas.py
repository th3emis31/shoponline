from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ProductOut(BaseModel):
    """Public product view: internal cost fields are deliberately absent."""

    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    price: int
    is_bundle: bool
    in_stock: bool


class AddItemIn(BaseModel):
    product_id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(default=1, ge=1, le=99)


class CartLineOut(BaseModel):
    product_id: str
    name: str
    unit_price: int
    quantity: int
    line_total: int


class CartOut(BaseModel):
    id: str
    items: list[CartLineOut]
    subtotal: int
    shipping: int
    total: int


class CheckoutIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    address: str = Field(min_length=1, max_length=500)

    @field_validator("name", "address")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class OrderOut(BaseModel):
    id: str
    status: str
    items: list[CartLineOut]
    subtotal: int
    shipping: int
    total: int
    created_at: datetime


class EconomicsOut(BaseModel):
    product_id: str
    label: str = "ESTIMATE"
    net_revenue: int
    payment_fee: int
    returns_allowance: int
    contribution_pre_ads: int
    contribution_margin: float
    break_even_roas: float | None
    contribution_post_ads: int
