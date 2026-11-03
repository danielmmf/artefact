"""Comparação entre arquiteturas num mesmo cenário: pré-registro verificável, estado isolado, repetições alternadas."""
import hashlib
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import time
import tomllib
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from emporio_lab import cases, runner
from emporio_lab import scenario as sc
from emporio_lab.architectures import ARCHITECTURES
from emporio_lab.pydanticai_agent import tool_definitions
from emporio_lab.synthetic import SYNTHETIC_MARK, build_workload, fingerprint, kind_counts

CODE_PATHS = ('src', 'pyproject.toml', 'uv.lock')
PREREG_FILE = 'preregistration.json'


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report_dir(s: sc.Scenario, root: Path, reports_root: Path | None) -> Path:
    return (reports_root or root / runner.REPORTS) / (s.relatorio_em or s.nome)


# --- pré-registro ------------------------------------------------------------------------------------------------------
def frozen_files(s: sc.Scenario, scenarios_root: Path) -> dict[str, Path]:
    files = {f'scenarios/{s.nome}.yaml': sc.path_of(s.nome, scenarios_root)}
    if s.protocolo:
        files[s.protocolo] = scenarios_root / s.protocolo
    return files


def preregister(name: str, scenarios_root: Path, reports_root: Path | None = None) -> Path:
    """Registra o SHA do commit que contém os critérios e o hash de cada arquivo. Exige tudo commitado e sem alterações."""
    s = sc.load(name, scenarios_root)
    shas = {}
    for rel, path in frozen_files(s, scenarios_root).items():
        if runner.git('status', '--porcelain', '--', str(path), cwd=scenarios_root) or not runner.git('ls-files', str(path), cwd=scenarios_root):
            raise sc.ScenarioError(f'{rel} precisa estar commitado e sem alterações antes do pré-registro')
        shas[rel] = sha256_file(path)
    commit = runner.git('log', '-1', '--format=%H', '--', *[str(p) for p in frozen_files(s, scenarios_root).values()], cwd=scenarios_root)
    record = {'cenario': name, 'commit_dos_criterios': commit, 'commit_instante': runner.git('show', '-s', '--format=%cI', commit, cwd=scenarios_root),
              'arquivos_sha256': shas, 'registrado_em': datetime.now(timezone.utc).isoformat(),
              'como_verificar': 'git show <commit>:<arquivo> | sha256sum deve igualar arquivos_sha256; o commit deve ser ancestral do commit da execução.'}
    target = report_dir(s, scenarios_root, reports_root) / PREREG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return target


def verify_preregistration(s: sc.Scenario, scenarios_root: Path, reports_root: Path | None, started: datetime) -> tuple[bool, dict, str]:
    """Prova de pré-registro: o registro existe e foi commitado DEPOIS dos critérios, os arquivos de hoje são byte a byte os do commit
    registrado e esse commit é ancestral do atual. Arquivo 'rastreado e limpo' sozinho não basta."""
    path = report_dir(s, scenarios_root, reports_root) / PREREG_FILE
    if not path.exists():
        return False, {}, f'{PREREG_FILE} ausente: rode `emporio-lab scenario preregister {s.nome}` e commite'
    if runner.git('status', '--porcelain', '--', str(path), cwd=scenarios_root) or not runner.git('ls-files', str(path), cwd=scenarios_root):
        return False, {}, f'{PREREG_FILE} não está commitado'
    record = json.loads(path.read_text(encoding='utf-8'))
    commit = record['commit_dos_criterios']
    if subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'HEAD'], cwd=scenarios_root).returncode != 0:
        return False, record, 'o commit dos critérios não é ancestral do commit atual'
    record_commit = runner.git('log', '-1', '--format=%H', '--', str(path), cwd=scenarios_root)
    if subprocess.run(['git', 'merge-base', '--is-ancestor', commit, record_commit], cwd=scenarios_root).returncode != 0 or commit == record_commit:
        return False, record, 'o registro precisa ser commitado depois do commit dos critérios'
    for rel, expected in record['arquivos_sha256'].items():
        at_commit = subprocess.run(['git', 'show', f'{commit}:{rel}'], capture_output=True, cwd=scenarios_root).stdout
        if hashlib.sha256(at_commit).hexdigest() != expected or sha256_file(scenarios_root / rel) != expected:
            return False, record, f'{rel} difere do que foi registrado'
    if datetime.fromisoformat(record['commit_instante']) > started:
        return False, record, 'o commit dos critérios é posterior à execução'
    return True, record, 'ok'


