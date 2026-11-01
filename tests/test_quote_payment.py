from decimal import Decimal
from pathlib import Path
import sqlite3

import pytest

from emporio.ingest.pipeline import ingest
from emporio.repository.sqlite import SQLiteRepository
from emporio.tools.quote_payment import quote_payment

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def repository(tmp_path):
    db = tmp_path / 'store.db'
    ingest(ROOT / 'data/raw', db, tmp_path / 'processed', ROOT / 'docs/adr/ADR-000-especificacao-consolidada.md')
    repo = SQLiteRepository(db)
    yield repo
    repo.close()


def quote(repo, items, city=None):
    result = quote_payment(repo, {'items': [{'product_id': p, 'quantity': q} for p, q in items], 'destination_city': city})
    assert result.ok, result.error
    return result.data


def test_quote_uses_real_active_promotions_and_pix(repository):
    data = quote(repository, [(121, 1), (81, 2)], 'Campo Grande')
    promotion, normal = data['items']
    assert promotion['list_price'] == Decimal('549.00')
    assert promotion['active_promotion']['discount_percent'] == Decimal('20')
    assert promotion['final_price'] == promotion['pix_price'] == Decimal('439.20')
    assert not promotion['pix_eligible']
    assert normal['list_price'] == Decimal('599.90')
    assert normal['pix_eligible'] and normal['pix_price'] == Decimal('569.91')
    assert data['subtotal'] == Decimal('1639.00')
    assert data['pix_subtotal'] == Decimal('1579.02')
    assert data['shipping']['fee'] == 0
    assert data['total_with_shipping'] == Decimal('1639.00')
    assert data['pix_total_with_shipping'] == Decimal('1579.02')
    assert data['installments_basis'] == 'subtotal de produtos, sem frete'
    assert sum(data['installments'][2]['amounts']) == data['subtotal']


def test_inactive_promotion_is_not_applied_and_18_percent_is_real(repository):
    inactive, active = quote(repository, [(95, 1), (90, 1)])['items']
    assert inactive['active_promotion'] is None and inactive['pix_eligible']
    assert active['active_promotion']['discount_percent'] == Decimal('18')
    assert active['list_price'] == Decimal('2399.00')
    assert active['final_price'] == Decimal('1967.18')
    assert not active['pix_eligible']


def test_unavailable_and_insufficient_stock_excluded(repository):
    data = quote(repository, [(96, 1), (113, 1), (136, 1), (130, 1), (81, 13)], 'Campo Grande')
    assert [x['reason'] for x in data['items']] == ['out_of_stock', 'discontinued', 'discontinued', 'coming_soon', 'insufficient_stock']
    assert all(x['status'] == 'not_purchasable' for x in data['items'])
    assert data['subtotal'] == data['pix_subtotal'] == 0
    assert data['shipping'] is None and not data['installments']
    assert data['items'][2]['special_quote_required'] is True


def test_special_freight_is_advisory_and_other_city_has_no_fee(repository):
    data = quote(repository, [(139, 1)], 'Dourados')
    shipping = data['shipping']
    assert shipping['region'] == 'other' and shipping['fee'] is None and shipping['free'] is None
    assert data['total_with_shipping'] is None and data['pix_total_with_shipping'] is None
    assert shipping['special_quote_required'] and shipping['special_quote_note'] == 'Pode exigir cotação especial.'
    assert [x['name'] for x in shipping['modalities']] == ['PAC', 'SEDEX', 'Jadlog']
    assert not quote(repository, [(143, 1)], 'Dourados')['shipping']['special_quote_required']


def test_unknown_destination_and_real_database_read_only(repository):
    data = quote(repository, [(81, 1)])
    assert data['shipping']['region'] == 'unknown' and data['shipping']['fee'] is None
    with pytest.raises(sqlite3.OperationalError, match='readonly'):
        repository.connection.execute('UPDATE products SET price_cents = 0')


@pytest.mark.parametrize('args', [
    {}, {'items': []}, {'items': [{'product_id': 81, 'quantity': 0}]},
    {'items': [{'product_id': 81, 'quantity': True}]}, {'items': [{'product_id': 2**63, 'quantity': 1}]}, {'items': [{'product_id': '81', 'quantity': 1}]},
    {'items': [{'product_id': 81, 'quantity': 1, 'price': 1}]},
    {'items': [{'product_id': 81, 'quantity': 1}, {'product_id': 81, 'quantity': 2}]},
])
def test_invalid_input_has_structured_error(repository, args):
    result = quote_payment(repository, args)
    assert not result.ok and result.data is None and result.error.code == 'invalid_input'


def test_missing_product_has_structured_error(repository):
    result = quote_payment(repository, {'items': [{'product_id': 999999, 'quantity': 1}]})
    assert not result.ok and result.error.code == 'not_found'

@pytest.mark.parametrize(('price', 'fee'), [(49999, Decimal('35')), (50000, Decimal('0')), (50001, Decimal('0'))])
def test_shipping_threshold_through_sqlite(tmp_path, price, fee):
    db = tmp_path / 'store.db'
    ingest(ROOT / 'data/raw', db, tmp_path / 'processed', ROOT / 'docs/adr/ADR-000-especificacao-consolidada.md')
    with sqlite3.connect(db) as con:
        con.execute('UPDATE products SET price_cents = ? WHERE product_id = ?', (price, 81))
    repo = SQLiteRepository(db)
    try:
        data = quote(repo, [(81, 1)], 'Campo Grande')
        assert data['shipping']['fee'] == fee
        assert data['total_with_shipping'] == Decimal(price) / 100 + fee
    finally:
        repo.close()


def test_city_variations_and_safe_database_error(repository):
    assert quote(repository, [(81, 1)], ' campo grande / MS ')['shipping']['region'] == 'metro'
    repository.close()
    result = quote_payment(repository, {'items': [{'product_id': 81, 'quantity': 1}]})
    assert not result.ok and result.error.code == 'internal_error'
    assert 'sqlite' not in result.model_dump_json().lower()


def test_quote_installments_expose_common_and_last_amount_that_close_the_total(repository):
    data = quote_payment(repository, {'items': [{'product_id': 95, 'quantity': 1}]}).data
    for line in data['installments']:
        n = line['n']
        assert Decimal(line['valor']) * (n - 1) + Decimal(line['last_amount']) == Decimal(data['subtotal'])
    eight = data['installments'][7]
    assert (eight['valor'], eight['last_amount']) == (Decimal('274.87'), Decimal('274.91'))
