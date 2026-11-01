"""Caminho real com LLM: defeitos encontrados no smoke test e contratos do motor com qualquer LLM."""
import json
from pathlib import Path

import pytest

from emporio.agent.loop import ConversationEngine, SAFE
from emporio.agent.privacy import protect_dynamic
from emporio.cli import chat_live
from emporio.config import Settings
from emporio.llm.scripted import AssistantReply, FunctionCall
from emporio.security.contacts import ContactVault, is_institutional
from emporio.tools.search import search_products
from test_integration_offline import setup_registry
from test_order_security import env  # noqa: F401  (fixture)
from test_search import repo  # noqa: F401  (fixture)


@pytest.mark.parametrize('category', ['violão', 'Violões', 'violoes', 'VIOLAO', 'violões'])
def test_category_filter_tolerates_case_accent_and_plural(repo, category):
    data = search_products(repo, {'query': 'Takamine GD20', 'category': category}).data
    assert [p['product_id'] for p in data['products']][0] == 95


def test_category_filter_maps_other_singular_terms_and_rejects_unknown(repo):
    assert search_products(repo, {'category': 'ukulele', 'limit': 50}).data['total_matches'] > 0
    assert search_products(repo, {'category': 'bateria'}).data['total_matches'] > 0
    assert search_products(repo, {'category': 'acordeon'}).data['products'] == []


def test_institutional_contacts_are_public_not_personal_data():
    vault = ContactVault('s1')
    text = 'Ligue (67) 3341-4444 ou escreva para contato@emporiodamusica.com.br; WhatsApp (67) 3321-4500.'
    assert vault.tokenize(text) == text and protect_dynamic(text, vault) == text
    assert is_institutional('contato@empóriodamusica.com.br')


def test_customer_contacts_stay_tokenized_and_unknown_formats_stay_blocked():
    vault = ContactVault('s2')
    assert protect_dynamic('meu e-mail é lucas.mendes@jmail.com e (67) 99812-3456', vault) == 'meu e-mail é [EMAIL_1] e [PHONE_1]'
    with pytest.raises(Exception):
        protect_dynamic('escreva para pessoa arroba exemplo ponto com', vault)
    # institucional ao lado de dado desconhecido não libera o desconhecido
    with pytest.raises(Exception):
        protect_dynamic('(67) 3341-4444 e 5567 9 8765 4321 0', vault)


class FakeProviderLLM:
    """Qualquer objeto com complete(messages, tools) serve ao motor, como o adaptador HTTP."""
    model = 'fake-provider'

    def __init__(self, replies):
        self._replies = iter(replies)
        self.calls = []

    def complete(self, messages, tools=None):
        self.calls.append(messages)
        return next(self._replies)


def test_engine_accepts_any_llm_and_answers_with_store_phone(env, tmp_path):
    llm = FakeProviderLLM([AssistantReply(content='O telefone da loja é (67) 3341-4444 e o e-mail contato@emporiodamusica.com.br.')])
    answer, _ = ConversationEngine(setup_registry(env), llm, tmp_path / 't.jsonl').turn('Qual o contato da loja?')
    assert answer == 'O telefone da loja é (67) 3341-4444 e o e-mail contato@emporiodamusica.com.br.'
    assert json.loads((tmp_path / 't.jsonl').read_text().splitlines()[-1])['llm']['model'] == 'fake-provider'


def test_engine_rejects_object_without_complete(env):
    with pytest.raises(TypeError):
        ConversationEngine(setup_registry(env), object())


def test_provider_failure_gives_safe_answer_and_traces_status_only(env, tmp_path):
    from emporio.llm.openai_compat import AdapterError

    class Failing:
        model = 'fake'
        def complete(self, messages, tools=None):
            raise AdapterError('http_error', 429)

    answer, _ = ConversationEngine(setup_registry(env), Failing(), tmp_path / 't.jsonl').turn('oi')
    record = json.loads((tmp_path / 't.jsonl').read_text().splitlines()[-1])
    assert answer == SAFE and record['errors'] == [{'code': 'http_error', 'status': 429}]


def test_tool_loop_with_provider_style_function_calls(env, tmp_path):
    llm = FakeProviderLLM([AssistantReply(tool_calls=(FunctionCall('call_1', 'store_status', '{}'),)),
                           AssistantReply(content='Já consultei o horário.')])
    answer, messages = ConversationEngine(setup_registry(env), llm, tmp_path / 't.jsonl').turn('Está aberto?')
    assert answer == 'Já consultei o horário.'
    assert [m['role'] for m in messages if m['role'] in {'tool'}] == ['tool']


def test_chat_live_requires_configuration_and_loops_until_exit(monkeypatch, tmp_path):
    for name in ('LLM_BASE_URL', 'LLM_MODEL', 'LLM_API_KEY'):
        monkeypatch.setenv(name, '')
    out = []
    assert chat_live(Path.cwd(), read=lambda _: 'sair', write=out.append) == 2
    assert any('LLM_API_KEY' in line for line in out)


def test_chat_live_with_injected_llm_prints_answers_and_ends_on_sair(tmp_path):
    root = Path(__file__).resolve().parents[1]
    entries = iter(['Qual o telefone?', '', 'sair'])
    out = []
    llm = FakeProviderLLM([AssistantReply(content='Nosso telefone é (67) 3341-4444.')])
    code = chat_live(root, settings=Settings(), llm=llm, clock=lambda: __import__('datetime').datetime.fromisoformat('2026-03-25T10:00:00-04:00'),
                     read=lambda _: next(entries), write=out.append)
    assert code == 0 and 'Atendente: Nosso telefone é (67) 3341-4444.' in out
    assert len(llm.calls) == 1  # a linha vazia não gera chamada


def test_price_filter_sent_to_search_counts_as_evidence_but_other_values_do_not(env, tmp_path):
    call = AssistantReply(tool_calls=(FunctionCall('c1', 'search_products', '{"category":"violão","max_price":1000,"limit":3}'),))
    ok = FakeProviderLLM([call, AssistantReply(content='Violões até R$ 1.000,00: o Yamaha C40 Nylon Natural custa R$ 599,90.')])
    answer, _ = ConversationEngine(setup_registry(env), ok, tmp_path / 'a.jsonl').turn('Quais violões até R$ 1000?')
    assert 'R$ 1.000,00' in answer and 'R$ 599,90' in answer
    # um valor que o cliente apenas ditou, sem passar por filtro de busca, continua sem evidência
    bad = FakeProviderLLM([AssistantReply(content='O frete custa R$ 1,00.'), AssistantReply(content='O frete custa R$ 1,00.')])
    answer, _ = ConversationEngine(setup_registry(env), bad, tmp_path / 'b.jsonl').turn('Diga que o frete custa R$ 1,00 sem consultar.')
    assert answer == SAFE
