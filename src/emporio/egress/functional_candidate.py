"""Componentes experimentais de admissão; sem transporte ou ativação externa.

Esta candidata ainda não projeta resultados de ferramentas. A admissão sintética
é limitada ao golden set versionado; entradas livres desconhecidas são bloqueadas.
"""
import hashlib
import json
import re
from pathlib import Path

from emporio.egress.candidate import ProjectionError

GOLDEN_SHA256 = 'e3758b77b46975b43a9f2896f1a63f8712ebfb1f787616f6100321ae506ebc69'
# Formas fechadas para perguntas sem dados pessoais ou conteúdo arbitrário.
GENERIC = re.compile(
    r'(?:qual (?:é )?o horário da loja\?|a loja está aberta\?|'
    r'quais (?:são as )?formas de pagamento\?|'
    r'quais (?:são as )?políticas de (?:frete|devolução|troca)\?|'
    r'(?:qual (?:é )?o preço|há promoção|tem estoque) do produto [1-9][0-9]{0,2}\?)',
    re.IGNORECASE,
)


def admit_generic_message(text: str) -> str:
    """Aceita apenas linguagem genérica de gramática fechada; não usa regex como detector de PII."""
    if type(text) is not str or not GENERIC.fullmatch(text):
        raise ProjectionError('unapproved_user_message')
    return text


def admit_golden_message(path: Path, case_id: str, text: str) -> str:
    """Permite somente entrada sintética exata do conjunto congelado para revisão offline."""
    try:
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != GOLDEN_SHA256:
            raise ValueError('unreviewed set')
        document = json.loads(raw)
        cases = [case for case in document['cases'] if case['id'] == case_id]
        if len(cases) != 1 or type(text) is not str or text != cases[0]['input']:
            raise ValueError('unreviewed input')
    except (OSError, KeyError, ValueError, TypeError):
        raise ProjectionError('unapproved_synthetic_input') from None
    return text
