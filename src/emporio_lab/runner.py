"""Executa um cenário: explica, prepara os dados, roda as arquiteturas nas mesmas condições e grava o relatório."""
import hashlib
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from emporio.cli import ingest_project
from emporio.repository.sqlite import SQLiteRepository
from emporio.search_bench import run_bench
from emporio_lab import scenario as sc
from emporio_lab.architectures import ARCHITECTURES
from emporio_lab.synthetic import SYNTHETIC_MARK, build_workload, fingerprint, kind_counts

REPORTS = Path('reports/scenarios')
EXIT_OK, EXIT_CRITERIA_FAILED, EXIT_INVALID, EXIT_NOT_PREREGISTERED = 0, 1, 2, 4


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(p / 100 * len(ordered) + 0.4999) - 1))] if ordered else 0.0


def explain(s: sc.Scenario) -> str:
    p = s.parametros
    lines = [f'CENÁRIO {s.nome}', '', s.descricao.strip(), '',
             f'O que muda em relação à v1.0.2: {s.mudanca_em_relacao_a_v1_0_2.strip()}',
             f'Hipótese (o gargalo que deve aparecer): {s.hipotese.strip()}',
             f'Arquitetura candidata: {s.arquitetura_candidata or "nenhuma (este cenário só mede a referência)"}']
    if p:
        lines += ['', 'Condições: ' + f'{p.usuarios_simultaneos} usuários simultâneos × {p.turnos_por_usuario} turnos; catálogo de '
                  f'{p.tamanho_do_catalogo} produtos; conhecimento: {p.tamanho_do_conhecimento}; fluxo: {p.requisitos_de_fluxo}; '
                  f'LLM simulado com latência de {p.latencia_llm_simulada_ms} ms por chamada (seed {p.seed}).',
                  'Critérios definidos ANTES da execução:']
        lines += [f'  - {m.id}: {m.criterio.texto()} {m.unidade} ({m.descricao})' for m in s.metricas if m.tipo == 'criterio']
        lines += ['Apenas registrados (referência): ' + ', '.join(m.id for m in s.metricas if m.tipo == 'referencia')]
    return '\n'.join(lines)


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(['git', *args], capture_output=True, text=True, cwd=cwd, timeout=20).stdout.strip()


def preregistered(name: str, scenarios_root: Path) -> bool:
    """O arquivo do cenário está commitado e sem mudanças: os critérios existiam antes desta execução."""
    path = sc.path_of(name, scenarios_root)
    tracked = subprocess.run(['git', 'ls-files', '--error-unmatch', str(path)], capture_output=True, cwd=scenarios_root).returncode == 0
    return tracked and git('status', '--porcelain', '--', str(path), cwd=scenarios_root) == ''


def product_names(root: Path) -> list[str]:
    repo = SQLiteRepository(root / 'var/store.db')
    try:
        rows = repo.connection.execute("SELECT name FROM products WHERE status = 'active' AND stock_quantity > 0 ORDER BY product_id").fetchall()
        return [r['name'] for r in rows]
    finally:
        repo.close()


def measure(architecture, workload, root: Path, latency_ms: int) -> dict:
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(workload)) as pool:
        per_user = list(pool.map(lambda turns: architecture().run_user(root, turns, latency_ms), workload))
    wall = time.perf_counter() - started
    results = [r for user in per_user for r in user]
    done = [r for r in results if r.kind != 'erro']
    overhead = [(r.total_s - r.llm_s) * 1000 for r in done]
    totals = [r.total_s * 1000 for r in done]
    tokens = [r.tokens_estimated for r in done if r.tokens_estimated]
    return {
        'turnos': len(done), 'tempo_total_s': round(wall, 3),
        'erros_de_execucao': sum(1 for r in results if r.error),
        'contingencias_seguras': sum(1 for r in done if r.safe_fallback),
        'sobrecarga_local_p50_ms': round(percentile(overhead, 50), 2), 'sobrecarga_local_p95_ms': round(percentile(overhead, 95), 2),
        'latencia_turno_p50_ms': round(percentile(totals, 50), 2), 'latencia_turno_p95_ms': round(percentile(totals, 95), 2),
        'vazao_turnos_por_s': round(len(done) / wall, 3) if wall else 0.0,
        'tokens_prompt_estimados_p50': percentile(tokens, 50), 'tokens_prompt_estimados_max': max(tokens) if tokens else 0,
        'chamadas_llm_por_turno': round(statistics.mean(r.llm_calls for r in done), 2) if done else 0,
        'erros_detalhe': sorted({r.error for r in results if r.error})[:5],
    }


