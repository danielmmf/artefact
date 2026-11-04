"""Orquestra o S2: pré-registro verificável, indexação por escala, seleção de configuração no desenvolvimento, medição em processos
isolados (ordem alternada), avaliação, decisão pelos critérios do YAML e relatórios."""
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

from emporio_lab import compare, runner
from emporio_lab import scenario as sc
from emporio_lab.s2 import build as bd
from emporio_lab.s2 import catalog as cat
from emporio_lab.s2 import evaluate as ev
from emporio_lab.s2 import metrics as mx
from emporio_lab.s2 import queries as qs
from emporio_lab.s2 import strategies as st
from emporio_lab.s2 import vocab

NAMES = {'A': 'A · SQLite FTS5 + RapidFuzz (original)', 'B': 'B · Qdrant denso', 'C': 'C · Qdrant híbrido (BM25 + denso, RRF)', 'D': 'D · FTS5 + numpy exato + RRF'}
GROUPS_FOR_TUNING = ('intencao', 'sinonimos', 'nome_codigo', 'digitacao')
CONTAINERS = {'B': 'emporio-s2-qdrant-dense', 'C': 'emporio-s2-qdrant-hybrid'}


# --- dados: gerados do zero a cada execução e comparados com o pré-registro ----------------------------------------------------------
def data_fingerprint(seed: int, sizes=(5000, 50000)) -> dict:
    full = cat.generate(max(sizes), seed)
    queries = qs.build_queries(full, seed)
    return {'catalogo_sha256': {str(n): cat.catalog_hash(full[:n]) for n in sizes}, 'consultas_sha256': qs.queries_hash(queries),
            'consultas_por_grupo_e_divisao': {f'{g}/{sp}': sum(1 for q in queries if q.group == g and q.split == sp) for g in qs.GROUPS for sp in ('dev', 'val')},
            'sobreposicao_de_vocabulario': {'nivel_uso_fonte': vocab.overlap_report(), 'nivel_uso_no_catalogo_50k': vocab.realized_overlap(full)}}


def export_queries(path: Path, seed: int) -> None:
    """Consultas rotuladas versionadas (evals/s2_consultas.json): o arquivo é regenerável e o teste exige que seja idêntico ao gerador."""
    queries = qs.build_queries(cat.generate(50000, seed), seed)
    path.write_text(json.dumps({'seed': seed, 'sha256': qs.queries_hash(queries), 'consultas': [asdict(q) for q in queries]}, ensure_ascii=False, indent=0) + '\n', encoding='utf-8')


def load_smoke_queries(root: Path) -> list[dict]:
    cases = json.loads((root / 'evals/search_queries.yaml').read_text(encoding='utf-8'))
    return [{'id': f'smoke-{i:02d}', 'group': c['group'], 'text': c['query'], 'filters': {'only_available': True}, 'relevant': c['relevant']} for i, c in enumerate(cases, 1)]


def preregister(name: str, root: Path) -> Path:
    s = sc.load(name, root)
    target = compare.preregister(name, root)
    record = json.loads(target.read_text(encoding='utf-8'))
    seed = s.experimento['seed']
    meta_model = bd.model_files(st.MODEL)
    record['dados'] = data_fingerprint(seed) | {'seed': seed, 'gerador': 'src/emporio_lab/s2/catalog.py', 'consultas_smoke_sha256': compare.sha256_file(root / 'evals/search_queries.yaml')}
    record['versoes'] = bd.versions() | {'qdrant_servidor_imagem': s.experimento['qdrant']['servidor'], 'qdrant_digest': s.experimento['qdrant']['digest']}
    record['modelos'] = {'denso': meta_model, 'esparso': {'modelo': st.BM25_MODEL, 'idioma': st.BM25_LANGUAGE}}
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return target


def verify(s: sc.Scenario, root: Path, reports_root, started: datetime) -> tuple[bool, dict, str]:
    ok, record, why = compare.verify_preregistration(s, root, reports_root, started)
    if not ok:
        return ok, record, why
    if 'dados' not in record:
        return False, record, 'o pré-registro não traz os hashes dos dados'
    now = data_fingerprint(s.experimento['seed'])
    if now['catalogo_sha256'] != record['dados']['catalogo_sha256'] or now['consultas_sha256'] != record['dados']['consultas_sha256']:
        return False, record, 'o catálogo ou as consultas gerados hoje diferem dos hashes pré-registrados'
    return True, record, 'ok'


# --- servidores -------------------------------------------------------------------------------------------------------------------
def restart_servers(root: Path) -> None:
    subprocess.run(['docker', 'restart', *CONTAINERS.values()], check=True, capture_output=True)
    import urllib.request
    for url in (bd.DENSE_URL, bd.HYBRID_URL):
        for _ in range(120):
            try:
                urllib.request.urlopen(url + '/readyz', timeout=2)
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError(f'Qdrant {url} não ficou pronto')
    time.sleep(2)


