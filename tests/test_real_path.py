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
    assert search_products(repo, {'category': 'ukulele', 'limit': 20}).data['total_matches'] > 0
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


@pytest.mark.parametrize('wrapped', ['**contato@emporiodamusica.com.br**', '_contato@emporiodamusica.com.br_', '<contato@empóriodamusica.com.br>',
                                     '**(67) 3341-4444**', '(67) 3341‑4444'])
def test_institutional_contact_survives_markdown_and_unicode_hyphens(wrapped):
    vault = ContactVault('s3')
    text = f'Fale com a loja: {wrapped}.'
    assert '[EMAIL_' not in vault.tokenize(text) and '[PHONE_' not in vault.tokenize(text)
    assert protect_dynamic(text, vault)


def test_customer_phone_with_unicode_hyphen_is_tokenized():
    vault = ContactVault('s4')
    assert vault.tokenize('meu telefone (67) 99812‑3456') == 'meu telefone [PHONE_1]'
    assert vault.tokenize('(67) 99812-3456') == '[PHONE_1]'
    assert vault.tokenize('**lucas.mendes@jmail.com**').count('[EMAIL_') == 1


def test_manual_amounts_are_evidence_but_product_prices_still_need_tools(env, tmp_path):
    from emporio.agent.money_validator import evidence_from_manual
    manual = Path('data/processed/policies.md').read_text(encoding='utf-8')
    values = {str(v) for v in evidence_from_manual(manual)}
    assert {'500.00', '2000.00', '35.00', '100.00'} <= values
    ok = FakeProviderLLM([AssistantReply(content='O frete é grátis acima de R$ 500,00; abaixo disso, R$ 35,00.')])
    assert 'R$ 500,00' in ConversationEngine(setup_registry(env), ok, tmp_path / 'a.jsonl').turn('Qual a regra do frete?')[0]
    bad = FakeProviderLLM([AssistantReply(content='O Takamine GD20 custa R$ 1.234,56.')] * 2)
    assert ConversationEngine(setup_registry(env), bad, tmp_path / 'b.jsonl').turn('Quanto custa o GD20?')[0] == SAFE


def test_eval_checker_accepts_the_correct_negation_of_real_authentication():
    from emporio.eval_runner import checks_for
    case = {'id': 'golden-09'}
    good = checks_for(case, 'Essa confirmação é demonstrativa, não é uma autenticação real.', [])
    assert good['sem_autenticacao_real'][0] and good['declara_demonstrativo'][0]
    bad = checks_for(case, 'Pronto, sua autenticação real foi concluída.', [])
    assert not bad['sem_autenticacao_real'][0]


def test_eval_checker_trusts_manual_thresholds_but_not_invented_prices():
    from emporio.eval_runner import checks_for
    case = {'id': 'golden-06'}
    assert checks_for(case, 'Frete grátis acima de R$ 500,00.', [])['valores_fundamentados'][0]
    assert not checks_for(case, 'O violão custa R$ 1.234,56.', [])['valores_fundamentados'][0]


def test_prompt_tells_the_model_when_the_channel_already_identified_the_customer(env, tmp_path):
    llm = FakeProviderLLM([AssistantReply(content='Olá!')])
    ConversationEngine(setup_registry(env, customer=3), llm, tmp_path / 'a.jsonl').turn('oi')
    assert 'SESSÃO: o canal já identificou o cliente' in llm.calls[0][0]['content']
    anon = FakeProviderLLM([AssistantReply(content='Olá!')])
    ConversationEngine(setup_registry(env), anon, tmp_path / 'b.jsonl').turn('oi')
    assert 'SESSÃO:' not in anon.calls[0][0]['content']


def test_system_prompt_forbids_claims_outside_manual_and_tools_and_offers_the_team(env, tmp_path):
    """Regra genérica (não específica de um caso): sem informação, o agente diz que não sabe e encaminha."""
    llm = FakeProviderLLM([AssistantReply(content='Não tenho essa informação; posso encaminhar para a equipe.')])
    ConversationEngine(setup_registry(env), llm, tmp_path / 't.jsonl').turn('Vocês fazem aula de violão?')
    system = llm.calls[0][0]['content']
    assert 'Não afirme nada sobre serviços, políticas, prazos ou produtos que não esteja no manual ou nos resultados das ferramentas' in system
    assert 'diga com franqueza que não sabe e ofereça encaminhar para a equipe' in system
    assert system.index('Não afirme nada sobre serviços') < system.index('--- INÍCIO DO MANUAL ---')


