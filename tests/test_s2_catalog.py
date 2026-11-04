"""Catálogo sintético do S2: determinístico, derivado de atributos, com o mesmo esquema da v1 e sem cópia dos 65 produtos originais."""
import sqlite3
from pathlib import Path

from emporio_lab.s2 import catalog as cat
from emporio_lab.s2 import lexicon as lx
from emporio_lab.s2 import vocab

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261103


def test_same_seed_same_catalog_and_other_seed_differs():
    a, b = cat.generate(600, SEED), cat.generate(600, SEED)
    assert cat.catalog_hash(a) == cat.catalog_hash(b)
    assert cat.catalog_hash(a) != cat.catalog_hash(cat.generate(600, SEED + 1))


def test_small_catalog_is_the_prefix_of_the_large_one():
    big = cat.generate(3000, SEED)
    assert cat.catalog_hash(cat.generate(1000, SEED)) == cat.catalog_hash(big[:1000])


def test_ids_are_stable_unique_and_contiguous_from_the_first_id():
    products = cat.generate(800, SEED)
    assert [p.product_id for p in products] == list(range(cat.FIRST_ID, cat.FIRST_ID + 800))
    assert len({p.name for p in products}) == 800                      # nome completo identifica um produto


def test_descriptions_are_derived_from_the_attributes():
    for p in cat.generate(500, SEED):
        a = p.attrs
        assert p.category_id == lx.TYPES[a['type']][1] == a['category']
        assert lx.USES[a['use']] in lx.TYPES[a['type']][4]
        if a['level_in_text']:
            assert any(phrase.capitalize() + '.' in p.description for phrase in lx.LEVEL_DESC[lx.LEVELS[a['level']]])
        if a['use_in_text']:
            assert any(phrase.capitalize() + '.' in p.description for phrase in lx.USE_DESC[lx.USES[a['use']]])
        assert p.name.startswith(lx.BRANDS[a['brand']])


def test_noise_and_variety_exist():
    products = cat.generate(2000, SEED)
    assert {p.status for p in products} == {'active', 'discontinued'}
    assert any(p.promo_percent for p in products) and any(p.stock == 0 for p in products)
    assert any(not p.attrs['use_in_text'] for p in products) and any(not p.attrs['level_in_text'] for p in products)
    assert len({p.attrs['series'] for p in products}) > 300


def test_nothing_is_copied_from_the_65_original_products():
    con = sqlite3.connect(ROOT / 'var/store.db') if (ROOT / 'var/store.db').exists() else None
    if con is None:
        return
    originals = {r[0].casefold() for r in con.execute('SELECT name FROM products')}
    assert not originals & {p.name.casefold() for p in cat.generate(5000, SEED)}


def test_sqlite_has_the_v1_schema_and_fts5(tmp_path):
    products = cat.generate(300, SEED)
    timing = cat.build_sqlite(products, tmp_path / 'store.db')
    con = sqlite3.connect(tmp_path / 'store.db')
    assert con.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 300
    assert con.execute("SELECT COUNT(*) FROM products_fts WHERE products_fts MATCH 'violão'").fetchone()[0] > 0
    v1 = sqlite3.connect(ROOT / 'var/store.db') if (ROOT / 'var/store.db').exists() else None
    if v1:
        cols = lambda c, t: [r[1] for r in c.execute(f'PRAGMA table_info({t})')]
        for table in ('products', 'categories', 'promotions'):
            assert cols(con, table) == cols(v1, table)
    assert timing['bytes'] > 0


def test_lexicon_separation_holds_at_the_source_and_in_the_realized_catalog():
    assert vocab.overlap_report() == {}
    assert vocab.realized_overlap(cat.generate(3000, SEED)) == {}
