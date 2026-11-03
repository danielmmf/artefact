"""Carga sintética, LLM simulado e runner do lab (com condições mínimas, só para testar o mecanismo)."""
import json
from pathlib import Path

import pytest
import yaml

from emporio_lab import runner
from emporio_lab import scenario as sc
from emporio_lab.cli import main as lab_main
from emporio_lab.simllm import SimulatedLLM, brl
from emporio_lab.synthetic import build_workload, fingerprint, kind_counts

ROOT = Path(__file__).resolve().parents[1]
NAMES = ['Yamaha C40 Nylon Natural', 'Takamine GD20 Dreadnought Natural', 'Kala KA-15S Soprano Mogno']


def test_workload_is_deterministic_by_seed_and_changes_with_it():
    a, b, c = (build_workload(NAMES, 3, 10, seed) for seed in (7, 7, 8))
    assert fingerprint(a) == fingerprint(b) and fingerprint(a) != fingerprint(c)
    assert [len(u) for u in a] == [10, 10, 10] and sum(kind_counts(a).values()) == 30
    assert all(t.text for u in a for t in u) and {t.kind for u in a for t in u} <= {'preco', 'listagem', 'horario', 'conversa'}
    with pytest.raises(ValueError):
        build_workload([], 1, 1, 1)


def test_money_format_matches_the_validator_expectations():
    assert brl('2199') == '2.199,00' and brl('1967.18') == '1.967,18' and brl('0.5') == '0,50'


def test_simulated_llm_answers_are_grounded_and_pay_the_artificial_latency():
    llm = SimulatedLLM(latency_ms=20)
    reply = llm.complete([{'role': 'user', 'content': 'Quanto custa o Takamine GD20 Dreadnought Natural?'}])
    call = reply.tool_calls[0]
    assert call.name == 'get_product' and json.loads(call.arguments_json) == {'name': 'Takamine GD20 Dreadnought Natural'}
    tool_result = {'ok': True, 'data': {'name': 'Takamine GD20', 'stock_quantity': 5, 'price_info': {'final_price': '2199'}}}
    messages = [{'role': 'user', 'content': 'x'}, {'role': 'assistant', 'content': '', 'tool_calls': [{'id': call.call_id, 'type': 'function',
                'function': {'name': 'get_product', 'arguments': call.arguments_json}}]},
                {'role': 'tool', 'tool_call_id': call.call_id, 'content': json.dumps(tool_result)}]
    assert 'R$ 2.199,00' in llm.complete(messages).content
    assert llm.calls == 2 and llm.busy_seconds >= 0.04
    assert llm.complete([{'role': 'user', 'content': 'Oi, tudo bem?'}]).tool_calls == ()


def tiny_scenario(tmp_path, **override):
    data = {'nome': 'S9-mini', 'status': 'mensuravel', 'descricao': 'Mini cenário só para testar o mecanismo.',
            'mudanca_em_relacao_a_v1_0_2': 'nada', 'hipotese': 'o mecanismo roda', 'arquiteturas': ['v1.0.2'],
            'parametros': {'usuarios_simultaneos': 2, 'turnos_por_usuario': 4, 'tamanho_do_catalogo': 65,
                           'tamanho_do_conhecimento': 'manual', 'requisitos_de_fluxo': 'síncrono', 'latencia_llm_simulada_ms': 5, 'seed': 3},
            'metricas': [{'id': 'erros_de_execucao', 'descricao': 'erros durante a carga', 'unidade': 'erros', 'tipo': 'criterio',
                          'criterio': {'operador': '==', 'valor': 0}},
                         {'id': 'contingencias_seguras', 'descricao': 'contingências', 'unidade': 'respostas', 'tipo': 'criterio',
                          'criterio': {'operador': '==', 'valor': 0}},
                         {'id': 'vazao_turnos_por_s', 'descricao': 'vazão', 'unidade': 'turnos/s', 'tipo': 'referencia'}]}
    data.update(override)
    (tmp_path / 'scenarios').mkdir(exist_ok=True)
    (tmp_path / 'scenarios' / 'S9-mini.yaml').write_text(yaml.safe_dump(data, allow_unicode=True), encoding='utf-8')


def run_tiny(tmp_path, **kwargs):
    lines = []
    code = runner.run('S9-mini', ROOT, scenarios_root=tmp_path, reports_root=tmp_path / 'out', out=lines.append, **kwargs)
    return code, '\n'.join(lines)


