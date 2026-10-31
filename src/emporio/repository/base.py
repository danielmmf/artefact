from typing import Protocol
from emporio.domain.models import Product, ProductPricing

class StoreRepository(Protocol):
    def get_product(self, product_id: int) -> Product | None: ...

    def get_product_pricing(self, product_id: int) -> ProductPricing | None: ...
