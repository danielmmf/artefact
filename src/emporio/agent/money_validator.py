"""Validação conservadora de valores em reais contra resultados do turno."""
import re
from decimal import Decimal, InvalidOperation

MONEY_KEYS = {'price','list_price','final_price','pix_price','unit_original_cents','unit_final_cents',
              'subtotal','pix_subtotal','total_with_shipping','pix_total_with_shipping','total_brl',
              'fee','valor','last_amount','amounts'}
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

# Valores do manual (parte confiável do prompt) só contam em frases do tema a que pertencem; nunca como preço de produto.
_FRETE = re.compile(r'frete|entrega|envio', re.IGNORECASE)
_PARCELA = re.compile(r'parcel|m[íi]nim', re.IGNORECASE)
_PAGAMENTO = re.compile(r'combin|formas? de pagamento|pagamento (misto|combinado)', re.IGNORECASE)  # o R$ 2.000 do manual é só do pagamento combinado
MANUAL_CONTEXT = {Decimal('35'): (_FRETE,), Decimal('500'): (_FRETE,),
                  Decimal('50'): (_PARCELA,), Decimal('80'): (_PARCELA,), Decimal('100'): (_PARCELA,),
                  Decimal('2000'): (_PAGAMENTO,)}


def _sentence(text: str, position: int) -> str:
    """Frase que contém `position`; o ponto de '1.234,56' não encerra a frase (só ponto seguido de espaço/fim)."""
    ends = [m.end() for m in re.finditer(r'[.!?](?=\s|$)|\n', text[:position])]
    start = ends[-1] if ends else 0
    stop = re.search(r'[.!?](?=\s|$)|\n', text[position:])
    return text[start:position + stop.start()] if stop else text[start:]


def _allowed(value: Decimal, evidence: set[Decimal], manual, sentence: str) -> bool:
    if value in evidence:
        return True
    return value in manual and any(rule.search(sentence) for rule in MANUAL_CONTEXT.get(value, ()))


def unsupported_amounts(text: str, evidence: set[Decimal], manual=frozenset()) -> list[Decimal]:
    """Valores em R$ do texto sem respaldo: nem em resultado de tool do turno, nem em valor do manual no tema certo."""
    bad = [parse_amount(m.group('prefix') or m.group('suffix')) for m in CLAIM.finditer(text)
           if not _allowed(parse_amount(m.group('prefix') or m.group('suffix')), evidence, manual, _sentence(text, m.start()))]
    remaining = CLAIM.sub('', text)
    bad += [parse_amount(m.group('amount')) for m in CONTEXT.finditer(remaining)
            if not _allowed(parse_amount(m.group('amount')), evidence, manual, _sentence(remaining, m.start()))]
    return bad


def supported_money(text: str, evidence: set[Decimal], manual=frozenset()) -> bool:
    if MARKER.search(CLAIM.sub('', text)):
        return False
    return not unsupported_amounts(text, evidence, manual)


FILTER_KEYS = {'min_price', 'max_price'}
_BOUND = r'(?:at[ée]|abaixo de|menos de|no m[áa]ximo|m[áa]ximo de|acima de|mais de|a partir de|no m[íi]nimo|m[íi]nimo de)'
_AMOUNT = re.compile(rf'\b{_BOUND}\s*(?:R\s*\$\s*)?(?P<n>{NUM})(?P<mil>\s*mil\b)?', re.IGNORECASE)
_BETWEEN = re.compile(rf'\bentre\s*(?:R\s*\$\s*)?(?P<a>{NUM})\s*e\s*(?:R\s*\$\s*)?(?P<b>{NUM})', re.IGNORECASE)


def amounts_in_message(message: str) -> set[Decimal]:
    """Valores que o cliente citou como preço: com R$/reais, depois de 'até/acima de/entre…' ou 'N mil'. Número solto não conta."""
    found = {parse_amount(m.group('prefix') or m.group('suffix')) for m in CLAIM.finditer(message)}
    for m in _AMOUNT.finditer(message):
        found.add(parse_amount(m.group('n')) * (1000 if m.group('mil') else 1))
    for m in _BETWEEN.finditer(message):
        found |= {parse_amount(m.group('a')), parse_amount(m.group('b'))}
    found |= {Decimal(m.group(1)) * 1000 for m in re.finditer(r'\b(\d+)\s*mil\s+reais\b', message, re.IGNORECASE)}
    if re.search(r'\bmil\s+reais\b', message, re.IGNORECASE):
        found.add(Decimal(1000))
    return found


def evidence_from_filters(arguments, message: str) -> set[Decimal]:
    """Faixa de preço enviada à busca só vale como evidência se o cliente a disse neste turno; valor inventado não vale."""
    said = amounts_in_message(message)
    found = set()
    if isinstance(arguments, dict):
        for key in FILTER_KEYS:
            value = arguments.get(key)
            if value is not None and not isinstance(value, bool):
                try:
                    amount = Decimal(str(value))
                except InvalidOperation:
                    continue
                if amount.is_finite() and amount >= 0 and amount in said:
                    found.add(amount)
    return found


def evidence_from_manual(manual: str) -> set[Decimal]:
    """Valores em R$ do manual (parte confiável do prompt): limites de frete, parcela mínima, pagamento combinado."""
    return {parse_amount(m.group('prefix') or m.group('suffix')) for m in CLAIM.finditer(manual)}