def search_metrics(root: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        report = run_bench(root / 'var/store.db', root / 'evals/search_queries.yaml', Path(tmp) / 'search.json')
    return {'busca_recall_at_5': round(report['recall_at_5'], 4), 'busca_mrr': round(report['mrr'], 4)}


def evaluate(s: sc.Scenario, metrics: dict) -> list[dict]:
    rows = []
    for m in s.metricas:
        value = metrics.get(m.id)
        if m.tipo == 'criterio':
            ok = value is not None and m.criterio.satisfeito(value)
            rows.append({'id': m.id, 'valor': value, 'unidade': m.unidade, 'criterio': m.criterio.texto(), 'resultado': 'atendido' if ok else 'reprovado'})
        else:
            rows.append({'id': m.id, 'valor': value, 'unidade': m.unidade, 'criterio': None, 'resultado': 'referência'})
    return rows


def conclusion(s: sc.Scenario, architecture: str, metrics: dict, evaluation: list[dict]) -> str:
    p = s.parametros
    failed = [r for r in evaluation if r['resultado'] == 'reprovado']
    llm_per_turn = p.latencia_llm_simulada_ms * metrics['chamadas_llm_por_turno']
    if failed:
        bottleneck = 'critérios reprovados: ' + '; '.join(f"{r['id']} = {r['valor']} (critério {r['criterio']})" for r in failed)
    else:
        bottleneck = (f"o LLM e o tamanho do prompt: a sobrecarga local foi {metrics['sobrecarga_local_p95_ms']} ms no p95 contra "
                      f"{llm_per_turn:.0f} ms de latência simulada do LLM por turno, e o pedido ao LLM tem cerca de "
                      f"{metrics['tokens_prompt_estimados_p50']:.0f} tokens estimados; o código local não é gargalo")
    numbers = (f"erros {metrics['erros_de_execucao']}, contingências {metrics['contingencias_seguras']}, sobrecarga local p95 "
               f"{metrics['sobrecarga_local_p95_ms']} ms, latência do turno p95 {metrics['latencia_turno_p95_ms']} ms, "
               f"{metrics['vazao_turnos_por_s']} turnos/s, tokens estimados p50 {metrics['tokens_prompt_estimados_p50']:.0f}, "
               f"recall@5 {metrics['busca_recall_at_5']}, MRR {metrics['busca_mrr']}")
    return (f"Se o cenário mudar para {p.usuarios_simultaneos} usuários simultâneos, catálogo de {p.tamanho_do_catalogo} produtos e "
            f"{p.tamanho_do_conhecimento}, o gargalo medido foi {bottleneck}, e a arquitetura recomendada é {architecture} "
            f"(cenário de referência, sem alternativa medida), pelos números: {numbers}.")


def write_report(directory: Path, report: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    d, run = report['dados'], report['execucao']
    lines = [f"# Relatório do cenário {report['cenario']}", '',
             f"> **Dados sintéticos ({SYNTHETIC_MARK})**: carga gerada com seed {d['seed']} (impressão digital `{d['workload_sha256'][:16]}…`). "
             f"Catálogo: {d['catalogo']}. LLM: **simulado**, latência artificial de {d['latencia_llm_simulada_ms']} ms por chamada.", '',
             '## Execução', '',
             f"- Commit: `{run['git_head']}` · cenário (SHA-256): `{run['scenario_sha256'][:16]}…` · critérios commitados antes da execução: **{'sim' if run['criterios_pre_registrados'] else 'NÃO'}**",
             f"- Início: {run['started_at']} · Python {run['python']} · {run['plataforma']} · {run['cpus']} CPUs", '',
             '## Métricas e critérios', '', '| Métrica | Medido | Critério | Resultado |', '| --- | --- | --- | --- |']
    for row in report['avaliacao']:
        lines.append(f"| `{row['id']}` | {row['valor']} {row['unidade']} | {row['criterio'] or '—'} | {row['resultado']} |")
    lines += ['', f"Cargas: {d['turnos_por_tipo']}", '', '## Conclusão', '', report['conclusao'], '']
    (directory / 'report.md').write_text('\n'.join(lines), encoding='utf-8')


def run(name: str, root: Path = Path('.'), *, scenarios_root: Path | None = None, reports_root: Path | None = None,
        allow_dirty: bool = False, strict: bool = False, out=print) -> int:
    scenarios_root = scenarios_root or root
    try:
        s = sc.load(name, scenarios_root)
    except sc.ScenarioError as error:
        out(f'ERRO: {error}')
        return EXIT_INVALID
    out(explain(s))
    if s.status != 'mensuravel':
        out(f'\nERRO: o cenário {name} está "planejado": defina as métricas e os critérios antes de executar. Sem medição não há conclusão.')
        return EXIT_INVALID
    if len(s.arquiteturas) != 1:
        out('\nERRO: a comparação entre várias arquiteturas ainda não está implementada; este lab só executa a v1.0.2 (S0).')
        return EXIT_INVALID
    unknown = [a for a in s.arquiteturas if a not in ARCHITECTURES]
    if unknown:
        out(f'\nERRO: arquitetura desconhecida: {unknown}')
        return EXIT_INVALID
    pre = preregistered(name, scenarios_root)
    if not pre and not allow_dirty:
        out(f'\nERRO: scenarios/{name}.yaml não está commitado (ou tem mudanças). Os critérios precisam estar no histórico antes da execução.')
        return EXIT_NOT_PREREGISTERED
    p = s.parametros
    if not (root / 'var/store.db').exists() or not (root / 'data/processed/policies.md').exists():
        ingest_project(root)
    names = product_names(root)
    workload = build_workload(names, p.usuarios_simultaneos, p.turnos_por_usuario, p.seed)
    digest = fingerprint(workload)
    out(f'\nDados: carga {SYNTHETIC_MARK} (seed {p.seed}, {digest[:16]}…), {sum(len(u) for u in workload)} turnos {kind_counts(workload)}; '
        f'catálogo oficial de {len(names)} produtos disponíveis.')
    started = datetime.now(timezone.utc)
    arch_name = s.arquiteturas[0]
    out(f'Rodando {arch_name} com {p.usuarios_simultaneos} usuários simultâneos...')
    metrics = measure(ARCHITECTURES[arch_name], workload, root, p.latencia_llm_simulada_ms) | search_metrics(root)
    evaluation = evaluate(s, metrics)
    report = {'cenario': s.nome, 'arquitetura': arch_name,
              'execucao': {'started_at': started.isoformat(), 'git_head': git('rev-parse', '--short', 'HEAD', cwd=root),
                           'scenario_sha256': sc.sha256_of(name, scenarios_root), 'criterios_pre_registrados': pre,
                           'python': sys.version.split()[0], 'plataforma': platform.platform(), 'cpus': __import__('os').cpu_count()},
              'dados': {'sinteticos': True, 'seed': p.seed, 'workload_sha256': digest, 'turnos_por_tipo': kind_counts(workload),
                        'catalogo': f'oficial, {len(names)} produtos disponíveis', 'latencia_llm_simulada_ms': p.latencia_llm_simulada_ms},
              'metricas': metrics, 'avaliacao': evaluation, 'conclusao': conclusion(s, arch_name, metrics, evaluation)}
    directory = (reports_root or root / REPORTS) / name
    write_report(directory, report)
    out('\nResultado:')
    for row in evaluation:
        out(f"  {row['resultado']:10} {row['id']} = {row['valor']} {row['unidade']}" + (f" (critério {row['criterio']})" if row['criterio'] else ''))
    out(f'\nConclusão: {report["conclusao"]}\nRelatório: {directory}/report.md')
    failed = any(r['resultado'] == 'reprovado' for r in evaluation)
    if failed and strict:
        return EXIT_CRITERIA_FAILED
    return EXIT_OK