def test_runner_runs_the_v102_under_load_and_writes_the_comparable_report(tmp_path):
    tiny_scenario(tmp_path)
    code, output = run_tiny(tmp_path, allow_dirty=True)
    assert code == 0 and 'CENÁRIO S9-mini' in output and 'SINTÉTICO' in output and 'Conclusão: Se o cenário mudar para' in output
    report = json.loads((tmp_path / 'out/S9-mini/report.json').read_text(encoding='utf-8'))
    assert report['dados']['sinteticos'] is True and report['execucao']['criterios_pre_registrados'] is False
    assert report['metricas']['turnos'] == 8 and report['metricas']['erros_de_execucao'] == 0 and report['metricas']['contingencias_seguras'] == 0
    assert report['metricas']['tokens_prompt_estimados_p50'] > 1000          # o manual vai inteiro no prompt
    assert {r['resultado'] for r in report['avaliacao']} == {'atendido', 'referência'}
    md = (tmp_path / 'out/S9-mini/report.md').read_text(encoding='utf-8')
    assert 'Dados sintéticos (SINTÉTICO)' in md and '## Conclusão' in md and 'NÃO' in md        # NÃO pré-registrado, por causa do --allow-dirty


def test_same_seed_gives_the_same_workload_fingerprint_in_two_runs(tmp_path):
    tiny_scenario(tmp_path)
    run_tiny(tmp_path, allow_dirty=True)
    first = json.loads((tmp_path / 'out/S9-mini/report.json').read_text(encoding='utf-8'))['dados']['workload_sha256']
    run_tiny(tmp_path, allow_dirty=True)
    assert json.loads((tmp_path / 'out/S9-mini/report.json').read_text(encoding='utf-8'))['dados']['workload_sha256'] == first


def test_runner_refuses_a_scenario_whose_criteria_are_not_committed(tmp_path):
    tiny_scenario(tmp_path)                              # fora de um repositório git: não há pré-registro
    code, output = run_tiny(tmp_path)
    assert code == runner.EXIT_NOT_PREREGISTERED and 'não está commitado' in output
    assert not (tmp_path / 'out').exists()               # nada foi medido


def test_runner_refuses_planned_and_unknown_scenarios_without_measuring(tmp_path):
    for name in ('S1-mil-usuarios', 'S4-fluxo-com-aprovacao'):
        lines = []
        assert runner.run(name, ROOT, reports_root=tmp_path / 'out', out=lines.append) == runner.EXIT_INVALID
        assert 'planejado' in '\n'.join(lines) and 'Sem medição não há conclusão' in '\n'.join(lines)
    lines = []
    assert runner.run('S7-nao-existe', ROOT, out=lines.append) == runner.EXIT_INVALID
    assert not (tmp_path / 'out').exists()


def test_failed_criterion_is_reported_and_only_strict_mode_turns_it_into_an_error(tmp_path):
    tiny_scenario(tmp_path, metricas=[{'id': 'sobrecarga_local_p95_ms', 'descricao': 'critério impossível de propósito', 'unidade': 'ms',
                                       'tipo': 'criterio', 'criterio': {'operador': '<=', 'valor': 0}}])
    code, output = run_tiny(tmp_path, allow_dirty=True)
    assert code == 0 and 'reprovado' in output and 'critérios reprovados' in output
    code, _ = run_tiny(tmp_path, allow_dirty=True, strict=True)
    assert code == runner.EXIT_CRITERIA_FAILED


def test_unknown_architecture_is_refused(tmp_path):
    tiny_scenario(tmp_path, arquiteturas=['v1.0.2', 'outra'], parametros={**yaml.safe_load(open(ROOT / 'scenarios/S0-baseline.yaml'))['parametros'], 'repeticoes': 3, 'alternar_ordem': True})
    code, output = run_tiny(tmp_path, allow_dirty=True)
    assert code == runner.EXIT_INVALID and 'arquitetura desconhecida' in output


def test_comparison_demands_three_repetitions_with_alternating_order(tmp_path):
    tiny_scenario(tmp_path, arquiteturas=['v1.0.2', 'pydantic-ai'])
    code, output = run_tiny(tmp_path, allow_dirty=True)
    assert code == runner.EXIT_INVALID and 'ao menos 3 repetições' in output


def test_scenario_list_shows_one_short_line_per_scenario(capsys):
    assert lab_main(['scenario', 'list']) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 5 and lines[0].startswith('S0-baseline') and all(len(l) < 160 for l in lines)
    assert sum('planejado' in l for l in lines) == 4


def test_percentile_is_nearest_rank():
    assert runner.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50) == 5 and runner.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10
    assert runner.percentile([], 95) == 0.0 and runner.percentile([4], 95) == 4
