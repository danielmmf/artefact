import json
import sqlite3
from pathlib import Path
from emporio.domain.models import ActivePromotion, Product, ProductPricing
from emporio.money import from_cents

class SQLiteRepository:
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro', uri=True)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA query_only=ON')

    def close(self) -> None:
        self.connection.close()

    def get_product(self, product_id: int) -> Product | None:
        row = self.connection.execute('SELECT * FROM products WHERE product_id = ?', (product_id,)).fetchone()
        if row is None:
            return None
        return Product(product_id=row['product_id'], name=row['name'], price=from_cents(row['price_cents']), category_id=row['category_id'], stock_quantity=row['stock_quantity'], status=row['status'], description=None if product_id in {135,136,137,139,140,142,144} else row['description'], specs=json.loads(row['specs']))

    def get_product_pricing(self, product_id: int) -> ProductPricing | None:
        row = self.connection.execute(
            """SELECT p.product_id, p.name, p.price_cents, p.stock_quantity, p.status,
                      promo.description AS promotion_name, promo.discount_percent
               FROM products AS p
               LEFT JOIN promotions AS promo ON promo.product_id = p.product_id AND promo.is_active = 1
               WHERE p.product_id = ?""", (product_id,)
        ).fetchone()
        if row is None:
            return None
        promotion = (ActivePromotion(name=row['promotion_name'], discount_percent=row['discount_percent'])
                     if row['discount_percent'] is not None else None)
        return ProductPricing(product_id=row['product_id'], name=row['name'], price_cents=row['price_cents'],
                              stock_quantity=row['stock_quantity'], status=row['status'], active_promotion=promotion)

    def find_product_names(self, name: str) -> list[tuple[int, str]]:
        import unicodedata
        def normalize(value: str) -> str:
            return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c))
        query = normalize(name.strip())
        rows = self.connection.execute('SELECT product_id, name FROM products ORDER BY product_id').fetchall()
        matches = [(row['product_id'], row['name']) for row in rows if query in normalize(row['name'])]
        exact = [candidate for candidate in matches if normalize(candidate[1]) == query]
        return exact or matches

    def inactive_promotions(self, product_id: int) -> list[dict]:
        rows = self.connection.execute('SELECT description, discount_percent FROM promotions WHERE product_id = ? AND is_active = 0 ORDER BY promotion_id', (product_id,)).fetchall()
        return [{'name': row['description'], 'discount_percent': row['discount_percent']} for row in rows]

    def product_alternatives(self, product_id: int, category_id: int, price_cents: int, limit: int = 3) -> list[Product]:
        rows = self.connection.execute('''SELECT product_id FROM products WHERE category_id = ? AND product_id != ?
            AND status = 'active' AND stock_quantity > 0 ORDER BY ABS(price_cents - ?), product_id LIMIT ?''',
            (category_id, product_id, price_cents, limit)).fetchall()
        return [self.get_product(row['product_id']) for row in rows]
