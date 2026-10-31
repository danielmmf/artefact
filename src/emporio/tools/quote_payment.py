"""Cotação de produtos atuais; não registra ou confirma compras."""
import sqlite3
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from emporio.money import from_cents
from emporio.repository.base import StoreRepository
from emporio.rules.pricing import CartItem, combined_payment_allowed, installment_options, price_cart, quote_shipping
from emporio.tools.contracts import ToolError, ToolResult


class QuoteItemInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_id: int = Field(gt=0, le=9223372036854775807, strict=True)
    quantity: int = Field(gt=0, strict=True)


class QuotePaymentInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    items: list[QuoteItemInput] = Field(min_length=1)
    destination_city: str | None = None

    @model_validator(mode='after')
    def unique_products(self):
        ids = [item.product_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError('Produtos duplicados')
        return self


def _quote_payment(repository: StoreRepository, args: dict) -> ToolResult:
    try:
        request = QuotePaymentInput.model_validate(args)
    except ValidationError:
        return ToolResult(ok=False, error=ToolError(code='invalid_input', message_for_agent='Dados da cotação inválidos.'))

    products = []
    cart_items = []
    for item in request.items:
        product = repository.get_product_pricing(item.product_id)
        if product is None:
            return ToolResult(ok=False, error=ToolError(code='not_found', message_for_agent='Produto não encontrado.'))
        products.append(product)
        cart_items.append(CartItem(product.product_id, item.quantity, product.price_cents,
                                   product.stock_quantity, product.status,
                                   product.active_promotion.discount_percent if product.active_promotion else None))

    cart = price_cart(cart_items)
    lines = []
    for product, line in zip(products, cart.items):
        lines.append({
            'product_id': line.product_id, 'name': product.name, 'quantity': line.quantity,
            'status': 'purchasable' if line.purchasable else 'not_purchasable', 'reason': line.reason,
            'list_price': from_cents(line.unit_original_cents),
            'final_price': from_cents(line.unit_final_cents) if line.unit_final_cents is not None else None,
            'active_promotion': product.active_promotion.model_dump() if product.active_promotion else None,
            'pix_eligible': line.purchasable and product.active_promotion is None,
            'pix_price': from_cents(line.unit_pix_cents) if line.unit_pix_cents is not None else None,
            'subtotal': from_cents(line.final_total_cents), 'pix_subtotal': from_cents(line.pix_total_cents),
            'special_quote_required': line.special_quote_possible,
            'special_quote_note': 'Pode exigir cotação especial.' if line.special_quote_possible else None,
        })
    shipping = quote_shipping(cart, request.destination_city)
    has_purchasable = any(line.purchasable for line in cart.items)
    if not has_purchasable:
        shipping_data = None
        installments = []
        combination = False
    else:
        region = 'unknown' if shipping.needs_destination else 'metro' if shipping.cost_cents is not None else 'other'
        shipping_data = {
            'region': region,
            'fee': from_cents(shipping.cost_cents) if shipping.cost_cents is not None else None,
            'free': shipping.cost_cents == 0 if shipping.cost_cents is not None else None,
            'rule_ref': '§5.1' if region == 'metro' else '§5.2' if region == 'other' else None,
            'modalities': [{'name': m.name, 'business_days_min': m.business_days_min,
                            'business_days_max': m.business_days_max} for m in shipping.methods],
            # O nome do contrato é histórico: True significa apenas que pode exigir cotação.
            'special_quote_required': shipping.special_quote_possible,
            'special_quote_note': 'Pode exigir cotação especial.' if shipping.special_quote_possible else None,
        }
        installments = [{'n': option.count, 'valor': from_cents(option.amounts_cents[0]),
                         'amounts': [from_cents(amount) for amount in option.amounts_cents],
                         'valid': option.valid, 'reason': option.reason}
                        for option in installment_options(cart.subtotal_cents)]
        combination = combined_payment_allowed(cart.subtotal_cents)

    result = {
        'items': lines,
        'subtotal': from_cents(cart.subtotal_cents), 'pix_subtotal': from_cents(cart.pix_subtotal_cents),
        'total_with_shipping': from_cents(cart.subtotal_cents + shipping.cost_cents) if has_purchasable and shipping.cost_cents is not None else None,
        'pix_total_with_shipping': from_cents(cart.pix_subtotal_cents + shipping.cost_cents) if has_purchasable and shipping.cost_cents is not None else None,
        'installments': installments, 'installments_basis': 'subtotal de produtos, sem frete',
        'combined_payment_allowed': combination, 'combined_payment_basis': 'subtotal de produtos, sem frete',
        'shipping': shipping_data,
    }
    return ToolResult(ok=True, data=result)


def quote_payment(repository: StoreRepository, args: dict) -> ToolResult:
    try:
        return _quote_payment(repository, args)
    except sqlite3.Error:
        return ToolResult(ok=False, error=ToolError(code='internal_error', message_for_agent='Não foi possível consultar a cotação.'))