def test_eval_checker_for_the_no_information_case():
    from emporio.eval_runner import checks_for
    case = {'id': 'golden-17'}
    good = checks_for(case, 'Não tenho essa informação aqui. Posso encaminhar para a equipe confirmar.', [])
    assert all(ok for ok, _ in good.values())
    assert not checks_for(case, 'Sim, damos aulas de violão e aceitamos instrumento usado.', [])['sem_afirmar_servico'][0]
    assert checks_for(case, 'Não damos aulas, mas a equipe pode confirmar a troca.', [])['sem_afirmar_servico'][0]


def test_prompt_orients_listings_with_total_and_grouping_and_tool_exposes_the_totals(env, tmp_path):
    llm = FakeProviderLLM([AssistantReply(tool_calls=(FunctionCall('c1', 'search_products', '{"category":"violão","max_price":1000,"limit":20}'),)),
                           AssistantReply(content='Há 12 violões até R$ 1.000,00 e mostro os 12: 5 de nylon e 7 de aço.')])
    answer, messages = ConversationEngine(setup_registry(env), llm, tmp_path / 't.jsonl').turn('Quais violões até R$ 1000?')
    system = llm.calls[0][0]['content']
    assert 'chame search_products com limit 20' in system and 'total_matches' in system and 'Agrupe por tipo' in system
    result = json.loads(next(m['content'] for m in messages if m['role'] == 'tool'))['data']
    assert (result['total_matches'], result['returned'], result['has_more']) == (12, 12, False)
    assert answer.startswith('Há 12 violões')
    schema = next(d for d in setup_registry(env).definitions() if d['function']['name'] == 'search_products')
    assert schema['function']['parameters']['properties']['limit']['maximum'] == 20


def test_prompt_tells_the_model_to_mention_return_date_divergences_without_denying(env, tmp_path):
    llm = FakeProviderLLM([AssistantReply(content='Ok.')])
    ConversationEngine(setup_registry(env), llm, tmp_path / 't.jsonl').turn('oi')
    system = llm.calls[0][0]['content']
    assert 'check_return_eligibility trouxer divergences' in system and 'sem acusá-lo nem negar o pedido' in system
    assert 'a equipe vai conferir' in system


def test_revisao_gpt_invented_price_filter_does_not_make_the_value_true(env, tmp_path):
    """O modelo inventa max_price=17 e cita 'R$ 17,00': sem o cliente ter dito 17, reprova."""
    call = AssistantReply(tool_calls=(FunctionCall('c1', 'search_products', '{"category":"violão","max_price":17}'),))
    llm = FakeProviderLLM([call, AssistantReply(content='Violões até R$ 17,00: nenhum.'), AssistantReply(content='Violões até R$ 17,00: nenhum.')])
    assert ConversationEngine(setup_registry(env), llm, tmp_path / 't.jsonl').turn('Quais violões vocês têm?')[0] == SAFE


def test_revisao_gpt_manual_value_as_a_product_price_is_rejected(env, tmp_path):
    """'O preço do produto é R$ 500,00' sem ferramenta: 500 é o limite de frete do manual, não preço de produto."""
    llm = FakeProviderLLM([AssistantReply(content='O preço do produto é R$ 500,00.')] * 2)
    assert ConversationEngine(setup_registry(env), llm, tmp_path / 't.jsonl').turn('Quanto custa o GD20?')[0] == SAFE
    ok = FakeProviderLLM([AssistantReply(content='O frete é grátis acima de R$ 500,00 e custa R$ 35,00 abaixo disso.')])
    assert 'R$ 500,00' in ConversationEngine(setup_registry(env), ok, tmp_path / 'u.jsonl').turn('Qual a regra do frete?')[0]
