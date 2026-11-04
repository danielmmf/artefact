"""Pontua as saídas dos workers contra os rótulos por atributo, agrega por grupo e calcula os deltas da decisão."""
import json
import sqlite3
from pathlib import Path

import numpy as np

from emporio.repository.sqlite import SQLiteRepository
from emporio_lab.s2 import catalog as cat
from emporio_lab.s2 import metrics as mx
from emporio_lab.s2 import queries as qs


class Labels:
    """Rótulos de uma escala: atributos do gerador + estado ATUAL (preço, estoque, promoção) lido da base."""
    def __init__(self, products: list[cat.Product], db: Path, query_list: list[qs.Query]):
        self.arr = cat.attribute_arrays(products)
        con = sqlite3.connect(f'{db.resolve().as_uri()}?mode=ro', uri=True)
        self.dyn = qs.dynamic_from_sqlite(con)
        con.close()
        repo = SQLiteRepository(db)
        self.queries = {q.id: q for q in query_list}
        self.gains: dict[str, np.ndarray] = {}
        for q in query_list:
            cats = repo._match_categories(q.filters['category']) if q.filters.get('category') else None
            self.gains[q.id] = qs.gains_for(q, self.arr, self.dyn, cats)
        repo.close()
        self.n2 = {i: int((g == 2).sum()) for i, g in self.gains.items()}
        self.n1 = {i: int((g == 1).sum()) for i, g in self.gains.items()}

    def score(self, query_id: str, ids: list[int]) -> dict:
        g = self.gains[query_id]
        top = [int(g[i - cat.FIRST_ID]) for i in ids[:mx.K]]
        out = mx.score_query(top, self.n2[query_id], self.n1[query_id])
        out['n_relevantes'] = self.n2[query_id]
        return out


def group_scores(rows: list[dict], labels: Labels, split: str | None) -> dict:
    """Médias por grupo (e geral por grupo de consulta). `rows` = linhas do worker; `split` = 'val'/'dev'/None."""
    out: dict = {}
    for row in rows:
        q = labels.queries[row['id']]
        if split and q.split != split:
            continue
        out.setdefault(q.group, []).append((q, row, labels.score(q.id, row['ids'])))
    summary = {}
    for group, items in out.items():
        if group == 'sem_correspondencia':
            summary[group] = {'n': len(items), 'falso_positivo': mx.mean([1.0 if row['ids'] else 0.0 for _, row, _ in items])}
            continue
        summary[group] = {'n': len(items), 'precisao_at_5': mx.mean([s['precision'] for _, _, s in items]), 'ndcg_at_5': mx.mean([s['ndcg'] for _, _, s in items]),
                          'hit_at_5': mx.mean([s['hit'] for _, _, s in items]), 'sem_resposta': mx.mean([1.0 if not row['ids'] else 0.0 for _, row, _ in items])}
        if group == 'filtros':
            subs = {}
            for q, row, s in items:
                subs.setdefault(q.subgroup, []).append(s)
            summary[group]['por_subgrupo'] = {k: {'n': len(v), 'precisao_at_5': mx.mean([x['precision'] for x in v]), 'ndcg_at_5': mx.mean([x['ndcg'] for x in v])} for k, v in subs.items()}
    return summary


def per_query(rows: list[dict], labels: Labels, group: str, metric: str, split: str = 'val') -> dict[str, float]:
    return {r['id']: labels.score(r['id'], r['ids'])[metric] for r in rows if labels.queries[r['id']].group == group and labels.queries[r['id']].split == split}


def filter_violations(rows: list[dict], labels: Labels) -> int:
    """Resultados devolvidos que violam o filtro no estado atual da base (ganho 0 por filtro): deve ser 0."""
    bad = 0
    for row in rows:
        q = labels.queries[row['id']]
        if not q.filters:
            continue
        f = q.filters
        for i in row['ids'][:mx.K]:
            r = i - cat.FIRST_ID
            if f.get('only_available', True) and not labels.dyn['available'][r]:
                bad += 1
            elif f.get('max_price') is not None and labels.dyn['price'][r] > f['max_price']:
                bad += 1
            elif f.get('min_price') is not None and labels.dyn['price'][r] < f['min_price']:
                bad += 1
            elif f.get('category') and lx_category(labels.arr['category'][r]) != f['category']:
                bad += 1
    return bad


def lx_category(code: int) -> str:
    from emporio_lab.s2 import lexicon as lx
    return lx.CATEGORIES[int(code)]


def latency_summary(runs: list[dict], by: str = 'e2e_ms', group_of=None) -> dict:
    """p50/p95 de cada componente, juntando as repetições (cada uma com índice pronto e cache aquecido)."""
    out = {}
    for field in ('embed_ms', 'index_ms', 'hydrate_ms', 'e2e_ms'):
        values = [q[field] for r in runs for q in r['queries']]
        out[field] = {'p50': round(mx.percentile(values, 50), 2), 'p95': round(mx.percentile(values, 95), 2), 'media': round(float(np.mean(values)), 2)}
    return out


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))
