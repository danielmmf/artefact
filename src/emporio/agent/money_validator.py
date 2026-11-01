"""Validação conservadora de valores em reais contra resultados do turno."""
import re
from decimal import Decimal, InvalidOperation

MONEY_KEYS = {'price','list_price','final_price','pix_price','unit_original_cents','unit_final_cents',
              'subtotal','pix_subtotal','total_with_shipping','pix_total_with_shipping','total_brl',
              'fee','valor','amounts'}
NUM = r'(?:\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)'
CLAIM = re.compile(rf'(?<!\w)(?:(?:R\s*\$|BRL)\s*(?P<prefix>{NUM})(?!\d|[.,]\d)|(?P<suffix>{NUM})\s*(?:reais?|BRL)\b)', re.IGNORECASE)
CONTEXT = re.compile(rf'\b(?:custa|preço|valor|total|frete|parcela|por|oferta)\s*(?:(?:é|de|:)\s*)?(?:apenas\s+)?(?P<amount>{NUM})(?!\d|[.,]\d|%)', re.IGNORECASE)
MARKER = re.compile(r'R\s*\$|\bBRL\b|\breais?\b', re.IGNORECASE)

def parse_amount(text: str) -> Decimal:
    if ',' in text:
        text = text.replace('.', '').replace(',', '.')
    elif re.fullmatch(r'\d{1,3}(?:\.\d{3})+', text):
        text = text.replace('.', '')
    return Decimal(text)

def evidence_from_result(value, key: str = '') -> set[Decimal]:
    result = set()
    if isinstance(value, dict):
        for k, v in value.items():
            result.update(evidence_from_result(v, k))
    elif isinstance(value, list):
        for item in value:
            result.update(evidence_from_result(item, key))
    elif key in MONEY_KEYS and value is not None and not isinstance(value, bool):
        try:
            amount = Decimal(str(value))
            if amount.is_finite() and amount >= 0:
                result.add(amount / 100 if key.endswith('_cents') else amount)
        except InvalidOperation:
            pass
    return result

def supported_money(text: str, evidence: set[Decimal]) -> bool:
    claims = list(CLAIM.finditer(text))
    remaining = CLAIM.sub('', text)
    if MARKER.search(remaining):
        return False
    values = [parse_amount(m.group('prefix') or m.group('suffix')) for m in claims]
    values.extend(parse_amount(m.group('amount')) for m in CONTEXT.finditer(remaining))
    return all(value in evidence for value in values)


FILTER_KEYS = {'min_price', 'max_price'}

def evidence_from_filters(arguments) -> set[Decimal]:
    """Faixa de preço pedida pelo cliente e enviada à busca: repeti-la na resposta não é valor inventado."""
    found = set()
    if isinstance(arguments, dict):
        for key in FILTER_KEYS:
            value = arguments.get(key)
            if value is not None and not isinstance(value, bool):
                try:
                    amount = Decimal(str(value))
                except InvalidOperation:
                    continue
                if amount.is_finite() and amount >= 0:
                    found.add(amount)
    return found
