from pathlib import Path
import pytest
from emporio.ingest.pipeline import ingest
from emporio.repository.sqlite import SQLiteRepository
from emporio.tools.search import search_products

ROOT = Path(__file__).resolve().parents[1]
@pytest.fixture
def repo(tmp_path):
    db = tmp_path/'store.db'
    ingest(ROOT/'data/raw', db, tmp_path/'processed', ROOT/'docs/adr/ADR-000-especificacao-consolidada.md')
    r = SQLiteRepository(db)
    yield r
    r.close()

def test_name_accent_fuzzy_and_no_match(repo):
    data = search_products(repo, {'query': 'Yamaha C40'}).data
    assert data['products'][0]['product_id'] == 81 and data['search_backend'] == 'sqlite_fts5_bm25'
    assert search_products(repo, {'query': 'violao'}) .data['total_matches'] > 0
    assert search_products(repo, {'query': 'Yamahaa C400'}).data['search_backend'] == 'rapidfuzz'
    assert search_products(repo, {'query': 'zzzzzzzzzzz'}).data['products'] == []

def test_filters_and_availability(repo):
    data = search_products(repo, {'category': 'Violões', 'min_price': '1967.18', 'max_price': '1967.18', 'only_available': True, 'limit': 50}).data
    assert [p['product_id'] for p in data['products']] == [90]
    assert data['products'][0]['price_info']['active_promotion']['discount_percent'] == '18'
    assert search_products(repo, {'category': 'Violões', 'min_price': '1967.19', 'max_price': '1967.19'}).data['products'] == []
    all_ = search_products(repo, {'query': 'Giannini GF-3D', 'only_available': False}).data['products']
    assert any(p['product_id'] == 96 and p['availability'] == 'out_of_stock' for p in all_)
    assert all(p['availability'] == 'available' for p in search_products(repo, {'query': 'Giannini GF-3D'}).data['products'])

def test_empty_malformed_and_description_protection(repo):
    assert search_products(repo, {}).data['total_matches'] == repo.connection.execute("SELECT count(*) FROM products WHERE status='active' AND stock_quantity > 0").fetchone()[0]
    assert search_products(repo, {'query': '" OR *'}).data['products'] == []
    assert search_products(repo, {'limit': 0}).error.code == 'invalid_input'
    assert search_products(repo, {'min_price': 10, 'max_price': 1}).error.code == 'invalid_input'
    result = search_products(repo, {'query': 'Fender Jazz Bass', 'only_available': False, 'limit': 50}).data
    assert any(p['product_id'] == 135 for p in result['products'])
    assert all('description' not in p for p in result['products'])