def drop_other_collections(keep: str) -> None:
    from qdrant_client import QdrantClient
    for url in (bd.DENSE_URL, bd.HYBRID_URL):
        client = QdrantClient(url=url, check_compatibility=False)
        for c in client.get_collections().collections:
            if not c.name.startswith(keep + '_'):
                client.delete_collection(c.name)
        client.close()


def container_mb(name: str) -> float:
    out = subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{.MemUsage}}', name], capture_output=True, text=True).stdout.split('/')[0].strip()
    value = float(''.join(c for c in out if c.isdigit() or c == '.'))
    return round(value * (1024 if 'GiB' in out else 1 if 'MiB' in out else 1 / 1024), 1)


# --- configuração (desenvolvimento) -------------------------------------------------------------------------------------------------
def tune(s: sc.Scenario, index_dir: Path, query_list: list[qs.Query], products, out) -> dict:
    grid = s.experimento['grade_de_configuracao']
    labels = ev.Labels(products[:5000], Path(json.loads((index_dir / 'meta.json').read_text())['db']), query_list)
    index = st.load_index(index_dir)
    dev = [q for q in query_list if q.split == 'dev' and q.group in GROUPS_FOR_TUNING]
    results = []
    for k in grid['rrf_k']:
        for depth in grid['profundidade_por_ramo']:
            strategy = st.D(index, st.Config(rrf_k=k, depth=depth, candidates=grid['candidatos_para_o_sqlite']))
            rows = [{'id': q.id, **strategy.search(q.text, q.filters)} for q in dev]
            strategy.close()
            groups = ev.group_scores(rows, labels, 'dev')
            score = float(np.mean([groups[g]['ndcg_at_5'] for g in GROUPS_FOR_TUNING]))
            results.append({'rrf_k': k, 'profundidade': depth, 'media_ndcg_dev': round(score, 4), 'ndcg_por_grupo': {g: round(groups[g]['ndcg_at_5'], 4) for g in GROUPS_FOR_TUNING}})
            out(f'  configuração rrf_k={k} profundidade={depth}: média de nDCG@5 no desenvolvimento = {score:.4f}')
    best = sorted(results, key=lambda r: (-r['media_ndcg_dev'], r['profundidade'], -r['rrf_k']))[0]
    return {'candidatas': results, 'escolhida': {'rrf_k': best['rrf_k'], 'profundidade': best['profundidade']}, 'subconjunto': 'desenvolvimento', 'escala': 'catalogo5k', 'estrategia': 'D'}


