"""Estratégias do S2 sem servidor Qdrant: A é a busca original, D funciona com embeddings falsos, e o SQLite manda nos dados comerciais."""
import sqlite3
from pathlib import Path

import numpy as np
import pytest

from emporio.repository.sqlite import SQLiteRepository
from emporio_lab.s2 import catalog as cat
from emporio_lab.s2 import strategies as st

SEED = 20261103


def fake_embed(self, text: str) -> np.ndarray:
    """Vetor determinístico por palavra (saco de palavras com hash): consultas e documentos com palavras em comum ficam próximos."""
    v = np.zeros(st.DENSE_DIM, dtype=np.float32)
    for word in text.casefold().replace('.', ' ').split():
        v[sum(map(ord, word)) * 7919 % st.DENSE_DIM] += 1.0
    n = np.linalg.norm(v)
    return v / n if n else v


@pytest.fixture()
def tiny(tmp_path, monkeypatch):
    monkeypatch.setattr(st.Embedders, 'embed_query', fake_embed)
    products = cat.generate(400, SEED)
    db = tmp_path / 'store.db'
    cat.build_sqlite(products, db)
    from emporio_lab.s2.build import load_rows
    rows = load_rows(db)
    matrix = np.array([fake_embed(None, cat.document_text(r['name'], r['description'], r['category'])) for r in rows], dtype=np.float32)
    np.save(tmp_path / 'emb.npy', matrix)
    np.save(tmp_path / 'ids.npy', np.array([r['id'] for r in rows]))
    np.save(tmp_path / 'snap_category.npy', np.array([r['category_id'] for r in rows]))
    np.save(tmp_path / 'snap_price.npy', np.array([r['price'] for r in rows]))
    np.save(tmp_path / 'snap_available.npy', np.array([r['available'] for r in rows]))
    index = st.Index('tiny', tmp_path, db, 'x', 'y', 'http://x', 'http://y')
    return index, products


def test_a_is_exactly_the_original_search(tiny):
    index, products = tiny
    query = products[10].name
    a = st.A(index, st.Config())
    result = a.search(query, {'only_available': False})
    ids, backend = a.repo.search_product_ids(query, None, None, None, False)
    assert result['ids'] == ids[:5] and result['backend'] == backend and result['ids'][0] == products[10].product_id
    a.close()


def test_rrf_rewards_agreement_between_branches_and_is_deterministic():
    fused = st.rrf([[1, 2, 3], [3, 2, 9]], k=60)
    assert set(fused[:2]) == {2, 3} and set(fused) == {1, 2, 3, 9}
    assert st.rrf([[5, 6]], 60) == [5, 6] and st.rrf([[7, 8], [8, 7]], 60) == [7, 8]      # empate: menor id


def test_d_finds_the_exact_product_and_respects_filters(tiny):
    index, products = tiny
    d = st.D(index, st.Config())
    target = products[42]
    assert d.search(target.name, {'only_available': False})['ids'][0] == target.product_id
    r = d.search('instrumento', {'category': 'Violões', 'only_available': True})
    repo = SQLiteRepository(index.db)
    assert r['ids'] and all(repo.get_product(i).category_id == 5 for i in r['ids'])
    assert all(repo.get_product_pricing(i).stock_quantity > 0 for i in r['ids'])
    repo.close(); d.close()


def test_a_stale_index_cannot_resurrect_an_unavailable_product_or_an_old_price(tiny):
    """Integração: o índice foi construído antes da mudança; a camada SQLite (fonte de verdade) decide."""
    index, products = tiny
    d = st.D(index, st.Config())
    available = [p for p in products if p.status == 'active' and p.stock > 0 and p.promo_percent is None]
    victim, repriced = available[0], available[1]
    before = d.search(victim.name, {'only_available': True})
    assert victim.product_id in before['ids']
    con = sqlite3.connect(index.db)
    con.execute('UPDATE products SET stock_quantity = 0 WHERE product_id = ?', (victim.product_id,))
    con.execute('UPDATE products SET price_cents = 999900 WHERE product_id = ?', (repriced.product_id,))
    con.commit(); con.close()
    after = d.search(victim.name, {'only_available': True})
    assert victim.product_id not in after['ids']
    f = st.Filters(d.repo, {'only_available': True})
    stale_candidates, _ = d.dense(fake_embed(None, victim.name), f, 100)
    assert victim.product_id in stale_candidates                                        # o snapshot do índice ainda diz "disponível"
    kept, dropped = st.hydrate(d.repo, stale_candidates, f, 100)
    assert victim.product_id not in kept and dropped >= 1                                # o SQLite (fonte de verdade) o descarta
    capped = d.search(repriced.name, {'only_available': True, 'max_price': repriced.price_cents + 1000})
    assert repriced.product_id not in capped['ids']                                    # o snapshot dizia "cabe no teto"; o SQLite diz que não
    d.close()


def test_hydrate_uses_the_final_promotional_price_for_price_filters(tiny):
    index, products = tiny
    promo = next(p for p in products if p.promo_percent and p.status == 'active' and p.stock > 0)
    repo = SQLiteRepository(index.db)
    f_cap_below_list = st.Filters(repo, {'max_price': promo.price_cents - 1, 'only_available': True})
    kept, dropped = st.hydrate(repo, [promo.product_id], f_cap_below_list, 5)
    assert kept == [promo.product_id] and dropped == 0                                  # promoção deixa o preço final abaixo do teto
    repo.close()


def test_qdrant_filter_translation():
    f = type('F', (), {'category_ids': [5], 'only_available': True, 'min_cents': 100, 'max_cents': 900})()
    flt = st.qdrant_filter(f)
    assert [c.key for c in flt.must] == ['category_id', 'available', 'price_cents']
    assert st.qdrant_filter(type('F', (), {'category_ids': None, 'only_available': False, 'min_cents': None, 'max_cents': None})()) is None


def test_fts_query_matches_the_v1_construction():
    assert st.fts_query('violão  nylon, Yamaha') == '"violão" OR "nylon" OR "Yamaha"' and st.fts_query('!!!') is None
