"""Pure commercial rules derived from docs/DECISIONS.md (S-a..S-f, S-i, S-j).

No database, LLM, filesystem or wall-clock dependencies. All money amounts
are integer cents. Discounts are rounded HALF_UP per unit (MVP convention).
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


SPECIAL_QUOTE_PRODUCT_IDS = frozenset(range(135, 142))
PIX_DISCOUNT_PERCENT = Decimal('5')


@dataclass(frozen=True)
class CartItem:
    product_id: int
    quantity: int
    unit_price_cents: int
    stock_quantity: int
    status: str
    active_promotion_percent: Decimal | None = None

    def __post_init__(self) -> None:
        if isinstance(self.product_id, bool) or not isinstance(self.product_id, int) or self.product_id <= 0:
            raise ValueError('product_id must be a positive integer')
        for field in ('quantity', 'stock_quantity', 'unit_price_cents'):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0 or (field == 'quantity' and value == 0):
                raise ValueError(f'{field} must be a valid nonnegative integer')
        if self.status not in {'active', 'discontinued', 'coming_soon'}:
            raise ValueError('unknown product status')
        if self.active_promotion_percent is not None:
            try:
                percent = Decimal(str(self.active_promotion_percent))
            except (InvalidOperation, ValueError) as exc:
                raise ValueError('invalid promotion percent') from exc
            if not percent.is_finite() or not Decimal('0') <= percent <= Decimal('100'):
                raise ValueError('promotion percent must be between 0 and 100')
            object.__setattr__(self, 'active_promotion_percent', percent)


@dataclass(frozen=True)
class PricedItem:
    product_id: int
    quantity: int
    purchasable: bool
    reason: str | None
    unit_original_cents: int
    unit_final_cents: int | None
    unit_pix_cents: int | None
    final_total_cents: int
    pix_total_cents: int
    promotion_percent: Decimal | None
    special_quote_possible: bool


@dataclass(frozen=True)
class CartTotals:
    items: tuple[PricedItem, ...]
    subtotal_cents: int
    pix_subtotal_cents: int
    has_unavailable_items: bool


@dataclass(frozen=True)
class Installment:
    count: int
    amounts_cents: tuple[int, ...]
    valid: bool
    reason: str | None


@dataclass(frozen=True)
class ShippingMethod:
    name: str
    business_days_min: int
    business_days_max: int


@dataclass(frozen=True)
class ShippingQuote:
    destination_city: str | None
    cost_cents: int | None
    methods: tuple[ShippingMethod, ...]
    needs_destination: bool
    special_quote_possible: bool


OTHER_CITY_METHODS = (
    ShippingMethod('PAC', 5, 12),
    ShippingMethod('SEDEX', 2, 5),
    ShippingMethod('Jadlog', 3, 8),
)
LOCAL_METHOD = (ShippingMethod('Entrega local', 1, 3),)


def discounted_cents(original_cents: int, percent: Decimal) -> int:
    """ROUND_HALF_UP per unit, never floats; preserve original unit price."""
    if isinstance(original_cents, bool) or not isinstance(original_cents, int) or original_cents < 0:
        raise ValueError('price must be nonnegative integer cents')
    try:
        amount = Decimal(str(percent))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('invalid discount') from exc
    if not amount.is_finite() or not Decimal('0') <= amount <= Decimal('100'):
        raise ValueError('discount percent out of range')
    return int((Decimal(original_cents) * (Decimal('100') - amount) / Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def may_require_special_quote(product_id: int) -> bool:
    """Manual says 'may require' special freight; never treat it as mandatory."""
    return product_id in SPECIAL_QUOTE_PRODUCT_IDS


def price_cart(items: list[CartItem] | tuple[CartItem, ...]) -> CartTotals:
    """Only purchasable products enter totals; PIX is itemwise and exclusive."""
    seen: set[int] = set()
    results: list[PricedItem] = []
    for item in items:
        if item.product_id in seen:
            raise ValueError(f'duplicate product_id: {item.product_id}')
        seen.add(item.product_id)
        reason = (
            'discontinued' if item.status == 'discontinued' else
            'coming_soon' if item.status == 'coming_soon' else
            'out_of_stock' if item.stock_quantity == 0 else
            'insufficient_stock' if item.stock_quantity < item.quantity else None
        )
        purchasable = reason is None
        final_unit = discounted_cents(item.unit_price_cents, item.active_promotion_percent) if item.active_promotion_percent is not None else item.unit_price_cents
        pix_unit = discounted_cents(item.unit_price_cents, PIX_DISCOUNT_PERCENT) if item.active_promotion_percent is None else final_unit
        results.append(PricedItem(
            product_id=item.product_id,
            quantity=item.quantity,
            purchasable=purchasable,
            reason=reason,
            unit_original_cents=item.unit_price_cents,
            unit_final_cents=final_unit if purchasable else None,
            unit_pix_cents=pix_unit if purchasable else None,
            final_total_cents=final_unit * item.quantity if purchasable else 0,
            pix_total_cents=pix_unit * item.quantity if purchasable else 0,
            promotion_percent=item.active_promotion_percent,
            special_quote_possible=may_require_special_quote(item.product_id),
        ))
    return CartTotals(
        items=tuple(results),
        subtotal_cents=sum(line.final_total_cents for line in results),
        pix_subtotal_cents=sum(line.pix_total_cents for line in results),
        has_unavailable_items=any(not line.purchasable for line in results),
    )


def minimum_installment_cents(count: int) -> int:
    if not 1 <= count <= 12:
        raise ValueError('installment count must be 1..12')
    if count == 1:
        return 0
    if count <= 3:
        return 5_000
    if count <= 6:
        return 8_000
    return 10_000


def installment_options(total_cents: int) -> tuple[Installment, ...]:
    """Installment sums exactly equal the total; odd cents go to earliest terms."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int) or total_cents < 0:
        raise ValueError('total must be nonnegative integer cents')
    options = []
    for count in range(1, 13):
        base, remainder = divmod(total_cents, count)
        amounts = tuple(base + (1 if i < remainder else 0) for i in range(count))
        valid = min(amounts) >= minimum_installment_cents(count)
        options.append(Installment(
            count=count,
            amounts_cents=amounts,
            valid=valid,
            reason=None if valid else 'installment_below_minimum',
        ))
    return tuple(options)


def combined_payment_allowed(subtotal_cents: int) -> bool:
    if isinstance(subtotal_cents, bool) or not isinstance(subtotal_cents, int) or subtotal_cents < 0:
        raise ValueError('subtotal must be nonnegative integer cents')
    return subtotal_cents >= 200_000


def quote_shipping(cart: CartTotals, destination_city: str | None) -> ShippingQuote:
    """Shipping threshold uses promotional subtotal BEFORE the PIX discount."""
    city = destination_city.strip() if destination_city else None
    special = any(line.purchasable and line.special_quote_possible for line in cart.items)
    if not city:
        return ShippingQuote(None, None, (), True, special)
    if city.casefold() == 'campo grande':
        return ShippingQuote(city, 0 if cart.subtotal_cents >= 50_000 else 3_500, LOCAL_METHOD, False, special)
    return ShippingQuote(city, None, OTHER_CITY_METHODS, False, special)
