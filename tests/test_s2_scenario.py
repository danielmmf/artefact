"""S2: o YAML declara critérios antes da execução, o formato recusa comparações sem repetição e o pré-registro é verificável."""
import json
import subprocess
from pathlib import Path

import pytest
import yaml

from emporio_lab import runner
from emporio_lab import scenario as sc
from emporio_lab.s2 import run as s2

ROOT = Path(__file__).resolve().parents[1]


def test_s2_is_a_measurable_search_scenario_with_four_strategies_and_criteria_declared_up_front():
    s = sc.load('S2-catalogo-grande', ROOT)
    assert s.status == 'mensuravel' and s.tipo == 'busca' and s.arquiteturas == ['A', 'B', 'C', 'D']
    x = s.experimento
    assert x['repeticoes'] >= 3 and x['alternar_ordem'] and x['k'] == 5 and x['decisao_na_escala'] == 'catalogo50k'
    assert [e['produtos'] for e in x['escalas']] == [65, 5000, 50000]
    criteria = {m.id: m.criterio.texto() for m in s.metricas if m.tipo == 'criterio'}
    assert criteria['d_vs_a_delta_ndcg_intencao'] == '>= 0.05' and criteria['c_vs_d_delta_ndcg_intencao'] == '>= 0.03'
    assert criteria['d_vs_a_delta_precisao_nome'] == '>= -0.02' and criteria['p95_e2e_ms'] == '<= 200' and criteria['violacoes_de_filtro'] == '== 0'
    assert criteria['smoke_a_recall_at_5'] == '== 0.8' and criteria['smoke_a_mrr'] == '== 0.75'
    assert 'servidor' in x['qdrant']['modo'] and 'não o modo em processo' in x['qdrant']['modo'] and x['bm25']['idioma'] == 'portuguese'
    assert x['qdrant']['servidor'] == 'qdrant/qdrant:v1.20.0' and x['qdrant']['digest'].startswith('sha256:')
    assert s.protocolo == 'docs/S2-PROTOCOLO.md' and (ROOT / s.protocolo).exists()


def test_every_ordering_is_a_latin_square_row():
    s = sc.load('S2-catalogo-grande', ROOT)
    orders = s.experimento['ordens']
    for position in range(4):
        assert sorted(o[position] for o in orders) == ['A', 'B', 'C', 'D']
    assert all(sorted(o) == ['A', 'B', 'C', 'D'] for o in orders)


def load_dict():
    return yaml.safe_load((ROOT / 'scenarios/S2-catalogo-grande.yaml').read_text(encoding='utf-8'))


@pytest.mark.parametrize('mutation,message', [
    (lambda d: d['experimento'].update(repeticoes=2), 'ao menos 3 repetições'),
    (lambda d: d['experimento'].update(alternar_ordem=False), 'ao menos 3 repetições'),
    (lambda d: d.update(experimento=None), 'exige experimento'),
    (lambda d: d.update(metricas=[m for m in d['metricas'] if m['tipo'] != 'criterio']), 'exige experimento'),
    (lambda d: d.update(arquiteturas=['A']), 'exige experimento'),
])
def test_search_scenario_format_rejects_unmeasurable_setups(mutation, message):
    data = load_dict()
    mutation(data)
    with pytest.raises(Exception, match=message):
        sc.Scenario.model_validate(data)


def test_explain_states_the_strategies_and_the_criteria_before_running():
    text = s2.explain(sc.load('S2-catalogo-grande', ROOT))
    for fragment in ('Qdrant híbrido', 'FTS5 + numpy', 'catalogo50k', 'd_vs_a_delta_ndcg_intencao: >= 0.05', 'p95_e2e_ms: <= 200'):
        assert fragment in text


def git(cwd, *args):
    return subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def test_run_refuses_without_preregistration_and_measures_nothing(tmp_path):
    out = []
    code = s2.run('S2-catalogo-grande', ROOT, reports_root=tmp_path / 'r', out=out.append)
    assert code == runner.EXIT_NOT_PREREGISTERED and 'pré-registro não verificado' in '\n'.join(out)
    assert not (tmp_path / 'r').exists()


def test_preregistration_requires_hashes_of_data_and_a_commit_after_the_criteria(tmp_path):
    s = sc.load('S2-catalogo-grande', ROOT)
    fingerprint = s2.data_fingerprint(s.experimento['seed'])
    assert set(fingerprint['catalogo_sha256']) == {'5000', '50000'} and len(fingerprint['consultas_sha256']) == 64
    assert fingerprint['sobreposicao_de_vocabulario'] == {'nivel_uso_fonte': {}, 'nivel_uso_no_catalogo_50k': {}}
    assert sum(fingerprint['consultas_por_grupo_e_divisao'].values()) == 450


def test_verify_rejects_a_record_without_data_hashes_or_with_different_data(tmp_path, monkeypatch):
    s = sc.load('S2-catalogo-grande', ROOT)
    monkeypatch.setattr(s2.compare, 'verify_preregistration', lambda *a: (True, {'commit_dos_criterios': 'x'}, 'ok'))
    assert s2.verify(s, ROOT, None, None)[0] is False
    monkeypatch.setattr(s2.compare, 'verify_preregistration', lambda *a: (True, {'dados': {'catalogo_sha256': {'5000': '0', '50000': '0'}, 'consultas_sha256': '0'}}, 'ok'))
    ok, _, why = s2.verify(s, ROOT, None, None)
    assert ok is False and 'diferem dos hashes' in why


def test_decision_rule_is_all_or_nothing_and_never_names_a_winner_without_evidence():
    s = sc.load('S2-catalogo-grande', ROOT)
    assert 'Não decidido' in s2.assemble(s, {}, {'git_head': 'x', 'codigo_sem_alteracoes': True}, {'escolhida': {}}, s2.st.Config(), {}, __import__('datetime').datetime.now(), __import__('datetime').datetime.now(), False)['decisao']['veredito']