def code_state(root: Path) -> dict:
    dirty = runner.git('status', '--porcelain', '--', *CODE_PATHS, cwd=root)
    return {'git_head': runner.git('rev-parse', 'HEAD', cwd=root), 'arvore_src_lab': runner.git('rev-parse', 'HEAD:src/emporio_lab', cwd=root),
            'codigo_sem_alteracoes': dirty == '', 'alteracoes': dirty.splitlines()[:10]}


# --- medições estáticas (complexidade, dependências, prompts) ---------------------------------------------------------
def count_lines(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding='utf-8').splitlines() if line.strip() and not line.strip().startswith('#'))


def closure(packages: dict, roots: list[str]) -> set[str]:
    seen, todo = set(), list(roots)
    while todo:
        name = todo.pop()
        if name not in seen and name in packages:
            seen.add(name)
            todo += [d['name'] for d in packages[name].get('dependencies', [])]
    return seen


def dist_size(name: str) -> int:
    try:
        return sum((f.locate().stat().st_size for f in metadata.distribution(name).files or [] if f.locate().exists()), 0)
    except metadata.PackageNotFoundError:
        return 0


def import_ms(module: str, root: Path) -> float:
    times = []
    for _ in range(5):
        started = time.perf_counter()
        subprocess.run([sys.executable, '-c', f'import {module}'], cwd=root, capture_output=True, check=True)
        times.append((time.perf_counter() - started) * 1000)
    return round(min(times), 1)


def bridge_lines(path: Path) -> int:
    text = path.read_text(encoding='utf-8')
    return count_text(text[text.index('# >>> PONTE'):text.index('# <<< PONTE')])


def count_text(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip() and not line.strip().startswith('#'))


def static_metrics(root: Path) -> dict[str, dict]:
    from emporio.agent.history import estimated_tokens
    from emporio.cli import open_registry
    with cases.isolated_root(root) as sandbox, open_registry(sandbox, None, lambda: cases.FIXED_NOW) as registry:
        v102_tools = registry.definitions()
    pai_tools = tool_definitions()
    lock = {p['name']: p for p in tomllib.loads((root / 'uv.lock').read_text(encoding='utf-8'))['package']}
    base = closure(lock, ['pydantic', 'pypdf', 'python-dotenv', 'rapidfuzz', 'pyyaml'])
    added = sorted(closure(lock, ['pydantic-ai-slim']) - base)
    src = root / 'src'
    return {
        'v1.0.2': {'loc_orquestracao': count_lines(src / 'emporio/agent/loop.py'), 'loc_ponte_de_teste': 0, 'pontos_de_cola': 0, 'pacotes_adicionais': 0, 'tamanho_dependencias_adicionais_kb': 0,
                   'tempo_importacao_ms': import_ms('emporio.agent.loop', root),
                   'tokens_esquemas_ferramentas': estimated_tokens([], v102_tools), 'bytes_esquemas_ferramentas': len(json.dumps(v102_tools, ensure_ascii=False))},
        'pydantic-ai': {'loc_orquestracao': count_lines(src / 'emporio_lab/pydanticai_agent.py'),
                        'loc_ponte_de_teste': bridge_lines(src / 'emporio_lab/pydanticai_agent.py'),
                        'pontos_de_cola': (src / 'emporio_lab/pydanticai_agent.py').read_text(encoding='utf-8').count('# COLA:'), 'pacotes_adicionais': len(added),
                        'tamanho_dependencias_adicionais_kb': round(sum(dist_size(n) for n in added) / 1024),
                        'tempo_importacao_ms': import_ms('emporio_lab.pydanticai_agent', root),
                        'tokens_esquemas_ferramentas': estimated_tokens([], pai_tools), 'bytes_esquemas_ferramentas': len(json.dumps(pai_tools, ensure_ascii=False)),
                        'pacotes_adicionais_lista': added},
    }


# --- execução ---------------------------------------------------------------------------------------------------------
def sequential_overhead(architecture, root: Path, turns) -> dict:
    """Um usuário, uma thread, latência artificial ZERO: o custo local puro da orquestração."""
    with cases.isolated_root(root) as sandbox:
        results = architecture().run_user(sandbox, turns, 0)
    done = [r for r in results if r.error is None]
    overhead = [r.total_s * 1000 for r in done]
    return {'seq_primeiro_turno_ms': round(overhead[0], 2) if overhead else 0.0,
            'seq_sobrecarga_p50_ms': round(runner.percentile(overhead[1:], 50), 2), 'seq_sobrecarga_p95_ms': round(runner.percentile(overhead[1:], 95), 2)}


