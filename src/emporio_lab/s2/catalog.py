"""Gerador determinístico do catálogo sintético do S2, a partir de ATRIBUTOS ESTRUTURADOS.

Cada produto nasce de (categoria, tipo, nível, uso, faixa de preço, disponibilidade); nome e descrição são derivados dos atributos.
O produto i depende só de (seed, bloco da série), então o catálogo de 5.000 é o prefixo do de 50.000 (as consultas por nome valem nos dois).
Nada daqui é lido da base original de 65 produtos.
"""
import hashlib
import json
import random
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from emporio_lab.s2 import lexicon as lx

FIRST_ID = 1001
SYNTHETIC = 'SINTÉTICO'
SCHEMA = '''
CREATE TABLE categories(category_id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL);
CREATE TABLE customers(customer_id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL, email TEXT NOT NULL, city TEXT NOT NULL);
CREATE TABLE products(product_id INTEGER PRIMARY KEY, price_cents INTEGER NOT NULL, name TEXT NOT NULL, category_id INTEGER NOT NULL REFERENCES categories, description TEXT NOT NULL, stock_quantity INTEGER NOT NULL, status TEXT NOT NULL, specs TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE orders(order_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers, order_date TEXT NOT NULL, status TEXT NOT NULL, total_cents INTEGER NOT NULL, payment_method TEXT NOT NULL, tracking_code TEXT NOT NULL, estimated_delivery TEXT NOT NULL, notes TEXT NOT NULL);
CREATE TABLE order_items(order_id INTEGER NOT NULL REFERENCES orders, quantity INTEGER NOT NULL, product_id INTEGER NOT NULL REFERENCES products, PRIMARY KEY(order_id,product_id));
CREATE TABLE promotions(promotion_id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products, discount_percent TEXT NOT NULL, description TEXT NOT NULL, is_active INTEGER NOT NULL);
CREATE UNIQUE INDEX one_active_promotion ON promotions(product_id) WHERE is_active=1;
'''
FTS_DDL = "CREATE VIRTUAL TABLE products_fts USING fts5(name, description, category, tokenize='unicode61 remove_diacritics 2');"
TYPE_INDEX = {t[0]: i for i, t in enumerate(lx.TYPES)}
TYPES_BY_CATEGORY = {c: [t for t in lx.TYPES if t[1] == c] for c in lx.CATEGORIES}


@dataclass
class Product:
    product_id: int
    name: str
    description: str
    category_id: int
    price_cents: int
    stock: int
    status: str
    promo_percent: int | None
    attrs: dict            # category, type, level, use, tier, brand, series, finish (códigos inteiros ou texto), use_in_text, level_in_text


def _series_block(rng: random.Random, series_index: int, next_id: int, brand_series_seen: set) -> list[Product]:
    category = rng.choices(list(lx.CATEGORIES), weights=(14, 10, 10, 12, 18, 10, 8, 8, 10))[0]
    ptype = rng.choice(TYPES_BY_CATEGORY[category])
    brand = rng.choice(lx.BRANDS)
    while True:
        code = f'{rng.choice("ABCDEFGHJKLMNPRSTVXZ")}{rng.choice("ABCDEFGHJKLMNPRSTVXZ")}-{rng.randrange(10, 100)}'
        if (brand, code) not in brand_series_seen:
            brand_series_seen.add((brand, code))
            break
    level = rng.choices(lx.LEVELS, weights=(35, 30, 22, 13))[0]
    tier = min(3, max(0, lx.LEVELS.index(level) + rng.choice((-1, 0, 0, 1))))   # nível e preço correlacionam, mas não coincidem
    variants = rng.randint(2, 8)
    finishes = rng.sample(lx.FINISHES, variants)
    products = []
    for finish in finishes:
        use = rng.choice(ptype[4])
        use_text = rng.random() > 0.08          # 8% das descrições não dizem o uso; 8% não dizem o nível (ruído realista)
        level_text = rng.random() > 0.08
        name = f'{brand} {code} {ptype[2].capitalize() if ptype[2][0].islower() else ptype[2]} {finish}'
        parts = [f'{ptype[2].capitalize()} {brand} série {code} no acabamento {finish.lower()}.']
        if level_text:
            parts.append(rng.choice(lx.LEVEL_DESC[level]).capitalize() + '.')
        if use_text:
            parts.append(rng.choice(lx.USE_DESC[use]).capitalize() + '.')
        parts.append(rng.choice(lx.BLURBS[category]))
        parts.append(rng.choice(lx.TIER_DESC[lx.TIER_NAMES[tier]]).capitalize() + '.')
        parts.append(rng.choice(lx.NOISE))
        price = lx.BASE_PRICE[category] * lx.TIER_MULT[tier] * rng.lognormvariate(0, 0.25)
        price_cents = int(round(price / 1000)) * 1000 - 10          # termina em ,90
        roll = rng.random()
        status, stock = ('active', rng.randint(1, 40)) if roll < 0.70 else (('active', 0) if roll < 0.85 else ('discontinued', 0))
        promo = rng.choice((5, 10, 15, 20, 30)) if rng.random() < 0.06 else None
        products.append(Product(next_id + len(products), name, ' '.join(parts), category, max(price_cents, 1990), stock, status, promo,
                                {'category': category, 'type': TYPE_INDEX[ptype[0]], 'level': lx.LEVELS.index(level), 'use': lx.USES.index(use),
                                 'tier': tier, 'brand': lx.BRANDS.index(brand), 'series': f'{brand} {code}', 'finish': lx.FINISHES.index(finish),
                                 'level_in_text': level_text, 'use_in_text': use_text}))
    return products


