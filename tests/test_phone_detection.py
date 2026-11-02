"""Telefone brasileiro: DDD válido + 8/9 dígitos, separadores generalizados; datas, CEP, valores e códigos não são telefone.

Política: sequência suspeita não reconhecida passa como está (não há bloqueio por dígitos)."""
import csv
from pathlib import Path

import pytest

from emporio.agent.loop import ConversationEngine
from emporio.agent.privacy import protect_dynamic
from emporio.llm.scripted import AssistantReply
from emporio.security.contacts import ContactVault, normalize_contact
from test_integration_offline import setup_registry
from test_order_security import env  # noqa: F401  (fixture)
from test_real_path import FakeProviderLLM

ROOT = Path(__file__).resolve().parents[1]


def tokenized(text):
    return ContactVault('t').tokenize(text)


# --- o que DEVE virar [PHONE_n] -------------------------------------------------------------------
SEPARATORS = [' ', '.', '-', '_', ':', '/', ',', ';', '|', '  ', ' - ', '. ']


@pytest.mark.parametrize('sep', SEPARATORS)
def test_mobile_with_any_common_separator_between_the_groups(sep):
    assert tokenized(f'meu tel 67{sep}99812{sep}3456 ok') == 'meu tel [PHONE_1] ok'


@pytest.mark.parametrize('sep', SEPARATORS)
def test_landline_with_any_common_separator_between_the_groups(sep):
    assert tokenized(f'fixo 11{sep}3456{sep}7890.') == 'fixo [PHONE_1].'


@pytest.mark.parametrize('phone', [
    '(67) 99812-3456', '(67)99812-3456', '67999123456', '6733414445', '+55 67 99812-3456', '55 67 99812 3456',
    '5567998123456', '+5567998123456', '(11) 98765-4321', '011 98765-4321'[1:], '(21) 2345-6789', '85:98765:4321',
])
def test_brazilian_formats_are_tokenized(phone):
    assert tokenized(f'contato: {phone}') == 'contato: [PHONE_1]'


@pytest.mark.parametrize('invalid', ['(20) 99812-3456', '(23) 99812-3456', '(00) 99812-3456', '(10) 99812-3456', '(99) 89812-3456',
                                     '67 9981-23456', '67 99812-345', '67 1234-5678'])
def test_invalid_ddd_or_shape_is_not_a_phone(invalid):
    assert tokenized(f'x {invalid} y') == f'x {invalid} y'


def test_every_customer_phone_in_the_official_data_is_recognized_and_normalized():
    rows = list(csv.DictReader(open(ROOT / 'data/raw/desafio_tecnico_ai_eng - customers.csv', encoding='utf-8')))
    assert len(rows) == 50
    for row in rows:
        vault = ContactVault('c')
        assert vault.tokenize(row['phone']) == '[PHONE_1]', row['customer_id']
        assert normalize_contact(row['phone'])[0] == 'phone'


# --- o que NÃO PODE ser tokenizado (nem bloqueado) ----------------------------------------------------
MUST_STAY = [
    '20/03/2026', '20/03/2026 às 10:00', '20/03/2026 10:00', '11/03/2026 10:00', '21/03/2026 14:30', '28/09/2026 21:45',
    '2026-03-25 10:00', '2026-03-25T10:00:00-04:00', '25/03/2026, 9:30', '79202-333', '79202333',
    'R$ 2.199,00', '10x de 219,90', 'R$ 11.499,00', '12.345.678,90', '8 × 274,87, sendo a última de R$ 274,91',
    'pedido 5', 'pedido 12345678', 'BRKR1122334BR', 'BRAB1234567BR', 'protocolo 3',
    'Recebi em 20/03/2026 10:00 e paguei R$ 2.199,00 no pedido 7',
]


@pytest.mark.parametrize('text', MUST_STAY)
def test_dates_times_cep_values_orders_and_tracking_codes_are_not_tokenized_nor_blocked(text):
    assert tokenized(text) == text
    assert protect_dynamic(text, ContactVault('p')) == text      # nenhum bloqueio de mensagem


def test_unrecognized_suspicious_digit_sequences_pass_as_they_are():
    for text in ['6799 8123 456 7', 'meu número é 67 9 9812 34 56', '1234567890123456', '0000000000']:
        assert protect_dynamic(text, ContactVault('p')) == text


def test_email_written_out_is_still_blocked_so_the_privacy_barrier_for_email_remains():
    from emporio.agent.privacy import PrivacyError
    with pytest.raises(PrivacyError):
        protect_dynamic('pessoa arroba exemplo ponto com', ContactVault('p'))


# --- ponta a ponta -------------------------------------------------------------------------------------
def test_engine_keeps_the_date_and_hides_the_phone_with_unusual_separators(env, tmp_path):
    llm = FakeProviderLLM([AssistantReply(content='Ok.')])
    answer, _ = ConversationEngine(setup_registry(env), llm, tmp_path / 't.jsonl').turn(
        'Recebi em 20/03/2026 10:00 e meu telefone é 67:99812:3456, ligue antes das 18:00')
    sent = llm.calls[0][-1]['content']
    assert answer == 'Ok.'                                    # a data com hora não derruba a conversa
    assert '20/03/2026 10:00' in sent and '18:00' in sent
    assert '[PHONE_1]' in sent and '99812' not in sent and '3456' not in sent


def test_institutional_phones_stay_visible_and_are_not_tokenized():
    for phone in ['(67) 3341-4444', '(67) 3321-4500', '**(67) 3341-4444**', '(67)3341-4444']:
        assert tokenized(f'Ligue {phone}.') == f'Ligue {phone}.'
