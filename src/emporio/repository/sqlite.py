import json
import sqlite3
from pathlib import Path
from emporio.domain.models import Product
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

    def order_customer_id(self, order_id: int) -> int | None:
        row = self.connection.execute('SELECT customer_id FROM orders WHERE order_id = ?', (order_id,)).fetchone()
        return row['customer_id'] if row else None

    def verify_order_contact(self, order_id: int, contact: tuple[str, str]) -> bool:
        from hmac import compare_digest
        from emporio.security.contacts import normalize_contact
        kind, expected = contact
        if kind not in ('email', 'phone'):
            return False
        owner_id = self.order_customer_id(order_id)
        # Percorrer toda a base impede que um contato compartilhado autorize qualquer cliente.
        customers = self.connection.execute('SELECT customer_id, email, phone FROM customers').fetchall()
        owners = []
        for customer in customers:
            normalized = normalize_contact(customer[kind])
            if normalized is not None and normalized[0] == kind and compare_digest(normalized[1].encode('utf-8'), expected.encode('utf-8')):
                owners.append(customer['customer_id'])
        return owner_id is not None and owners == [owner_id]

    def order_details(self, order_id: int) -> dict | None:
        import re
        row = self.connection.execute('''SELECT o.*, c.name AS customer_name FROM orders o
                                         JOIN customers c ON c.customer_id = o.customer_id WHERE o.order_id = ?''', (order_id,)).fetchone()
        if row is None:
            return None
        items = self.connection.execute('''SELECT p.product_id, p.name, i.quantity FROM order_items i
                                           JOIN products p ON p.product_id=i.product_id WHERE i.order_id = ? ORDER BY p.product_id''', (order_id,)).fetchall()
        notes = row['notes']
        # Dados livres não devem reproduzir contato nem nomes completos do cadastro.
        for customer in self.connection.execute('SELECT name, email, phone FROM customers'):
            for field in ('name', 'email', 'phone'):
                value = customer[field]
                if value:
                    notes = re.sub(re.escape(value), '[DADO REDIGIDO]', notes, flags=re.IGNORECASE)
        notes = re.sub(r'[^\s@]+@[^\s@]+\.[^\s@]+', '[EMAIL]', notes)
        notes = re.sub(r'(?<!\w)(?:\+?\d[\d ()-]{8,}\d)(?!\w)', '[TELEFONE]', notes)
        return {'order_id': row['order_id'], 'status': row['status'], 'order_date': row['order_date'],
                'items': [{'product_id': i['product_id'], 'name': i['name'], 'quantity': i['quantity']} for i in items],
                'total_brl': str(from_cents(row['total_cents'])), 'total_label': 'total registrado no pedido',
                'payment_method': row['payment_method'], 'tracking_code': row['tracking_code'],
                'estimated_delivery': row['estimated_delivery'], 'notes': notes,
                'first_name': row['customer_name'].split()[0]}
