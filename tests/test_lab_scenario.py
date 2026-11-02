"""Formato dos cenários do lab: os critérios existem antes da execução e cenário planejado não roda."""
from pathlib import Path

import pytest
import yaml

from emporio_lab import scenario as sc

ROOT = Path(__file__).resolve().parents[1]


def valid(**override):
    data = {'nome': 'S9-teste', 'status': 'mensuravel', 'descricao': 'Cenário de teste do formato.',
            'mudanca_em_relacao_a_v1_0_2': 'nada', 'hipotese': 'nenhuma', 'arquiteturas': ['v1.0.2'],
            'parametros': {'usuarios_simultaneos': 1, 'turnos_por_usuario': 1, 'tamanho_do_catalogo': 1,
                           'tamanho_do_conhecimento': 'x', 'requisitos_de_fluxo': 'x', 'latencia_llm_simulada_ms': 0, 'seed': 1},
            'metricas': [{'id': 'm1', 'descricao': 'uma métrica', 'unidade': 'ms', 'tipo': 'criterio',
                          'criterio': {'operador': '<=', 'valor': 10}}]}
    data.update(override)
    return data


def write(tmp_path, data, name='S9-teste'):
    (tmp_path / 'scenarios').mkdir(exist_ok=True)
    (tmp_path / 'scenarios' / f'{name}.yaml').write_text(yaml.safe_dump(data, allow_unicode=True), encoding='utf-8')


def test_the_five_initial_scenarios_load_and_only_s0_is_measurable():
    scenarios = {s.nome: s for s in sc.list_all(ROOT)}
    assert list(scenarios) == ['S0-baseline', 'S1-mil-usuarios', 'S2-catalogo-grande', 'S3-conhecimento-grande', 'S4-fluxo-com-aprovacao']
    assert [n for n, s in scenarios.items() if s.status == 'mensuravel'] == ['S0-baseline']
    for name in ('S1-mil-usuarios', 'S2-catalogo-grande', 'S3-conhecimento-grande', 'S4-fluxo-com-aprovacao'):
        assert scenarios[name].status == 'planejado' and scenarios[name].metricas == [] and scenarios[name].hipotese


def test_s0_declares_its_criteria_and_conditions_before_any_run():
    s0 = sc.load('S0-baseline', ROOT)
    assert s0.parametros.tamanho_do_catalogo == 65 and s0.parametros.usuarios_simultaneos == 5 and s0.arquiteturas == ['v1.0.2']
    criteria = {m.id: m.criterio.texto() for m in s0.metricas if m.tipo == 'criterio'}
    assert criteria == {'erros_de_execucao': '== 0', 'contingencias_seguras': '== 0', 'sobrecarga_local_p95_ms': '<= 100',
                        'busca_recall_at_5': '== 0.8', 'busca_mrr': '== 0.75'}
    assert {m.id for m in s0.metricas if m.tipo == 'referencia'} >= {'latencia_turno_p50_ms', 'vazao_turnos_por_s', 'tokens_prompt_estimados_p50'}


def test_criterion_evaluation():
    c = sc.Criterio(operador='<=', valor=100)
    assert c.satisfeito(100) and c.satisfeito(3) and not c.satisfeito(100.1)
    assert sc.Criterio(operador='==', valor=0).satisfeito(0) and not sc.Criterio(operador='==', valor=0).satisfeito(1)


@pytest.mark.parametrize('mutation, message', [
    ({'metricas': []}, 'ao menos uma métrica com critério'),
    ({'metricas': [{'id': 'm1', 'descricao': 'sem critério', 'unidade': 'ms', 'tipo': 'criterio'}]}, 'exige criterio'),
    ({'metricas': [{'id': 'm1', 'descricao': 'só referência', 'unidade': 'ms', 'tipo': 'referencia'}]}, 'ao menos uma métrica com critério'),
    ({'metricas': [{'id': 'm1', 'descricao': 'referência com critério', 'unidade': 'ms', 'tipo': 'referencia',
                    'criterio': {'operador': '<=', 'valor': 1}}]}, 'não tem criterio'),
    ({'arquiteturas': []}, 'lista de arquiteturas'),
    ({'parametros': None}, 'exige parametros'),
    ({'metricas': [{'id': 'm1', 'descricao': 'primeira', 'unidade': 'ms', 'tipo': 'criterio', 'criterio': {'operador': '<=', 'valor': 1}},
                   {'id': 'm1', 'descricao': 'duplicada', 'unidade': 'ms', 'tipo': 'referencia'}]}, 'duplicados'),
])
def test_a_measurable_scenario_without_pre_registered_criteria_is_rejected(tmp_path, mutation, message):
    write(tmp_path, valid(**mutation))
    with pytest.raises(sc.ScenarioError, match=message):
        sc.load('S9-teste', tmp_path)


def test_name_must_match_file_and_path_traversal_is_rejected(tmp_path):
    write(tmp_path, valid(nome='S8-outro'), name='S9-teste')
    with pytest.raises(sc.ScenarioError, match='declara nome'):
        sc.load('S9-teste', tmp_path)
    with pytest.raises(sc.ScenarioError, match='inválido'):
        sc.load('../secrets', tmp_path)
    with pytest.raises(sc.ScenarioError, match='não existe'):
        sc.load('S7-inexistente', tmp_path)


def test_unknown_fields_are_rejected_so_typos_do_not_silently_drop_criteria(tmp_path):
    data = valid()
    data['metricas'][0]['criteiro'] = {'operador': '<=', 'valor': 1}
    write(tmp_path, data)
    with pytest.raises(sc.ScenarioError):
        sc.load('S9-teste', tmp_path)