def spread(values: list[float]) -> dict:
    return {'mediana': round(statistics.median(values), 3), 'min': round(min(values), 3), 'max': round(max(values), 3),
            'desvio': round(statistics.pstdev(values), 3) if len(values) > 1 else 0.0, 'valores': [round(v, 3) for v in values]}


def evaluate(s: sc.Scenario, per_arch: dict[str, dict[str, list[float]]], comparative: dict[str, float]) -> list[dict]:
    rows = []
    for m in s.metricas:
        if m.escopo == 'comparativo':
            value = comparative.get(m.id)
            ok = None if m.tipo == 'referencia' else (value is not None and m.criterio.satisfeito(value))
            rows.append({'id': m.id, 'escopo': 'comparativo', 'unidade': m.unidade, 'criterio': m.criterio.texto() if m.criterio else None,
                         'valor': value, 'resultado': 'referência' if ok is None else 'atendido' if ok else 'reprovado'})
            continue
        row = {'id': m.id, 'escopo': 'arquitetura', 'unidade': m.unidade, 'criterio': m.criterio.texto() if m.criterio else None, 'por_arquitetura': {}}
        for arch, metrics in per_arch.items():
            values = metrics.get(m.id)
            entry = {'dispersao': spread(values) if values else None}
            if m.tipo == 'criterio':
                ok = bool(values) and all(m.criterio.satisfeito(v) for v in values)         # vale em TODAS as repetições
                entry['resultado'] = 'atendido' if ok else 'reprovado'
            else:
                entry['resultado'] = 'referência'
            row['por_arquitetura'][arch] = entry
        rows.append(row)
    return rows


