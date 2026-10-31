import pytest
from pathlib import Path
from emporio.ingest.pipeline import ingest
from emporio.repository.sqlite import SQLiteRepository
from emporio.tools.product import get_product

ROOT = Path(__file__).resolve().parents[1]
@pytest.fixture
def repo(tmp_path):
    db = tmp_path / 'store.db'
    ingest(ROOT/'data/raw', db, tmp_path/'processed', ROOT/'docs/adr/ADR-000-especificacao-consolidada.md')
    r = SQLiteRepository(db)
    yield r
    r.close()

def test_product_promotions(repo):
    gd = get_product(repo, {'product_id': 95}).data
    assert gd['price_info']['active_promotion'] is None and gd['inactive_promotions']
    detail = get_product(repo, {'product_id': 90}).data
    assert detail['price_info']['active_promotion']['discount_percent'] == '18'
    assert detail['price_info']['list_price'] == '2399' and detail['price_info']['final_price'] == '1967.18'

@pytest.mark.parametrize(('id_', 'expected'), [(96,'out_of_stock'),(113,'discontinued'),(130,'coming_soon'),(136,'discontinued')])
def test_availability_and_alternatives(repo, id_, expected):
    result = get_product(repo, {'product_id': id_}).data
    assert result['availability'] == expected
    if expected != 'coming_soon':
        assert result['alternatives'] and all(a['availability'] == 'available' for a in result['alternatives'])

@pytest.mark.parametrize('id_', [135,136,137,139,140,142,144])
def test_divergent_descriptions_not_returned(repo, id_):
    assert get_product(repo, {'product_id': id_}).data['description'] is None

def test_lookup_by_name_and_ambiguity(repo):
    assert get_product(repo, {'name': 'Yamaha C40 Nylon Natural'}).data['product_id'] == 81
    error = get_product(repo, {'name': 'Yamaha'}).error
    assert error.code == 'ambiguous' and len(error.candidates) > 1
    assert get_product(repo, {'name': 'inexistente_xyz'}).error.code == 'not_found'
    assert get_product(repo, {'name': ' ', 'product_id': 81}).error.code == 'invalid_input'

def test_special_quote(repo):
    for i in range(135, 142):
        detail = get_product(repo, {'product_id': i}).data
        assert detail['special_quote_required'] and detail['special_quote_note'] == 'Pode exigir cotação especial.'
    assert not get_product(repo, {'product_id': 143}).data['special_quote_required']
