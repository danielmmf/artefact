from decimal import Decimal, ROUND_HALF_UP


def to_cents(value: Decimal | str | int) -> int:
    amount = Decimal(value)
    if not amount.is_finite():
        raise ValueError("Valor monetário não finito")
    return int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def from_cents(value: int) -> Decimal:
    return Decimal(value) / Decimal(100)
