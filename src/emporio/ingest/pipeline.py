import csv
import json
import re
import sqlite3
import tempfile
from pathlib import Path
from pypdf import PdfReader
from emporio.ingest.schemas import Category, Customer, Order, OrderItem, Product, Promotion
from emporio.money import to_cents

SCHEMAS = {'categories': Category, 'customers': Customer, 'products': Product, 'orders': Order, 'order_items': OrderItem, 'promotions': Promotion}
DDL = '''
CREATE TABLE categories(category_id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL);
CREATE TABLE customers(customer_id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL, email TEXT NOT NULL, city TEXT NOT NULL);
CREATE TABLE products(product_id INTEGER PRIMARY KEY, price_cents INTEGER NOT NULL, name TEXT NOT NULL, category_id INTEGER NOT NULL REFERENCES categories, description TEXT NOT NULL, stock_quantity INTEGER NOT NULL, status TEXT NOT NULL, specs TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE orders(order_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers, order_date TEXT NOT NULL, status TEXT NOT NULL, total_cents INTEGER NOT NULL, payment_method TEXT NOT NULL, tracking_code TEXT NOT NULL, estimated_delivery TEXT NOT NULL, notes TEXT NOT NULL);
CREATE TABLE order_items(order_id INTEGER NOT NULL REFERENCES orders, quantity INTEGER NOT NULL, product_id INTEGER NOT NULL REFERENCES products, PRIMARY KEY(order_id,product_id));
CREATE TABLE promotions(promotion_id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products, discount_percent TEXT NOT NULL, description TEXT NOT NULL, is_active INTEGER NOT NULL);
CREATE UNIQUE INDEX one_active_promotion ON promotions(product_id) WHERE is_active=1;
'''

def locate(raw: Path, name: str) -> Path:
    candidates = [p for p in raw.glob('*.csv') if re.search(r'(?:^|[-_\s])' + re.escape(name) + r'\s*\.csv$', p.name, re.I)]
    if len(candidates) != 1:
        raise ValueError(f'CSV {name}: esperado um arquivo, encontrados {len(candidates)}')
    return candidates[0]

def read_rows(raw: Path) -> dict:
    data = {}
    for table, schema in SCHEMAS.items():
        with locate(raw, table).open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or set(reader.fieldnames) != set(schema.model_fields):
                raise ValueError(f'Cabeçalho inválido: {table}')
            rows = []
            for line, row in enumerate(reader, 2):
                try:
                    rows.append(schema.model_validate(row))
                except Exception as exc:
                    raise ValueError(f'Linha inválida: {table}:{line}') from exc
            data[table] = rows
    return data

def policies(pdf: Path) -> str:
    pages = PdfReader(pdf).pages
    if len(pages) != 8:
        raise ValueError('Manual deve ter 8 páginas')
    out = []
    section = 'capa'
    found = set()
    for n, page in enumerate(pages, 1):
        content = page.extract_text(extraction_mode='layout')
        if not content or not content.strip():
            raise ValueError(f'Página {n} sem texto extraível')
        out.append(f'[§{section} · p.{n}]\n')
        for line in content.splitlines():
            match = re.match(r'^(10|[1-9])(?:\.(\d+))?\.?(?:\s+)(\S.*)$', line)
            if match:
                section = match.group(1) + ('.' + match.group(2) if match.group(2) else '')
                found.add(match.group(1))
                out.append(f'\n[§{section} · p.{n}]')
            out.append(line)
        out.append('\n')
    if found != set(map(str, range(1, 11))):
        raise ValueError(f'Seções ausentes: {set(map(str, range(1, 11))) - found}')
    return '\n'.join(out).rstrip() + '\n'

def ingest(raw: Path, database: Path, processed: Path, adr: Path) -> None:
    data = read_rows(raw)
    pdfs = list(raw.glob('*.pdf'))
    if len(pdfs) != 1:
        raise ValueError('Esperado exatamente um PDF')
    text = policies(pdfs[0])
    # O relatório reproduz fatos já auditados na ADR; não inclui inferências novas.
    source = adr.read_text(encoding='utf-8')
    quality = '# Qualidade dos dados\n\nFatos documentados na ADR-000 §13; confira novamente quando os dados de origem mudarem.\n\n' + source.split('## 13. Inconsistências conhecidas dos dados\n', 1)[1].split('\n## 14.', 1)[0].strip() + '\n'
    database.parent.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=database.parent) as temp:
        target = Path(temp) / 'store.db'
        with sqlite3.connect(target) as con:
            con.execute('PRAGMA foreign_keys=ON')
            con.executescript(DDL)
            for table, rows in data.items():
                for row in rows:
                    values = row.model_dump(mode='json')
                    if 'price_brl' in values:
                        values['price_cents'] = to_cents(values.pop('price_brl'))
                    if 'total_brl' in values:
                        values['total_cents'] = to_cents(values.pop('total_brl'))
                    if 'specs' in values:
                        values['specs'] = json.dumps(values['specs'], ensure_ascii=False, sort_keys=True)
                    names = list(values)
                    con.execute(f"INSERT INTO {table} ({','.join(names)}) VALUES ({','.join('?' for _ in names)})", list(values.values()))
            if con.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Integridade referencial inválida')
        target.replace(database)
    (processed / 'policies.md').write_text(text, encoding='utf-8')
    (processed / 'QUALITY.md').write_text(quality, encoding='utf-8')
