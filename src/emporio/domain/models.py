from decimal import Decimal
from pydantic import BaseModel

class Product(BaseModel):
    product_id: int
    name: str
    price: Decimal
    category_id: int
    stock_quantity: int
    status: str
    description: str | None
    specs: dict

class ActivePromotion(BaseModel):
    name: str
    discount_percent: Decimal

class ProductPricing(BaseModel):
    product_id: int
    name: str
    price_cents: int
    stock_quantity: int
    status: str
    active_promotion: ActivePromotion | None = None