def generate(n: int, seed: int) -> list[Product]:
    """Os n primeiros produtos do fluxo determinístico (a última série pode ser truncada)."""
    rng = random.Random(seed)
    seen: set = set()
    out: list[Product] = []
    index = 0
    while len(out) < n:
        out.extend(_series_block(rng, index, FIRST_ID + len(out), seen))
        index += 1
    return out[:n]


def catalog_hash(products: list[Product]) -> str:
    h = hashlib.sha256()
    for p in products:
        h.update(json.dumps([p.product_id, p.name, p.description, p.category_id, p.price_cents, p.stock, p.status, p.promo_percent, p.attrs],
                            ensure_ascii=False, sort_keys=True).encode('utf-8'))
    return h.hexdigest()


def build_sqlite(products: list[Product], path: Path) -> dict:
    """Cria a base sintética com o MESMO esquema e o mesmo FTS5 da v1 (ingest/pipeline.py). Retorna tempos."""
    import time
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    t0 = time.perf_counter()
    con.executescript(SCHEMA)
    con.executemany('INSERT INTO categories VALUES (?,?,?)', [(i, n, lx.CATEGORY_DESCRIPTIONS[i]) for i, n in lx.CATEGORIES.items()])
    con.executemany('INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?)',
                    [(p.product_id, p.price_cents, p.name, p.category_id, p.description, p.stock, p.status,
                      json.dumps({'sintetico': True, **{k: v for k, v in p.attrs.items() if k in ('series',)}}, ensure_ascii=False), '2026-01-01') for p in products])
    con.executemany('INSERT INTO promotions(product_id, discount_percent, description, is_active) VALUES (?,?,?,1)',
                    [(p.product_id, str(p.promo_percent), 'Promoção sintética', ) for p in products if p.promo_percent])
    con.commit()
    t_rows = time.perf_counter() - t0
    t1 = time.perf_counter()
    con.execute(FTS_DDL)
    con.execute('INSERT INTO products_fts(rowid, name, description, category) SELECT p.product_id, p.name, p.description, c.name FROM products p JOIN categories c ON c.category_id = p.category_id')
    con.commit()
    con.execute('VACUUM')
    con.close()
    return {'inserir_linhas_s': round(t_rows, 3), 'indice_fts5_s': round(time.perf_counter() - t1, 3), 'bytes': path.stat().st_size}


def document_text(name: str, description: str, category: str) -> str:
    """Texto indexado nos três mecanismos: as mesmas colunas do FTS5 da v1 (nome, descrição, categoria)."""
    return f'{name}. {description} Categoria: {category}.'


def attribute_arrays(products: list[Product]) -> dict[str, np.ndarray]:
    ids = np.array([p.product_id for p in products])
    arr = {'product_id': ids}
    for key in ('category', 'type', 'level', 'use', 'tier', 'brand', 'finish'):
        arr[key] = np.array([p.attrs[key] for p in products])
    series = {s: i for i, s in enumerate(dict.fromkeys(p.attrs['series'] for p in products))}
    arr['series'] = np.array([series[p.attrs['series']] for p in products])
    arr['series_names'] = np.array(list(series))
    return arr