def run_comparison(s: sc.Scenario, root: Path, scenarios_root: Path, reports_root: Path | None, allow_dirty: bool, strict: bool, out) -> int:
    p = s.parametros
    started = datetime.now(timezone.utc)
    code = code_state(root)
    prereg_ok, prereg, why = verify_preregistration(s, scenarios_root, reports_root, started)
    if not prereg_ok and not allow_dirty:
        out(f'\nERRO: pré-registro não comprovado ({why}).')
        return runner.EXIT_NOT_PREREGISTERED
    if not code['codigo_sem_alteracoes'] and not allow_dirty:
        out(f"\nERRO: código com alterações não commitadas ({', '.join(code['alteracoes'][:3])}). O commit medido precisa ser reproduzível.")
        return runner.EXIT_NOT_PREREGISTERED
    out(f"\nPré-registro: {'comprovado' if prereg_ok else 'NÃO comprovado (' + why + ')'}; commit dos critérios {prereg.get('commit_dos_criterios', '—')[:12]}.")
    if not (root / 'var/store.db').exists() or not (root / 'data/processed/policies.md').exists():
        runner.ingest_project(root)
    names = runner.product_names(root)
    workload = build_workload(names, p.usuarios_simultaneos, p.turnos_por_usuario, p.seed)
    digest = fingerprint(workload)
    out(f'Dados: carga {SYNTHETIC_MARK} (seed {p.seed}, {digest[:16]}…), {sum(len(u) for u in workload)} turnos {kind_counts(workload)}.')

    out('Casos funcionais offline (modelo roteirizado, mesmo roteiro nas duas arquiteturas)...')
    suite = cases.run_suite({a: ARCHITECTURES[a] for a in s.arquiteturas}, root)
    out('Medições estáticas (complexidade, dependências, esquemas)...')
    static = static_metrics(root)
    search = runner.search_metrics(root)              # leitura da loja somente leitura; não grava nada

    per_arch: dict[str, dict[str, list[float]]] = {a: {} for a in s.arquiteturas}
    repetitions = []
    for rep in range(p.repeticoes):
        order = list(s.arquiteturas) if not p.alternar_ordem or rep % 2 == 0 else list(reversed(s.arquiteturas))
        record = {'repeticao': rep + 1, 'ordem': order, 'carga_da_maquina_antes': [round(x, 2) for x in os.getloadavg()], 'arquiteturas': {}}
        for arch in order:
            out(f'Repetição {rep + 1}/{p.repeticoes}: {arch} ({p.usuarios_simultaneos} usuários simultâneos)...')
            with cases.isolated_root(root) as sandbox:
                metrics = runner.measure(ARCHITECTURES[arch], workload, sandbox, p.latencia_llm_simulada_ms)
            metrics |= sequential_overhead(ARCHITECTURES[arch], root, workload[0])
            record['arquiteturas'][arch] = metrics
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    per_arch[arch].setdefault(key, []).append(float(value))
        record['carga_da_maquina_depois'] = [round(x, 2) for x in os.getloadavg()]
        repetitions.append(record)
    for arch in s.arquiteturas:
        for key, value in search.items():
            per_arch[arch][key] = [value]
        for key, value in suite['resumo'][arch].items():
            per_arch[arch][key] = [float(value)]
        per_arch[arch]['ferramentas_cobertas'] = [float(len(suite['resumo']['ferramentas_cobertas']))]
        for key, value in static[arch].items():
            if isinstance(value, (int, float)):
                per_arch[arch][key] = [float(value)]
    comparative = {'divergencias_em_casos_criticos': float(suite['resumo']['divergencias_em_casos_criticos']),
                   'divergencias_em_casos_com_paridade': float(suite['resumo']['divergencias_em_casos_com_paridade'])}
    a, b = s.arquiteturas[0], s.arquiteturas[1]
    for key in ('sobrecarga_local_p95_ms', 'latencia_turno_p95_ms', 'vazao_turnos_por_s', 'seq_sobrecarga_p50_ms'):
        base, other = statistics.median(per_arch[a][key]), statistics.median(per_arch[b][key])
        comparative[f'razao_{key}'] = round(other / base, 3) if base else 0.0
    evaluation = evaluate(s, per_arch, comparative)
    report = {'cenario': s.nome, 'arquiteturas': s.arquiteturas, 'tipo': 'comparacao',
              'execucao': {'started_at': started.isoformat(), **code, 'scenario_sha256': sc.sha256_of(s.nome, scenarios_root),
                           'pre_registro': {'comprovado': prereg_ok, 'motivo': why, **prereg},
                           'python': sys.version.split()[0], 'plataforma': platform.platform(), 'cpus': os.cpu_count(),
                           'versoes': {n: metadata.version(n) for n in ('pydantic', 'pydantic-ai-slim', 'pydantic-graph')}},
              'dados': {'sinteticos': True, 'seed': p.seed, 'workload_sha256': digest, 'turnos_por_tipo': kind_counts(workload),
                        'catalogo': f'oficial, {len(names)} produtos disponíveis', 'latencia_llm_simulada_ms': p.latencia_llm_simulada_ms},
              'repeticoes': repetitions, 'avaliacao': evaluation, 'comparativo': comparative,
              'casos_funcionais': suite['casos'], 'resumo_funcional': suite['resumo'],
              'detalhe_funcional': {k: {c: v['signature'] for c, v in d.items()} for k, d in suite['detalhe'].items()},
              'estatico': static}
    directory = report_dir(s, scenarios_root, reports_root)
    write_report(directory, report)
    out('\nResultado:')
    failed = False
    for row in evaluation:
        if row['escopo'] == 'comparativo':
            out(f"  {row['resultado']:10} {row['id']} = {row['valor']}" + (f" (critério {row['criterio']})" if row['criterio'] else ''))
            failed |= row['resultado'] == 'reprovado'
        else:
            marks = ' | '.join(f"{arch}: {e['dispersao']['mediana'] if e['dispersao'] else '—'} {e['resultado']}" for arch, e in row['por_arquitetura'].items())
            out(f"  {row['id']}: {marks}")
            failed |= any(e['resultado'] == 'reprovado' for e in row['por_arquitetura'].values())
    out(f'\nRelatório: {directory}/comparison.md')
    return runner.EXIT_CRITERIA_FAILED if failed and strict else runner.EXIT_OK


# --- relatório -------------------------------------------------------------------------------------------------------------
def fmt(entry: dict | None) -> str:
    if not entry or not entry['dispersao']:
        return '—'
    d = entry['dispersao']
    return f"{d['mediana']:g}" + ('' if d['min'] == d['max'] else f" [{d['min']:g}–{d['max']:g}]")


