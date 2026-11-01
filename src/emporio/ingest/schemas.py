from datetime import date
from decimal import Decimal
from typing import Literal
import json
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Row(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Category(Row):
    category_id: int = Field(gt=0)
    name: str = Field(min_length=1)
    description: str

class Customer(Row):
    customer_id: int = Field(gt=0)
    name: str = Field(min_length=1)
    phone: str
    email: str
    city: str

class Product(Row):
    product_id: int = Field(gt=0)
    price_brl: Decimal = Field(ge=0, allow_inf_nan=False)
    name: str = Field(min_length=1)
    category_id: int = Field(gt=0)
    description: str
    stock_quantity: int = Field(ge=0)
    status: Literal['active', 'discontinued', 'coming_soon']
    specs: dict
    created_at: date
    @field_validator('specs', mode='before')
    @classmethod
    def parse_specs(cls, v):
        return json.loads(v) if isinstance(v, str) else v
    @field_validator('price_brl')
    @classmethod
    def exact_cents(cls, v):
        if v * 100 != (v * 100).to_integral_value():
            raise ValueError('preço exige fração de centavo')
        return v

class Order(Row):
    order_id: int = Field(gt=0)
    customer_id: int = Field(gt=0)
    order_date: date
    status: Literal['pending', 'confirmed', 'shipped', 'delivered', 'cancelled']
    total_brl: Decimal = Field(ge=0, allow_inf_nan=False)
    payment_method: str
    tracking_code: str
    estimated_delivery: str
    notes: str
    @field_validator('total_brl')
    @classmethod
    def exact_cents(cls, v):
        if v * 100 != (v * 100).to_integral_value():
            raise ValueError('total exige fração de centavo')
        return v

class OrderItem(Row):
    order_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    product_id: int = Field(gt=0)

class Promotion(Row):
    promotion_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    discount_percent: Decimal = Field(ge=0, le=100, allow_inf_nan=False)
    description: str
    is_active: Literal[0, 1]
    @field_validator('is_active', mode='before')
    @classmethod
    def parse_active(cls, v):
        if v not in ('0', '1', 0, 1):
            raise ValueError('is_active inválido')
        return int(v)
