from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from emporio.money import from_cents
from emporio.repository.base import StoreRepository
from emporio.rules.pricing import discounted_cents, may_require_special_quote
from emporio.tools.contracts import ToolError, ToolResult

class GetProductInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_id: int | None = Field(default=None, gt=0, le=9223372036854775807, strict=True)
    name: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode='after')
    def exactly_one(self):
        if (self.product_id is None) == (self.name is None) or (self.name is not None and not self.name.strip()):
            raise ValueError('Informe id ou nome')
        return self

def availability(status: str, stock: int) -> str:
    if status == 'discontinued': return 'discontinued'
    if status == 'coming_soon': return 'coming_soon'
    return 'available' if stock > 0 else 'out_of_stock'

def get_product(repository: StoreRepository, args: dict) -> ToolResult:
    try:
        parsed = GetProductInput.model_validate(args)
    except ValidationError:
        return ToolResult(ok=False, error=ToolError(code='invalid_input', message_for_agent='Identificador ou nome inválido.'))
    product_id = parsed.product_id
    if parsed.name is not None:
        candidates = repository.find_product_names(parsed.name)
        if len(candidates) > 1:
            return ToolResult(ok=False, error=ToolError(code='ambiguous', message_for_agent='Informe qual produto deseja.', candidates=[{'product_id': i, 'name': n} for i, n in candidates]))
        product_id = candidates[0][0] if candidates else None
    product = repository.get_product(product_id) if product_id is not None else None
    if product is None:
        return ToolResult(ok=False, error=ToolError(code='not_found', message_for_agent='Produto não encontrado.'))
    pricing = repository.get_product_pricing(product.product_id)
    if pricing is None:
        return ToolResult(ok=False, error=ToolError(code='internal_error', message_for_agent='Não foi possível consultar o produto.'))
    promo = pricing.active_promotion
    final_cents = discounted_cents(pricing.price_cents, promo.discount_percent) if promo else pricing.price_cents
    status = availability(product.status, product.stock_quantity)
    alternatives = repository.product_alternatives(product.product_id, product.category_id, pricing.price_cents) if status in {'out_of_stock', 'discontinued'} else []
    data = product.model_dump(mode='json')
    data.update({
        'availability': status,
        'price_info': {'list_price': str(from_cents(pricing.price_cents)), 'final_price': str(from_cents(final_cents)), 'active_promotion': promo.model_dump(mode='json') if promo else None},
        'inactive_promotions': repository.inactive_promotions(product.product_id),
        'alternatives': [{'product_id': p.product_id, 'name': p.name, 'price': str(p.price), 'availability': availability(p.status, p.stock_quantity)} for p in alternatives],
        'special_quote_required': may_require_special_quote(product.product_id),
        'special_quote_note': 'Pode exigir cotação especial.' if may_require_special_quote(product.product_id) else None,
    })
    return ToolResult(ok=True, data=data)
