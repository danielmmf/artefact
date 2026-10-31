from typing import Protocol
from emporio.domain.models import Product

class StoreRepository(Protocol):
    def get_product(self, product_id: int) -> Product | None: ...
