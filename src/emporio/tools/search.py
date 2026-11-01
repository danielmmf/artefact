from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from emporio.money import from_cents, to_cents
from emporio.repository.base import StoreRepository
from emporio.rules.pricing import discounted_cents
from emporio.tools.contracts import ToolError, ToolResult
from emporio.tools.product import availability

class SearchInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=100, description='Categoria do catálogo: Guitarras, Baixos, Baterias e Percussão, Teclados e Pianos, Violões, Ukuleles (singular ou plural). Omita se não tiver certeza.')
    min_price: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False, max_digits=12, decimal_places=2)
    max_price: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False, max_digits=12, decimal_places=2)
    only_available: bool = Field(default=True, strict=True)
    limit: int = Field(default=5, ge=1, le=50, strict=True)
    @model_validator(mode='after')
    def validate_ranges(self):
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError('Faixa inválida')
        return self

def search_products(repository: StoreRepository, args: dict) -> ToolResult:
    try:
        request = SearchInput.model_validate(args)
    except ValidationError:
        return ToolResult(ok=False, error=ToolError(code='invalid_input', message_for_agent='Filtros de busca inválidos.'))
    query = request.query.strip() if request.query else None
    category = request.category.strip() if request.category else None
    ids, backend = repository.search_product_ids(query, category, to_cents(request.min_price) if request.min_price is not None else None, to_cents(request.max_price) if request.max_price is not None else None, request.only_available)
    results = []
    for id_ in ids[:request.limit]:
        product = repository.get_product(id_)
        pricing = repository.get_product_pricing(id_)
        if product is None or pricing is None:
            raise RuntimeError('Resultado do índice sem produto correspondente')
        promo = pricing.active_promotion
        final = discounted_cents(pricing.price_cents, promo.discount_percent) if promo else pricing.price_cents
        results.append({'product_id': id_, 'name': product.name, 'category': repository.category_name(product.category_id),
                        'availability': availability(product.status, product.stock_quantity), 'stock_quantity': product.stock_quantity,
                        'price_info': {'list_price': str(from_cents(pricing.price_cents)), 'final_price': str(from_cents(final)),
                                       'active_promotion': promo.model_dump(mode='json') if promo else None}})
    return ToolResult(ok=True, data={'products': results, 'total_matches': len(ids), 'search_backend': backend})