# --- execução de uma escala ------------------------------------------------------------------------------------------------------------
def run_workers(s: sc.Scenario, scale: str, directory: Path, config: st.Config, queries_file: Path, raw: Path, out) -> dict[str, list[dict]]:
    env = os.environ | {'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'TOKENIZERS_PARALLELISM': 'false'}
    runs: dict[str, list[dict]] = {k: [] for k in st.STRATEGIES}
    raw.mkdir(parents=True, exist_ok=True)
    for rep in range(s.experimento['repeticoes']):
        order = s.experimento['ordens'][rep % len(s.experimento['ordens'])]
        for name in order:
            target = raw / f'rep{rep}_{name}.json'
            t = time.perf_counter()
            subprocess.run([sys.executable, '-m', 'emporio_lab.s2.worker', '--strategy', name, '--index', str(directory), '--queries', str(queries_file),
                            '--config', json.dumps(asdict(config)), '--out', str(target)], check=True, env=env,
                           capture_output=True, text=True)
            result = ev.read_json(target)
            result['rep'] = rep
            if name in CONTAINERS:
                result['qdrant_rss_mb'] = container_mb(CONTAINERS[name])
            runs[name].append(result)
            out(f'  [{scale}] repetição {rep + 1}/{s.experimento["repeticoes"]} · {name}: {result["qps"]} consultas/s, p50 {np.median([q["e2e_ms"] for q in result["queries"]]):.1f} ms ({time.perf_counter() - t:.0f} s)')
    return runs


def summarize_scale(scale: str, runs: dict, labels: ev.Labels | None, meta: dict, smoke_cases: list[dict] | None) -> dict:
    out: dict = {'meta': meta, 'estrategias': {}}
    ref = runs['D'][0]['queries'] if runs.get('D') else []
    d_dense = {q['id']: q.get('dense_only', []) for q in ref}
    for name, reps in runs.items():
        first = reps[0]['queries']
        entry = {'latencia': ev.latency_summary(reps), 'primeira_consulta_fria_ms': [r['cold']['e2e_ms'] for r in reps], 'init_ms': [r['init_ms'] for r in reps],
                 'vazao_consultas_por_s': [r['qps'] for r in reps], 'rss_pico_mb': max(r['rss_peak_mb'] for r in reps), 'rss_apos_init_mb': max(r['rss_after_init_mb'] for r in reps),
                 'instabilidade_top5': float(np.mean([np.mean([a['ids'] != b['ids'] for a, b in zip(first, r['queries'])]) for r in reps[1:]])) if len(reps) > 1 else 0.0,
                 'candidatos_descartados_pela_fonte_de_verdade': float(np.mean([q['dropped'] > 0 for q in first]))}
        if any('qdrant_rss_mb' in r for r in reps):
            entry['qdrant_rss_mb'] = round(float(np.mean([r['qdrant_rss_mb'] for r in reps])), 1)
        if name == 'B':
            entry['concordancia_com_busca_exata_top5'] = round(float(np.mean([len(set(q['ids'][:5]) & set(d_dense[q['id']])) / 5 for q in first if d_dense.get(q['id']) and q['ids']])), 4)
        if labels is not None:
            entry['qualidade_validacao'] = ev.group_scores(first, labels, 'val')
            entry['qualidade_desenvolvimento'] = ev.group_scores(first, labels, 'dev')
            entry['violacoes_de_filtro'] = ev.filter_violations(first, labels)
            entry['por_consulta'] = {q['id']: {'ids': q['ids'], 'e2e_ms_mediana': round(float(np.median([r['queries'][i]['e2e_ms'] for r in reps])), 2)} for i, q in enumerate(first)}
        if smoke_cases is not None:
            relevant = {c['id']: set(c['relevant']) for c in smoke_cases}
            scores = [mx.recall_mrr(relevant[q['id']], q['ids']) for q in first]
            entry['smoke'] = {'recall_at_5': round(float(np.mean([x['recall'] for x in scores])), 4), 'mrr': round(float(np.mean([x['rr'] for x in scores])), 4),
                              'por_consulta': {q['id']: {'texto': c['text'], 'grupo': c['group'], 'ids': q['ids'], 'relevantes': c['relevant']} for q, c in zip(first, smoke_cases)}}
        out['estrategias'][name] = entry
    return out


# --- integração: o resultado do Qdrant é confirmado na camada original --------------------------------------------------------------------
def integration_check(directory: Path, root: Path) -> dict:
    """Muda preço, estoque e promoção numa CÓPIA do SQLite depois da indexação e mostra que as respostas de B, C e D refletem o SQLite."""
    import shutil
    import sqlite3
    import tempfile
    meta = json.loads((directory / 'meta.json').read_text())
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / 'store.db'
        shutil.copy(meta['db'], copy)
        index = st.load_index(directory)
        index.db = copy
        probe = 'violão para quem nunca tocou'
        evidence: dict = {'consulta': probe, 'estrategias': {}}
        baseline = {}
        for name in ('B', 'C', 'D'):
            strategy = st.REGISTRY[name](index, st.Config())
            baseline[name] = strategy.search(probe, {'only_available': True})['ids']
            strategy.close()
        victim, repriced = baseline['C'][0], baseline['C'][1]
        con = sqlite3.connect(copy)
        con.execute('UPDATE products SET stock_quantity = 0 WHERE product_id = ?', (victim,))              # esgotou depois da indexação
        con.execute('UPDATE products SET price_cents = 123400 WHERE product_id = ?', (repriced,))          # preço mudou depois da indexação
        con.execute('DELETE FROM promotions WHERE product_id = ? AND is_active = 1', (repriced,))
        con.execute("INSERT INTO promotions(product_id, discount_percent, description, is_active) VALUES (?, '50', 'Promoção nova', 1)", (repriced,))
        con.commit()
        con.close()
        from emporio.repository.sqlite import SQLiteRepository
        from emporio.rules.pricing import discounted_cents
        from decimal import Decimal
        repo = SQLiteRepository(copy)
        current = repo.get_product_pricing(repriced)
        repo.close()
        for name in ('B', 'C', 'D'):
            strategy = st.REGISTRY[name](index, st.Config())
            r = strategy.search(probe, {'only_available': True})
            strategy.close()
            evidence['estrategias'][name] = {'produto_esgotado_saiu_do_resultado': victim not in r['ids'], 'candidatos_descartados': r['dropped'],
                                             'produto_reprecificado_continua_no_resultado': repriced in r['ids']}
        evidence['produto_esgotado'] = victim
        evidence['produto_reprecificado'] = {'id': repriced, 'preco_atual_no_sqlite_centavos': discounted_cents(current.price_cents, current.active_promotion.discount_percent), 'preco_no_payload_do_qdrant_centavos': int(np.load(directory / 'snap_price.npy')[repriced - cat.FIRST_ID])}
        evidence['conclusao'] = 'o Qdrant só propôs IDs; estoque e preço vieram de get_product_pricing (SQLite) na hora da resposta'
        return evidence


# --- decisão ---------------------------------------------------------------------------------------------------------------------------------
def decide(s: sc.Scenario, big: dict) -> dict:
    limit = {m.id: m for m in s.metricas}
    e = big['estrategias']
    val = {n: {q: v for q, v in e[n]['por_consulta'].items()} for n in e}
    labels = big['_labels']
    queries = labels.queries
    def vec(n, group, metric):
        rows = [{'id': q, 'ids': v['ids']} for q, v in val[n].items()]
        return ev.per_query(rows, labels, group, metric)
    def delta(x, y, group, metric, seed):
        a, b = vec(x, group, metric), vec(y, group, metric)
        keys = sorted(a)
        return mx.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys], seed)
    seed = s.experimento['seed']
    di = delta('D', 'A', 'intencao', 'ndcg', seed)
    dn = delta('D', 'A', 'nome_codigo', 'precision', seed)
    ci = delta('C', 'D', 'intencao', 'ndcg', seed)
    cn = delta('C', 'D', 'nome_codigo', 'precision', seed)
    comparativos = {'d_vs_a_delta_ndcg_intencao': di['delta'], 'd_vs_a_ic95_inferior_ndcg_intencao': di['ic95_inf'], 'd_vs_a_delta_precisao_nome': dn['delta'],
                    'c_vs_d_delta_ndcg_intencao': ci['delta'], 'c_vs_d_ic95_inferior_ndcg_intencao': ci['ic95_inf'], 'c_vs_d_delta_precisao_nome': cn['delta']}
    por_estrategia = {n: {'p95_e2e_ms': e[n]['latencia']['e2e_ms']['p95'], 'violacoes_de_filtro': e[n]['violacoes_de_filtro'], 'instabilidade_top5': e[n]['instabilidade_top5']} for n in e}
    def ok(metric_id, value):
        return limit[metric_id].criterio.satisfeito(value)
    crit = {k: ok(k, v) for k, v in comparativos.items()}
    ok_lat = {n: ok('p95_e2e_ms', v['p95_e2e_ms']) and ok('violacoes_de_filtro', v['violacoes_de_filtro']) and ok('instabilidade_top5', v['instabilidade_top5']) for n, v in por_estrategia.items()}
    embeddings_ajudam = all(crit[k] for k in ('d_vs_a_delta_ndcg_intencao', 'd_vs_a_ic95_inferior_ndcg_intencao', 'd_vs_a_delta_precisao_nome')) and ok_lat['D']
    ponto_sem_ic = crit['d_vs_a_delta_ndcg_intencao'] and not crit['d_vs_a_ic95_inferior_ndcg_intencao']
    qualidade_c = all(crit[k] for k in ('c_vs_d_delta_ndcg_intencao', 'c_vs_d_ic95_inferior_ndcg_intencao', 'c_vs_d_delta_precisao_nome')) and ok_lat['C']
    limite = limit['p95_e2e_ms'].criterio.valor
    latencia_c = (not ok('p95_e2e_ms', por_estrategia['D']['p95_e2e_ms'])) and ok_lat['C'] and crit['c_vs_d_delta_precisao_nome']
    qdrant_justifica = embeddings_ajudam and (qualidade_c or latencia_c)
    if embeddings_ajudam and qdrant_justifica:
        veredito = 'Os embeddings ajudam e o Qdrant se justifica nas condições medidas.'
    elif embeddings_ajudam:
        veredito = 'Os embeddings ajudam; o Qdrant ainda não se justifica: C não superou D pelos critérios pré-registrados.'
    elif ponto_sem_ic:
        veredito = 'Inconclusivo: o ganho de D sobre A atinge o mínimo no ponto, mas o intervalo de confiança inclui zero.'
    else:
        veredito = 'Os embeddings não demonstraram o ganho mínimo pré-registrado sobre a busca original; nenhuma alternativa é recomendada por esta medição.'
    return {'comparativos': {k: round(v, 4) for k, v in comparativos.items()}, 'criterios_comparativos': crit, 'bootstrap': {'D_menos_A_intencao': di, 'D_menos_A_nome': dn, 'C_menos_D_intencao': ci, 'C_menos_D_nome': cn},
            'por_estrategia': por_estrategia, 'estrategia_dentro_dos_limites': ok_lat, 'embeddings_ajudam': embeddings_ajudam, 'qdrant_se_justifica': qdrant_justifica,
            'via_qualidade': qualidade_c, 'via_latencia': latencia_c, 'limite_p95_ms': limite, 'veredito': veredito}


