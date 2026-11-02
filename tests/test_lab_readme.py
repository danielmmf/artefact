"""O README do lab só tem conclusão para cenário medido, e ela é a do relatório (não digitada à mão)."""
import json
import re
from pathlib import Path

from emporio_lab import scenario as sc

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / 'scenarios/README.md').read_text(encoding='utf-8')


def section(name):
    match = re.search(rf'^## {re.escape(name)}\n(.*?)(?=^## |\Z)', README, re.MULTILINE | re.DOTALL)
    assert match, f'README do lab sem seção {name}'
    return match.group(1)


def test_every_scenario_has_a_section_and_only_measured_ones_have_a_conclusion():
    for s in sc.list_all(ROOT):
        body = section(s.nome)
        report = ROOT / 'reports/scenarios' / s.nome / 'report.json'
        if s.status == 'mensuravel' and report.exists():
            assert '**Conclusão:** Se o cenário mudar para' in body
        else:
            assert 'Conclusão: nenhuma (sem medição)' in body and 'Se o cenário mudar para' not in body
            assert not report.exists(), f'{s.nome} tem relatório mas está planejado'


def test_s0_conclusion_in_the_readme_is_the_one_in_the_report_and_has_the_required_form():
    report = json.loads((ROOT / 'reports/scenarios/S0-baseline/report.json').read_text(encoding='utf-8'))
    assert f"**Conclusão:** {report['conclusao']}" in section('S0-baseline')
    assert re.fullmatch(r'Se o cenário mudar para .+, o gargalo medido foi .+, e a arquitetura recomendada é .+, pelos números: .+\.', report['conclusao'])
    assert report['execucao']['criterios_pre_registrados'] is True and report['dados']['sinteticos'] is True
    assert all(row['resultado'] in ('atendido', 'referência') for row in report['avaliacao'])


def test_the_status_table_matches_the_scenario_files():
    for s in sc.list_all(ROOT):
        label = 'medido' if s.status == 'mensuravel' else 'planejado'
        assert re.search(rf'\| {re.escape(s.nome)} \| {label} \|', README), s.nome