def write_report(directory: Path, report: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    a, b = report['arquiteturas'][:2]
    run, d = report['execucao'], report['dados']
    pre = run['pre_registro']
    lines = [f"# Comparação do cenário {report['cenario']}: {a} × {b}", '',
             f"> **Dados sintéticos ({SYNTHETIC_MARK})**: seed {d['seed']} (`{d['workload_sha256'][:16]}…`), {d['catalogo']}. LLM **simulado** "
             f"({d['latencia_llm_simulada_ms']} ms por chamada); nenhuma API paga ou real foi usada. O relatório original do S0 (`report.md`) segue intacto.", '',
             '## Execução e pré-registro', '',
             f"- Commit medido: `{run['git_head'][:12]}` · árvore `src/emporio_lab`: `{run['arvore_src_lab'][:12]}` · código sem alterações: **{'sim' if run['codigo_sem_alteracoes'] else 'NÃO'}**",
             f"- Critérios: commit `{pre.get('commit_dos_criterios', '—')[:12]}`, SHA-256 do cenário `{run['scenario_sha256'][:16]}…`; pré-registro comprovado: **{'sim' if pre['comprovado'] else 'NÃO (' + pre['motivo'] + ')'}**",
             f"- Início {run['started_at']} · Python {run['python']} · {run['plataforma']} · {run['cpus']} CPUs · " + ', '.join(f'{k} {v}' for k, v in run['versoes'].items()), '',
             '## Repetições (ordem alternada)', '', f'| Repetição | Ordem | Carga da máquina (1 min) antes → depois | sobrecarga local p95 (ms) {a} | {b} |', '| --- | --- | --- | --- | --- |']
    for r in report['repeticoes']:
        lines.append(f"| {r['repeticao']} | {' → '.join(r['ordem'])} | {r['carga_da_maquina_antes'][0]} → {r['carga_da_maquina_depois'][0]} | "
                     f"{r['arquiteturas'][a]['sobrecarga_local_p95_ms']} | {r['arquiteturas'][b]['sobrecarga_local_p95_ms']} |")
    lines += ['', '## Métricas lado a lado', '', 'Valores: mediana das repetições [mínimo–máximo]. Critérios valem em TODAS as repetições.', '',
              f'| Métrica | Unidade | {a} | {b} | Critério | {a} | {b} |', '| --- | --- | --- | --- | --- | --- | --- |']
    for row in report['avaliacao']:
        if row['escopo'] == 'comparativo':
            lines.append(f"| `{row['id']}` (par) | {row['unidade']} | {row['valor']} | | {row['criterio'] or '—'} | {row['resultado']} | |")
        else:
            pa, pb = row['por_arquitetura'][a], row['por_arquitetura'][b]
            lines.append(f"| `{row['id']}` | {row['unidade']} | {fmt(pa)} | {fmt(pb)} | {row['criterio'] or '—'} | {pa['resultado']} | {pb['resultado']} |")
    lines += ['', '## Casos funcionais offline', '', f'| Caso | Crítico | Ferramentas | {a} | {b} | Paridade | Divergências |', '| --- | --- | --- | --- | --- | --- | --- |']
    for c in report['casos_funcionais']:
        ok = lambda arch: 'ok' if not any((c[arch]['violacoes_do_caso'], c[arch]['acesso_indevido'], c[arch]['preco_inventado_aceito'], c[arch]['contato_vazado'])) else 'FALHA'
        lines.append(f"| {c['caso']} | {'sim' if c['critico'] else ''} | {', '.join(c['ferramentas']) or '—'} | {ok(a)} | {ok(b)} | "
                     f"{'exigida' if c['paridade_esperada'] else 'diferença conhecida'} | {', '.join(c['divergencias']) or 'nenhuma'} |")
    lines += ['', '### Diferenças de orquestração observadas (casos sem paridade exigida)', '']
    for c in report['casos_funcionais']:
        if not c['paridade_esperada']:
            lines.append(f"- **{c['caso']}**: " + '; '.join(f"{arch} → chamadas ao domínio: {report['detalhe_funcional'][arch][c['caso']]['dominio'] or 'nenhuma'}, "
                                                          f"chamadas ao LLM: {report['detalhe_funcional'][arch][c['caso']]['chamadas_llm']}" for arch in (a, b)))
    s = report['estatico']
    lines += ['', '## Complexidade e dependências', '', f'| Medida | {a} | {b} |', '| --- | --- | --- |']
    for key in ('loc_orquestracao', 'loc_ponte_de_teste', 'pontos_de_cola', 'pacotes_adicionais', 'tamanho_dependencias_adicionais_kb', 'tempo_importacao_ms', 'bytes_esquemas_ferramentas', 'tokens_esquemas_ferramentas'):
        lines.append(f"| {key} | {s[a][key]} | {s[b][key]} |")
    lines += ['', f"Pacotes adicionais trazidos pelo PydanticAI: {', '.join(s[b].get('pacotes_adicionais_lista', []))}.", '',
              f"Cargas: {d['turnos_por_tipo']}", '', 'A interpretação e a decisão estão em `decision.md` e em `docs/LAB_JOURNAL.md`.', '']
    (directory / 'comparison.md').write_text('\n'.join(lines), encoding='utf-8')