# --- execução oficial -------------------------------------------------------------------------------------------------------------------------
def explain(s: sc.Scenario) -> str:
    x = s.experimento
    lines = [f'CENÁRIO {s.nome}', '', s.descricao.strip(), '', f'Hipótese: {s.hipotese.strip()}',
             'Estratégias: ' + '; '.join(NAMES[a] for a in s.arquiteturas),
             'Escalas: ' + ', '.join(f"{e['nome']} ({e['produtos']})" for e in x['escalas']) + f"; {x['repeticoes']} repetições com ordem alternada; seed {x['seed']}.",
             'Critérios definidos ANTES da execução (decisão na escala ' + x['decisao_na_escala'] + ', validação):']
    lines += [f'  - {m.id}: {m.criterio.texto()} {m.unidade} ({m.descricao})' for m in s.metricas if m.tipo == 'criterio']
    return '\n'.join(lines)


def run(name: str, root: Path, *, scenarios_root: Path | None = None, reports_root: Path | None = None, allow_dirty: bool = False, strict: bool = False,
        only_scales: list[str] | None = None, out=print) -> int:
    scenarios_root = scenarios_root or root
    s = sc.load(name, scenarios_root)
    out(explain(s))
    started = datetime.now(timezone.utc)
    ok, record, why = verify(s, scenarios_root, reports_root, started)
    if not ok and not allow_dirty:
        out(f'\nERRO: pré-registro não verificado: {why}.')
        return runner.EXIT_NOT_PREREGISTERED
    if not ok:
        out(f'\nAVISO: sem pré-registro ({why}); o relatório marcará a execução como NÃO pré-registrada.')
    state = compare.code_state(root)
    if not state['codigo_sem_alteracoes'] and not allow_dirty:
        out(f'\nERRO: código com alterações não commitadas: {state["alteracoes"]}')
        return runner.EXIT_NOT_PREREGISTERED
    x = s.experimento
    seed = x['seed']
    bd.servers_up(root)
    full = cat.generate(50000, seed)
    query_list = qs.build_queries(full, seed)
    smoke_cases = load_smoke_queries(root)
    scales = [e for e in x['escalas'] if not only_scales or e['nome'] in only_scales]
    out('\nConfiguração (desenvolvimento, escala de 5.000, estratégia D):')
    bd.build_scale('catalogo5k', root, seed, out, rebuild=True)
    tuning = tune(s, root / bd.S2_DIR / 'catalogo5k', query_list, full, out)
    config = st.Config(rrf_k=tuning['escolhida']['rrf_k'], depth=tuning['escolhida']['profundidade'], candidates=x['grade_de_configuracao']['candidatos_para_o_sqlite'])
    out(f'Escolhida: {tuning["escolhida"]}')
    results: dict = {}
    for scale_entry in scales:
        scale = scale_entry['nome']
        out(f'\n=== Escala {scale} ({scale_entry["produtos"]} produtos) ===')
        directory = bd.build_scale(scale, root, seed, out, rebuild=True)
        drop_other_collections(scale)
        restart_servers(root)
        meta = json.loads((directory / 'meta.json').read_text())
        meta['qdrant_rss_ocioso_mb'] = {'B': container_mb(CONTAINERS['B']), 'C': container_mb(CONTAINERS['C'])}
        raw = root / bd.S2_DIR / 'raw' / scale
        if scale == 'smoke65':
            queries_file = raw / 'queries.json'
            raw.mkdir(parents=True, exist_ok=True)
            queries_file.write_text(json.dumps(smoke_cases, ensure_ascii=False), encoding='utf-8')
            runs = run_workers(s, scale, directory, config, queries_file, raw, out)
            results[scale] = summarize_scale(scale, runs, None, meta, smoke_cases)
        else:
            queries_file = raw / 'queries.json'
            raw.mkdir(parents=True, exist_ok=True)
            queries_file.write_text(json.dumps([asdict(q) for q in query_list], ensure_ascii=False), encoding='utf-8')
            runs = run_workers(s, scale, directory, config, queries_file, raw, out)
            labels = ev.Labels(full[:scale_entry['produtos']], Path(meta['db']), query_list)
            results[scale] = summarize_scale(scale, runs, labels, meta, None)
            results[scale]['_labels'] = labels
            if scale == 'catalogo5k':
                results[scale]['integracao'] = integration_check(directory, root)
    finished = datetime.now(timezone.utc)
    report = assemble(s, record, state, tuning, config, results, started, finished, bool(ok))
    directory = compare.report_dir(s, scenarios_root, reports_root)
    write_reports(directory, s, report)
    write_decision(directory, s, report)
    out(f'\nVeredito: {report["decisao"]["veredito"]}\nRelatórios: {directory}')
    failed = any(r['resultado'] == 'reprovado' for r in report['avaliacao'])
    return runner.EXIT_CRITERIA_FAILED if failed and strict else runner.EXIT_OK


