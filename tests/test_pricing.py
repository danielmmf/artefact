"""Phase 2: deterministic PRC-01..PRC-07 regression tests (offline)."""

from decimal import Decimal

import pytest

from emporio.rules.pricing import (
    CartItem,
    combined_payment_allowed,
    discounted_cents,
    installment_options,
    may_require_special_quote,
    price_cart,
    quote_shipping,
)


def item(product_id=81, price=50000, quantity=1, stock=10, status='active', promotion=None):
    return CartItem(product_id, quantity, price, stock, status, promotion)


@pytest.mark.parametrize(('total', 'expected'), [(49999, 3500), (50000, 0), (50001, 0)])
def test_local_shipping_boundary(total, expected):
    cart = price_cart([item(price=total)])
    assert quote_shipping(cart, ' Campo Grande ').cost_cents == expected
    assert quote_shipping(cart, 'Campo Grande').methods[0].business_days_min == 1
    assert quote_shipping(cart, 'Campo Grande').methods[0].business_days_max == 3


def test_shipping_applies_to_promotional_subtotal_before_pix():
    cart = price_cart([item(price=51000)])
    assert cart.subtotal_cents == 51000
    assert cart.pix_subtotal_cents == 48450
    assert quote_shipping(cart, 'Campo Grande').cost_cents == 0
    other = quote_shipping(cart, 'Dourados')
    assert other.cost_cents is None
    assert [(m.name, m.business_days_min, m.business_days_max) for m in other.methods] == [
        ('PAC', 5, 12), ('SEDEX', 2, 5), ('Jadlog', 3, 8)]
    assert quote_shipping(cart, None).needs_destination


def test_promotions_and_pix_are_not_stacked_on_one_item():
    cart = price_cart([item(121, 10000, promotion=Decimal('20')), item(81, 20000)])
    a, b = cart.items
    assert a.unit_original_cents == 10000
    assert a.unit_final_cents == a.unit_pix_cents == 8000
    assert b.unit_pix_cents == 19000
    assert cart.subtotal_cents == 28000
    assert cart.pix_subtotal_cents == 27000


def test_discount_round_half_up_per_unit():
    assert discounted_cents(101, Decimal('50')) == 51
    assert discounted_cents(10000, Decimal('18')) == 8200
    assert discounted_cents(10000, Decimal('0')) == 10000
    assert discounted_cents(10000, Decimal('100')) == 0
    with pytest.raises(ValueError):
        discounted_cents(10000, Decimal('NaN'))


@pytest.mark.parametrize(('count', 'valid_total', 'invalid_total'), [
    (2, 10000, 9998), (3, 15000, 14997), (4, 32000, 31996),
    (6, 48000, 47994), (7, 70000, 69993), (12, 120000, 119988),
])
def test_installment_limits(count, valid_total, invalid_total):
    assert installment_options(valid_total)[count-1].valid
    rejected = installment_options(invalid_total)[count-1]
    assert not rejected.valid
    assert rejected.reason == 'installment_below_minimum'
    assert sum(rejected.amounts_cents) == invalid_total


def test_installments_distribute_cents_without_losing_money():
    installment = installment_options(10001)[2]
    assert installment.amounts_cents == (3334, 3334, 3333)
    assert sum(installment.amounts_cents) == 10001
    assert installment_options(1)[0].valid


def test_payment_combination_inclusive_boundary():
    assert not combined_payment_allowed(199999)
    assert combined_payment_allowed(200000)
    assert combined_payment_allowed(200001)


@pytest.mark.parametrize(('id_', 'status', 'stock', 'quantity', 'expected_reason'), [
    (96, 'active', 0, 1, 'out_of_stock'),
    (136, 'discontinued', 13, 1, 'discontinued'),
    (130, 'coming_soon', 10, 1, 'coming_soon'),
    (81, 'active', 2, 3, 'insufficient_stock'),
])
def test_not_purchasable_items_excluded_from_totals(id_, status, stock, quantity, expected_reason):
    cart = price_cart([item(id_, 10000, quantity, stock, status)])
    assert cart.has_unavailable_items
    assert cart.subtotal_cents == 0
    assert cart.pix_subtotal_cents == 0
    assert cart.items[0].reason == expected_reason
    assert cart.items[0].unit_final_cents is None


def test_special_quote_flag_is_advisory_and_uses_explicit_id_list():
    for id_ in range(135, 142):
        assert may_require_special_quote(id_)
    for id_ in (81, 130, 134, 142, 143, 144):
        assert not may_require_special_quote(id_)
    assert quote_shipping(price_cart([item(140)]), 'Dourados').special_quote_possible
    # 136 has the product flag, but discontinued products do not affect shipping.
    assert not quote_shipping(price_cart([item(136, status='discontinued')]), 'Dourados').special_quote_possible


def test_order_historic_prices_not_used_for_new_cart():
    """Cart calculations use supplied current prices, not historical orders."""
    cart = price_cart([item(price=345000)])
    assert cart.subtotal_cents == 345000


def test_invalid_prices_promotions_duplicate_products():
    with pytest.raises(ValueError):
        item(price=-1)
    with pytest.raises(ValueError):
        item(promotion=Decimal('101'))
    with pytest.raises(ValueError):
        price_cart([item(), item()])
    with pytest.raises(ValueError):
        installment_options(-1)
