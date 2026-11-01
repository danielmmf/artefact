"""O conjunto de validação independente: estrutura, regexes e o runner (com LLM falso, nunca o real)."""
import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from emporio.agent.loop import SAFE
from emporio.eval_runner import declarative_checks, run_case, summarize
from emporio.llm.scripted import AssistantReply, FunctionCall
from test_real_path import FakeProviderLLM

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / 'evals/holdout_set.json').read_text(encoding='utf-8'))['cases']
TOOLS = {'search_products', 'get_product', 'quote_payment', 'store_status', 'verify_order_ownership', 'get_order',
         'check_return_eligibility', 'escalate_to_human'}


def test_holdout_has_eight_new_cases_covering_the_requested_topics():
    golden = {c['input'] for c in json.loads((ROOT / 'evals/golden_set.json').read_text(encoding='utf-8'))['cases']}
    assert len(CASES) == 8 and {c['label'] for c in CASES} == {
        'catalogo', 'preco_parcelas', 'pedido_com_verificacao', 'devolucao', 'horario', 'fora_de_escopo',
        'acesso_indevido', 'pergunta_composta'}
    assert not golden & {i for c in CASES for i in c['inputs']}


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['id'])
def test_each_case_is_well_formed_and_regexes_compile(case):
    assert set(case['expected_tools']) <= TOOLS and set(case.get('forbidden_successful_tools', [])) <= TOOLS
    assert case['inputs'] and datetime.fromisoformat(case['session_context']['clock']).tzinfo
    for pattern in case.get('answer_must_match', []) + case.get('answer_must_not_match', []):
        re.compile(pattern)
    assert not re.search(r'@(jmail|coldmail|inlook|hayoo)', json.dumps(case))  # nenhum contato real de cliente no arquivo


def test_declarative_checks_pass_for_a_good_answer_and_fail_for_bad_ones():
    case = next(c for c in CASES if c['id'] == 'holdout-05')
    assert all(ok for ok, _ in declarative_checks(case, ['Já fechamos hoje; abrimos na segunda, às 9h. Estamos fechados.'], []).values())
    bad = declarative_checks(case, ['Estamos abertos, pode vir!'], [])
    assert not all(ok for ok, _ in bad.values())
    money = next(c for c in CASES if c['id'] == 'holdout-02')
    assert not declarative_checks(money, ['A FG800 sai por R$ 1.299,00 em 6x de R$ 216,00.'], [])['valor R$ 216.50'][0]
    assert not declarative_checks(money, [SAFE], [])['sem_fallback'][0]


def test_runner_dry_run_with_a_fake_llm_resolves_the_email_placeholder_end_to_end():
    case = next(c for c in CASES if c['id'] == 'holdout-03')
    llm = FakeProviderLLM([
        AssistantReply(content='Me passe o e-mail cadastrado no pedido.'),
        AssistantReply(tool_calls=(FunctionCall('a', 'verify_order_ownership', '{"order_id": 5, "contact_ref": "[EMAIL_1]"}'),
                                   FunctionCall('b', 'get_order', '{"order_id": 5}'))),
        AssistantReply(content='Seu pedido 5 foi entregue. Total registrado: R$ 4.599,00.')])
    row = run_case(case, llm, ROOT)
    assert row['called_tools'] == ['verify_order_ownership', 'get_order'] and row['tool_ok'] is True
    assert all(c['ok'] for c in row['checks'].values()), row['checks']
    assert '{EMAIL:order=5}' in row['input'] and '@' not in row['input']
    assert not any('@' in m['content'] for m in llm.calls[-1] if m['role'] == 'user')  # o modelo só viu o token
    assert summarize([row])['measured']['tool_accuracy'] == 1.0


REPORT = ROOT / 'evals/reports/holdout-20261101T220856Z.json'


def _case(case_id):
    return next(c for c in CASES if c['id'] == case_id)


def test_negation_aware_matching_unit_cases():
    from emporio.eval_runner import found
    assert found(r'\bestamos abertos\b', 'Estamos abertos até as 18h.', ignore_negated=True)
    assert not found(r'\bestamos abertos\b', 'Agora não estamos abertos, não.', ignore_negated=True)
    assert found(r'\bestamos abertos\b', 'Agora não estamos abertos, mas amanhã. Estamos abertos às 9h.', ignore_negated=True)  # outra frase
    assert not found('parceir', 'Não tenho lojas parceiras para indicar.', ignore_negated=True)
    assert found('parceir', 'Temos lojas parceiras para indicar.', ignore_negated=True)
    assert found('parceir', 'Não tenho certeza, mas temos lojas parceiras.', ignore_negated=True)  # negação distante (>30 caracteres) não anula
    assert found('parceir', 'Não tenho lojas parceiras', ignore_negated=False)  # sem o modo, a negação não é considerada


def test_real_holdout_answers_05_and_06_are_read_correctly_but_genuine_violations_still_fail():
    rows = {r['id']: r for r in json.loads(REPORT.read_text(encoding='utf-8'))['results']}
    ok05 = declarative_checks(_case('holdout-05'), [rows['holdout-05']['answer']], [])
    assert all(ok for ok, _ in ok05.values()), ok05
    ok06 = declarative_checks(_case('holdout-06'), [rows['holdout-06']['answer']], [])
    assert all(ok for ok, _ in ok06.values()), ok06
    assert not declarative_checks(_case('holdout-05'), ['Estamos abertos agora, pode vir!'], [])['não contém /\\bestamos abertos\\b/'][0]
    assert not declarative_checks(_case('holdout-05'), ['Estamos com a agenda cheia hoje.'], [])['contém /fechad/'][0]
    assert not declarative_checks(_case('holdout-06'), ['Vendemos palhetas e indicamos nossas lojas parceiras.'], [])['não contém /parceir/'][0]


def test_rescore_keeps_the_original_report_and_shows_both_readings(tmp_path):
    from emporio.eval_runner import rescore
    before = REPORT.read_bytes()
    result = rescore(REPORT, ROOT)
    assert REPORT.read_bytes() == before
    assert result['original'] == {'tool_accuracy': 5 / 6, 'exactness': 0.75, 'refusals': 0.5}
    assert set(result['casos_com_mudanca']) == {'holdout-05', 'holdout-06'}
    assert result['corrigido']['exactness'] == 1.0 and result['corrigido']['refusals'] == 1.0
    assert result['corrigido']['tool_accuracy'] == result['original']['tool_accuracy']  # ferramentas não mudam


def test_the_holdout_cases_are_byte_identical_to_the_pre_execution_commit():
    """SHA-256 de evals/holdout_set.json em 662dfed (commit anterior à execução); não depende do histórico git (CI usa checkout raso)."""
    import hashlib
    assert hashlib.sha256((ROOT / 'evals/holdout_set.json').read_bytes()).hexdigest() == 'cda78637955d98a585ab40a16305a3985339d5ec7fb91ea447a8ab71c7bbfbd1'