def assemble(s, record, state, tuning, config, results, started, finished, preregistered: bool) -> dict:
    big_name = s.experimento['decisao_na_escala']
    decision = None
    evaluation = []
    if big_name in results:
        decision = decide(s, results[big_name])
        values = decision['comparativos']
        for m in s.metricas:
            if m.tipo == 'criterio' and m.id in values:
                evaluation.append({'id': m.id, 'valor': round(values[m.id], 4), 'unidade': m.unidade, 'criterio': m.criterio.texto(), 'resultado': 'atendido' if m.criterio.satisfeito(values[m.id]) else 'reprovado'})
        for strat, vals in decision['por_estrategia'].items():
            for m in s.metricas:
                if m.tipo == 'criterio' and m.id in vals:
                    evaluation.append({'id': f'{m.id}[{strat}]', 'valor': vals[m.id], 'unidade': m.unidade, 'criterio': m.criterio.texto(), 'resultado': 'atendido' if m.criterio.satisfeito(vals[m.id]) else 'reprovado'})
    else:
        decision = {'veredito': f'Não decidido: a escala de decisão ({big_name}) não foi executada.'}
    if 'smoke65' in results:
        smoke = results['smoke65']['estrategias']['A']['smoke']
        for key, mid in (('recall_at_5', 'smoke_a_recall_at_5'), ('mrr', 'smoke_a_mrr')):
            m = next(m for m in s.metricas if m.id == mid)
            evaluation.append({'id': mid, 'valor': smoke[key], 'unidade': m.unidade, 'criterio': m.criterio.texto(), 'resultado': 'atendido' if m.criterio.satisfeito(smoke[key]) else 'reprovado'})
    clean = {scale: {k: v for k, v in r.items() if k != '_labels'} for scale, r in results.items()}
    return {'cenario': s.nome, 'sinteticos': True,
            'execucao': {'inicio': started.isoformat(), 'fim': finished.isoformat(), 'duracao_s': round((finished - started).total_seconds()), 'git_head': state['git_head'],
                         'codigo_sem_alteracoes': state['codigo_sem_alteracoes'], 'criterios_pre_registrados': preregistered,
                         'commit_dos_criterios': record.get('commit_dos_criterios'), 'python': sys.version.split()[0], 'plataforma': platform.platform(), 'cpus': os.cpu_count(),
                         'memoria_total_mb': int(open('/proc/meminfo').readline().split()[1]) // 1024},
            'pre_registro': {k: record.get(k) for k in ('commit_dos_criterios', 'arquivos_sha256', 'dados', 'versoes', 'modelos')},
            'configuracao_escolhida': tuning, 'config_usada': asdict(config), 'escalas': clean, 'avaliacao': evaluation, 'decisao': {k: v for k, v in decision.items()}}


def pct(x) -> str:
    return '—' if x is None else f'{x:.3f}'


def write_reports(directory: Path, s: sc.Scenario, report: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=float) + '\n', encoding='utf-8')
    run_info = report['execucao']
    L = [f'# Relatório do cenário {s.nome}', '',
         f'> **Dados sintéticos (SINTÉTICO)**, gerados por atributos com seed {s.experimento["seed"]}. Nenhum LLM, nenhuma API externa de embeddings: modelos baixados uma vez e inferência local.', '',
         '## Execução', '',
         f'- Commit: `{run_info["git_head"][:12]}` · código sem alterações: **{"sim" if run_info["codigo_sem_alteracoes"] else "NÃO"}** · critérios pré-registrados antes da execução: **{"sim" if run_info["criterios_pre_registrados"] else "NÃO"}** (commit dos critérios `{(run_info["commit_dos_criterios"] or "—")[:12]}`)',
         f'- Início {run_info["inicio"]} · duração {run_info["duracao_s"]} s · Python {run_info["python"]} · {run_info["plataforma"]} · {run_info["cpus"]} CPUs · {run_info["memoria_total_mb"]} MB de RAM',
         f'- Configuração escolhida no desenvolvimento (5.000, D): `{report["configuracao_escolhida"]["escolhida"]}`; usada em C e D.', '']
    for scale, r in report['escalas'].items():
        meta = r['meta']
        L += [f'## Escala {scale} ({meta["n"]} produtos)', '',
              f'Qdrant Server {meta["qdrant_server"]} · FastEmbed {meta["versoes"]["fastembed"]} · modelo {meta["modelo"]["modelo"]} ({meta["modelo"]["dim"]} dim, {meta["modelo"]["licenca"]}).', '']
        t = meta['tempos']
        L += ['### Indexação e armazenamento', '', '| Item | Valor |', '| --- | --- |',
              f'| Embeddings densos | {t["embeddings_densos_s"]} s (carregar o modelo: {t["carregar_modelo_denso_s"]} s) |', f'| Embeddings esparsos (BM25) | {t["embeddings_esparsos_bm25_s"]} s |',
              f'| SQLite + FTS5 (A e D) | {t["sqlite"].get("inserir_linhas_s", "—")} s linhas + {t["sqlite"].get("indice_fts5_s", "—")} s índice FTS5 |',
              f'| Qdrant denso (B), índice pronto | {t["qdrant_denso"]["indice_pronto_s"]} s · vetores indexados (contagem do Qdrant): {t["qdrant_denso"]["vetores_indexados_hnsw"]} |',
              f'| Qdrant híbrido (C), índice pronto | {t["qdrant_hibrido"]["indice_pronto_s"]} s · vetores indexados (contagem do Qdrant; inclui o esparso): {t["qdrant_hibrido"]["vetores_indexados_hnsw"]} |',
              f'| Disco: SQLite (com FTS5) | {meta["tamanhos"]["sqlite_total_bytes"] / 1e6:.1f} MB |', f'| Disco: embeddings numpy (D) | {meta["tamanhos"]["embeddings_npy_bytes"] / 1e6:.1f} MB |',
              f'| Disco: Qdrant denso / híbrido | {meta["tamanhos"]["qdrant_denso_bytes"] / 1e6:.1f} MB / {meta["tamanhos"]["qdrant_hibrido_bytes"] / 1e6:.1f} MB |',
              f'| RAM do servidor Qdrant ocioso (denso / híbrido) | {meta["qdrant_rss_ocioso_mb"]["B"]} MB / {meta["qdrant_rss_ocioso_mb"]["C"]} MB |', '']
        est = r['estrategias']
        if 'smoke' in est['A']:
            L += ['### Qualidade (smoke de 10 consultas rotuladas da v1.0.2)', '', '| Estratégia | recall@5 | MRR |', '| --- | --- | --- |']
            for n in 'ABCD':
                L.append(f'| {NAMES[n]} | {est[n]["smoke"]["recall_at_5"]} | {est[n]["smoke"]["mrr"]} |')
            L.append('')
        else:
            L += ['### Qualidade por grupo (subconjunto de validação)', '', '| Grupo | n | Métrica | A | B | C | D |', '| --- | --- | --- | --- | --- | --- | --- |']
            for g in qs.GROUPS:
                v = est['A']['qualidade_validacao'].get(g)
                if v is None:
                    continue
                if g == 'sem_correspondencia':
                    L.append(f'| {g} | {v["n"]} | falso positivo | ' + ' | '.join(pct(est[n]['qualidade_validacao'][g]['falso_positivo']) for n in 'ABCD') + ' |')
                    continue
                for metric, label in (('precisao_at_5', 'precisão@5'), ('ndcg_at_5', 'nDCG@5'), ('hit_at_5', 'hit@5')):
                    L.append(f'| {g if metric == "precisao_at_5" else ""} | {v["n"] if metric == "precisao_at_5" else ""} | {label} | ' + ' | '.join(pct(est[n]['qualidade_validacao'][g][metric]) for n in 'ABCD') + ' |')
            L += ['', '**Consultas com resposta possível que devolveram lista vazia (validação):** ' + ', '.join(f'{n} = {np.mean([est[n]["qualidade_validacao"][g]["sem_resposta"] for g in qs.GROUPS if g != "sem_correspondencia"]):.3f}' for n in 'ABCD'), '']
            fl = [(n, est[n]['qualidade_validacao']['filtros']['por_subgrupo']) for n in 'ABCD']
            L += ['**Qualidade com filtros (precisão@5 / nDCG@5, validação):**', '', '| Subgrupo | A | B | C | D |', '| --- | --- | --- | --- | --- |']
            for sub in fl[0][1]:
                L.append(f'| {sub} | ' + ' | '.join(f'{d[sub]["precisao_at_5"]:.3f} / {d[sub]["ndcg_at_5"]:.3f}' for _, d in fl) + ' |')
            L += ['', f'Violações de filtro no estado atual da base: ' + ', '.join(f'{n} = {est[n]["violacoes_de_filtro"]}' for n in 'ABCD') + '.', '']
        L += ['### Latência (ms, índice pronto e cache aquecido, todas as repetições)', '', '| Estratégia | embedding p50 / p95 | índice p50 / p95 | SQLite p50 / p95 | ponta a ponta p50 / p95 | 1ª consulta fria | consultas/s | RSS pico do processo | RSS Qdrant |', '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
        for n in 'ABCD':
            e = est[n]; lat = e['latencia']
            L.append(f'| {NAMES[n]} | {lat["embed_ms"]["p50"]} / {lat["embed_ms"]["p95"]} | {lat["index_ms"]["p50"]} / {lat["index_ms"]["p95"]} | {lat["hydrate_ms"]["p50"]} / {lat["hydrate_ms"]["p95"]} | **{lat["e2e_ms"]["p50"]} / {lat["e2e_ms"]["p95"]}** | '
                     f'{np.median(e["primeira_consulta_fria_ms"]):.0f} ms | {np.mean(e["vazao_consultas_por_s"]):.1f} | {e["rss_pico_mb"]:.0f} MB | {e.get("qdrant_rss_mb", "—")} |')
        L += ['', f'Instabilidade do top-5 entre repetições: ' + ', '.join(f'{n} = {est[n]["instabilidade_top5"]:.4f}' for n in 'ABCD') + f'. Concordância de B com a busca densa exata (top-5): {est["B"].get("concordancia_com_busca_exata_top5", "—")}.',
              f'Candidatos descartados na confirmação do SQLite (fração das consultas): ' + ', '.join(f'{n} = {est[n]["candidatos_descartados_pela_fonte_de_verdade"]:.3f}' for n in 'ABCD') + '.', '']
        if 'integracao' in r:
            i = r['integracao']
            L += ['### Integração: o SQLite continua sendo a fonte de verdade', '', f'Consulta "{i["consulta"]}"; depois da indexação, um produto foi esgotado e outro teve o preço alterado numa cópia do SQLite.',
                  '', '| Estratégia | produto esgotado saiu | candidatos descartados | produto reprecificado segue no resultado |', '| --- | --- | --- | --- |']
            for n, v in i['estrategias'].items():
                L.append(f'| {n} | {v["produto_esgotado_saiu_do_resultado"]} | {v["candidatos_descartados"]} | {v["produto_reprecificado_continua_no_resultado"]} |')
            L += ['', f'Preço no SQLite agora: {i["produto_reprecificado"]["preco_atual_no_sqlite_centavos"]} centavos; no payload do Qdrant (do momento da indexação): {i["produto_reprecificado"]["preco_no_payload_do_qdrant_centavos"]} centavos. {i["conclusao"]}.', '']
    L += ['## Critérios pré-registrados', '', '| Métrica | Medido | Critério | Resultado |', '| --- | --- | --- | --- |']
    for row in report['avaliacao']:
        L.append(f'| `{row["id"]}` | {row["valor"]} {row["unidade"]} | {row["criterio"]} | {row["resultado"]} |')
    d = report['decisao']
    L += ['', '## Resultado', '', d['veredito'], '']
    (directory / 'report.md').write_text('\n'.join(L), encoding='utf-8')


def write_decision(directory: Path, s: sc.Scenario, report: dict) -> None:
    d = report['decisao']
    L = [f'# Decisão do cenário {s.nome}', '', f'> Dados sintéticos. Critérios pré-registrados em `{(report["execucao"]["commit_dos_criterios"] or "—")[:12]}` (pré-registro: **{"sim" if report["execucao"]["criterios_pre_registrados"] else "NÃO"}**). Sem recalibração depois da medição.', '',
         '## Veredito', '', d['veredito'], '']
    if 'comparativos' in d:
        b = d['bootstrap']
        def line(label, x):
            return f'- {label}: {x["delta"]:+.4f} (IC95% {x["ic95_inf"]:+.4f} a {x["ic95_sup"]:+.4f}, {x["n"]} consultas de validação)'
        L += ['## As duas perguntas (escala principal, validação)', '',
              '**1. Os embeddings ajudam? (D contra A)** ' + ('Sim, pelos critérios.' if d['embeddings_ajudam'] else 'Não demonstrado pelos critérios.'),
              line('nDCG@5, consultas de intenção', b['D_menos_A_intencao']), line('precisão@5, consultas por nome e código', b['D_menos_A_nome']), '',
              '**2. O Qdrant se justifica? (C contra D)** ' + ('Sim.' if d['qdrant_se_justifica'] else 'Não nas condições medidas.'),
              line('nDCG@5, consultas de intenção', b['C_menos_D_intencao']), line('precisão@5, consultas por nome e código', b['C_menos_D_nome']),
              f'- Via qualidade: {"atendida" if d["via_qualidade"] else "não atendida"} · via latência (D acima de {d["limite_p95_ms"]:g} ms de p95 e C dentro): {"atendida" if d["via_latencia"] else "não atendida"}', '',
              '## Limites operacionais (p95 ponta a ponta, violações de filtro, instabilidade)', '', '| Estratégia | p95 ms | violações | instabilidade | dentro dos limites |', '| --- | --- | --- | --- | --- |']
        for n, v in d['por_estrategia'].items():
            L.append(f'| {NAMES[n]} | {v["p95_e2e_ms"]} | {v["violacoes_de_filtro"]} | {v["instabilidade_top5"]:.4f} | {d["estrategia_dentro_dos_limites"][n]} |')
    L += ['', '## O que esta medição não conclui', '']
    L += [s.experimento['limitacoes_declaradas_antes'].strip(), '',
          '- Rótulos e catálogo sintéticos: o resultado vale para este gerador e este modelo de embeddings; outro domínio, outro idioma de consulta ou outro modelo podem mudar a conclusão.',
          '- Nenhum vencedor global é declarado: a decisão é só sobre as duas perguntas acima, na escala de 50.000 produtos, com uma máquina.', '']
    (directory / 'decision.md').write_text('\n'.join(L), encoding='utf-8')
