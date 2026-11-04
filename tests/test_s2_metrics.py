import math

import pytest

from emporio_lab.s2 import metrics as mx


def test_precision_hit_ndcg_on_known_lists():
    s = mx.score_query([2, 0, 2, 0, 0], n2=100, n1=0)
    assert s['precision'] == pytest.approx(2 / 5) and s['hit'] == 1.0
    ideal = 2 + 2 / math.log2(3) + 2 / math.log2(4) + 2 / math.log2(5) + 2 / math.log2(6)
    assert s['ndcg'] == pytest.approx((2 + 2 / math.log2(4)) / ideal)
    assert mx.score_query([0, 0, 0, 0, 0], 100, 0)['ndcg'] == 0 and mx.score_query([0] * 5, 100, 0)['hit'] == 0.0


def test_precision_is_normalised_when_fewer_than_five_relevant_exist():
    assert mx.score_query([2, 0, 0, 0, 0], n2=1, n1=0)['precision'] == 1.0
    assert mx.score_query([2, 2, 0, 0, 0], n2=3, n1=0)['precision'] == pytest.approx(2 / 3)


def test_partial_gain_counts_for_ndcg_but_not_for_precision():
    s = mx.score_query([1, 1, 1, 1, 1], n2=0, n1=50)
    assert s['precision'] is None and s['ndcg'] == pytest.approx(1.0)
    t = mx.score_query([1, 1, 1, 1, 1], n2=10, n1=50)
    assert t['precision'] == 0.0 and 0 < t['ndcg'] < 1


def test_empty_result_scores_zero_and_is_flagged():
    s = mx.score_query([], n2=10, n1=0)
    assert s['ndcg'] == 0 and s['precision'] == 0 and s['returned'] == 0


def test_recall_and_mrr():
    r = mx.recall_mrr({1, 2}, [9, 2, 7, 1, 8])
    assert r['recall'] == 1.0 and r['rr'] == 0.5
    assert mx.recall_mrr({1}, [3, 4, 5, 6, 7, 1])['rr'] == 0.0           # fora do top-5


def test_paired_bootstrap_detects_a_real_difference_and_an_absent_one():
    a = [0.8, 0.7, 0.9, 0.85, 0.75] * 12
    b = [0.5, 0.45, 0.55, 0.5, 0.4] * 12
    d = mx.paired_bootstrap(a, b, seed=1)
    assert d['delta'] > 0.3 and d['ic95_inf'] > 0
    same = mx.paired_bootstrap(a, [x + (0.05 if i % 2 else -0.05) for i, x in enumerate(a)], seed=1)
    assert same['ic95_inf'] < 0 < same['ic95_sup']
    assert mx.paired_bootstrap(a, b, seed=1) == d                       # determinístico
