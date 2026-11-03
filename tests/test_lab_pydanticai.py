"""Segunda arquitetura do lab (PydanticAI) e o harness de comparação: tudo offline, sem credenciais nem rede."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from pydantic_ai import capture_run_messages, models
from pydantic_ai.models.test import TestModel

from emporio.agent.trace import TurnTracer
from emporio.cli import open_registry
from emporio.tools.contracts import ToolResult
from emporio.tools.registry import ToolRegistry
from emporio_lab import cases, compare
from emporio_lab import pydanticai_agent as pai
from emporio_lab import scenario as sc
from emporio_lab.architectures import ARCHITECTURES, PydanticAI, V102

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_real_model_requests():
    previous = models.ALLOW_MODEL_REQUESTS
    models.ALLOW_MODEL_REQUESTS = False          # guia oficial de testes: qualquer chamada real a um provedor falha
    yield
    models.ALLOW_MODEL_REQUESTS = previous


@pytest.fixture(scope='module')
def suite():
    return cases.run_suite(ARCHITECTURES, ROOT)


def test_pydanticai_is_a_native_orchestration_not_a_wrapper_of_the_engine():
    source = (ROOT / 'src/emporio_lab/pydanticai_agent.py').read_text(encoding='utf-8')
    assert 'import ConversationEngine' not in source and 'ConversationEngine(' not in source and 'from emporio.agent.loop import SAFE' in source
    assert PydanticAI.orchestrator is pai.PydanticAIAgent and V102.orchestrator is not pai.PydanticAIAgent
    assert type(pai.agent).__module__.startswith('pydantic_ai') and set(pai.toolset.tools) == set(pai.DESCRIPTIONS)


def test_all_eight_tools_are_exposed_by_the_framework_with_typed_schemas():
    definitions = {d['function']['name']: d['function']['parameters'] for d in pai.tool_definitions()}
    assert len(definitions) == 8 and definitions['get_order']['properties']['order_id']['type'] == 'integer'
    assert definitions['check_return_eligibility']['required'] == ['order_id', 'reason']


def test_testmodel_drives_every_tool_through_the_shared_registry_without_credentials():
    with open_registry(ROOT, None, lambda: cases.FIXED_NOW) as registry:
        seen = []
        original = registry.dispatch
        registry.dispatch = lambda name, args: (seen.append(name), original(name, args))[1]
        deps = pai.Deps(registry, TurnTracer('s', None).new(), 'sistema', 'oi', [], frozenset())
        with capture_run_messages() as messages:
            result = pai.agent.run_sync('oi', deps=deps, model=TestModel(custom_output_text='Olá!'))
    assert result.output == 'Olá!' and sorted(seen) == sorted(pai.DESCRIPTIONS) and len(messages) >= 3


def test_functional_suite_has_parity_and_no_critical_regression(suite):
    summary = suite['resumo']
    assert summary['ferramentas_cobertas'] == sorted(pai.DESCRIPTIONS)
    for architecture in ARCHITECTURES:
        assert summary[architecture] == {'casos_reprovados': 0, 'concessoes_indevidas_de_acesso': 0, 'precos_inventados_aceitos': 0, 'regressoes_de_privacidade': 0}
    assert summary['divergencias_em_casos_criticos'] == 0 and summary['divergencias_em_casos_com_paridade'] == 0


def test_both_paths_reach_the_same_domain_layer_with_the_same_calls(suite):
    for row in suite['casos']:
        if row['paridade_esperada']:
            domain = [suite['detalhe']['v1.0.2'][row['caso']]['signature']['dominio'], suite['detalhe']['pydantic-ai'][row['caso']]['signature']['dominio']]
            assert domain[0] == domain[1], row['caso']
    assert any(suite['detalhe']['pydantic-ai'][r['caso']]['signature']['dominio'] for r in suite['casos'])


def test_known_orchestration_differences_are_measured_not_hidden(suite):
    differences = {r['caso']: r['divergencias'] for r in suite['casos'] if not r['paridade_esperada']}
    assert set(differences) == {'ferramenta-inexistente', 'argumentos-nao-json', 'tipo-de-argumento-invalido'}
    assert all(d == ['dominio'] for d in differences.values())          # só o caminho até o domínio muda; resposta e histórico coincidem
    pai_calls = {c: suite['detalhe']['pydantic-ai'][c]['signature']['dominio'] for c in differences}
    assert all(calls == [] for calls in pai_calls.values())            # o framework rejeita antes do domínio e pede nova tentativa ao modelo


def test_suite_detects_a_sabotaged_money_validator(monkeypatch):
    monkeypatch.setattr(pai, 'supported_money', lambda *a, **k: True)
    result = cases.run_suite({'pydantic-ai': PydanticAI}, ROOT)
    assert result['resumo']['pydantic-ai']['precos_inventados_aceitos'] > 0 and result['resumo']['pydantic-ai']['casos_reprovados'] > 0


def test_suite_detects_a_sabotaged_privacy_barrier(monkeypatch):
    monkeypatch.setattr(pai, 'protect_dynamic', lambda value, vault: value)
    result = cases.run_suite({'pydantic-ai': PydanticAI}, ROOT)
    assert result['resumo']['pydantic-ai']['regressoes_de_privacidade'] > 0


def test_suite_detects_an_access_grant_to_a_stranger(monkeypatch):
    original = ToolRegistry.dispatch

    def broken(self, name, args):
        result = original(self, name, args)
        return ToolResult(ok=True, data={'order': 'vazado'}) if name in cases.ACCESS_TOOLS else result
    monkeypatch.setattr(ToolRegistry, 'dispatch', broken)
    result = cases.run_suite({'pydantic-ai': PydanticAI}, ROOT)
    assert result['resumo']['pydantic-ai']['concessoes_indevidas_de_acesso'] > 0


def test_each_run_uses_an_isolated_copy_and_leaves_the_real_state_untouched():
    before = {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in (ROOT / 'var').glob('*.db')}
    with cases.isolated_root(ROOT) as first:
        assert sorted(p.name for p in (first / 'var').iterdir()) == ['store.db']
        PydanticAI().run_user(first, [__import__('emporio_lab.synthetic', fromlist=['Turn']).Turn(0, 0, 'conversa', 'Oi, tudo bem?')], 0)
        assert (first / 'var/app.db').exists()
    with cases.isolated_root(ROOT) as second:
        assert not (second / 'var/app.db').exists() and not first.exists()
    assert before == {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in (ROOT / 'var').glob('*.db')}


def test_token_estimate_reflects_what_each_framework_really_sends(suite):
    static = compare.static_metrics(ROOT)
    assert static['v1.0.2']['tokens_esquemas_ferramentas'] > 0 and static['pydantic-ai']['tokens_esquemas_ferramentas'] > 0
    assert static['pydantic-ai']['pacotes_adicionais'] >= 3 and 'pydantic-ai-slim' in static['pydantic-ai']['pacotes_adicionais_lista']


# --- pré-registro -------------------------------------------------------------------------------------------------
def git(cwd, *args):
    return subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, 'init', '-q')
    data = yaml.safe_load((ROOT / 'scenarios/S0-baseline.yaml').read_text(encoding='utf-8'))
    data['arquiteturas'] = ['v1.0.2', 'pydantic-ai']
    data['parametros'].update(repeticoes=3, alternar_ordem=True)
    data['nome'] = 'S9-par'
    data['protocolo'] = 'docs/PROTOCOLO.md'
    data['relatorio_em'] = 'S9-par'
    (tmp_path / 'scenarios').mkdir()
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'scenarios/S9-par.yaml').write_text(yaml.safe_dump(data, allow_unicode=True), encoding='utf-8')
    (tmp_path / 'docs/PROTOCOLO.md').write_text('protocolo', encoding='utf-8')
    git(tmp_path, 'add', '.')
    git(tmp_path, 'commit', '-qm', 'criterios')
    return tmp_path


def check(repo):
    return compare.verify_preregistration(sc.load('S9-par', repo), repo, None, datetime.now(timezone.utc))


def test_preregistration_needs_a_record_committed_after_the_criteria(repo):
    assert check(repo)[0] is False and 'ausente' in check(repo)[2]
    compare.preregister('S9-par', repo)
    assert check(repo)[0] is False and 'não está commitado' in check(repo)[2]
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'registro')
    ok, record, why = check(repo)
    assert ok and why == 'ok' and record['commit_dos_criterios'] == git(repo, 'rev-parse', 'HEAD~1')
    assert record['arquivos_sha256']['scenarios/S9-par.yaml'] == hashlib.sha256((repo / 'scenarios/S9-par.yaml').read_bytes()).hexdigest()


def test_preregistration_rejects_a_criteria_file_changed_after_registration(repo):
    compare.preregister('S9-par', repo)
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'registro')
    path = repo / 'scenarios/S9-par.yaml'
    path.write_text(path.read_text(encoding='utf-8').replace('valor: 0', 'valor: 1', 1), encoding='utf-8')
    git(repo, 'commit', '-qam', 'afrouxa critério')                      # rastreado e limpo, mas diferente do registrado
    ok, _, why = check(repo)
    assert ok is False and 'difere do que foi registrado' in why


def test_preregistration_refuses_uncommitted_criteria_and_same_commit_records(repo):
    (repo / 'docs/PROTOCOLO.md').write_text('mudou', encoding='utf-8')
    with pytest.raises(sc.ScenarioError):
        compare.preregister('S9-par', repo)
    git(repo, 'checkout', '--', 'docs/PROTOCOLO.md')
    record = compare.preregister('S9-par', repo)
    git(repo, 'add', '.')
    git(repo, 'commit', '--amend', '-qm', 'criterios e registro juntos')   # registro no mesmo commit dos critérios
    assert record.exists() and check(repo)[0] is False
