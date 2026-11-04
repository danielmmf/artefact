"""Métricas de busca do S2: precisão@5, nDCG@5, hit@5 (catálogo grande); recall@5 e MRR (só no smoke de 65 produtos)."""
import math
import random

import numpy as np

K = 5


def dcg(gains) -> float:
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def score_query(top_gains: list[int], n2: int, n1: int) -> dict:
    """top_gains: ganhos (0/1/2) dos resultados devolvidos, em ordem. n2/n1: quantos produtos de ganho 2/1 existem no catálogo."""
    top = top_gains[:K]
    ideal = [2] * min(K, n2) + [1] * min(K - min(K, n2), n1)
    hits = sum(1 for g in top if g == 2)
    return {'precision': hits / min(K, n2) if n2 else None, 'hit': 1.0 if hits else 0.0 if n2 else None,
            'ndcg': dcg(top) / dcg(ideal) if ideal else None, 'returned': len(top_gains)}


def recall_mrr(relevant: set[int], ids: list[int]) -> dict:
    top = ids[:K]
    rank = next((i for i, x in enumerate(top, 1) if x in relevant), None)
    return {'recall': len(relevant.intersection(top)) / len(relevant), 'rr': 1 / rank if rank else 0.0}


def mean(values) -> float | None:
    values = [v for v in values if v is not None]
    return float(np.mean(values)) if values else None


def percentile(values: list[float], p: float) -> float:
    return float(np.percentile(values, p)) if len(values) else 0.0


def paired_bootstrap(a: list[float], b: list[float], seed: int, resamples: int = 2000) -> dict:
    """Diferença média (a - b) por consulta, com IC95% por bootstrap pareado sobre as consultas."""
    assert len(a) == len(b) and a
    diff = np.array(a) - np.array(b)
    rng = np.random.default_rng(seed)
    means = np.array([diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(resamples)])
    return {'delta': float(diff.mean()), 'ic95_inf': float(np.percentile(means, 2.5)), 'ic95_sup': float(np.percentile(means, 97.5)), 'n': len(diff)}
