"""Consultas rotuladas do S2: relevância por atributos, grupos, divisão desenvolvimento/validação e hashes estáveis."""
import random
from pathlib import Path

import numpy as np
import pytest

from emporio_lab.s2 import catalog as cat
from emporio_lab.s2 import lexicon as lx
from emporio_lab.s2 import queries as qs
from emporio_lab.s2 import vocab

SEED = 20261103


@pytest.fixture(scope='module')
def world():
    products = cat.generate(5000, SEED)
    return products, qs.build_queries(cat.generate(50000, SEED), SEED)


def test_group_counts_and_split(world):
    _, queries = world
    assert len(queries) == sum(qs.COUNTS.values()) == 450
    for group, n in qs.COUNTS.items():
        members = [q for q in queries if q.group == group]
        assert len(members) == n and abs(sum(q.split == 'dev' for q in members) - n / 2) <= 1
    assert {q.split for q in queries} == {'dev', 'val'}


def test_queries_are_deterministic_and_the_hash_changes_with_the_seed(world):
    _, queries = world
    again = qs.build_queries(cat.generate(50000, SEED), SEED)
    assert qs.queries_hash(queries) == qs.queries_hash(again)
    assert qs.queries_hash(queries) != qs.queries_hash(qs.build_queries(cat.generate(50000, SEED + 1), SEED + 1))


def test_every_answerable_query_has_enough_relevant_products_at_5k(world):
    products, queries = world
    arr = cat.attribute_arrays(products)
    dyn = qs.dynamic_from_products(products)
    for q in queries:
        if q.group == 'sem_correspondencia':
            assert not q.full
            continue
        cats = None
        if q.filters.get('category'):
            cats = [c for c, n in lx.CATEGORIES.items() if n == q.filters['category']]
        assert (qs.gains_for(q, arr, dyn, cats) == 2).sum() >= (1 if q.group in ('nome_codigo', 'digitacao') else qs.MIN_RELEVANT_AT_5K), q.id


def test_relevance_depends_on_attributes_not_on_description_text(world):
    products, queries = world
    arr = cat.attribute_arrays(products)
    dyn = qs.dynamic_from_products(products)
    q = next(q for q in queries if q.group == 'intencao' and q.subgroup == 'cat_nivel')
    before = qs.gains_for(q, arr, dyn)
    for p in products:
        p.description = 'texto totalmente diferente'
    assert (qs.gains_for(q, cat.attribute_arrays(products), qs.dynamic_from_products(products)) == before).all()
    expected = np.isin(arr['category'], q.full['category']) & np.isin(arr['level'], q.full['level']) & dyn['available']
    assert ((before == 2) == expected).all()


def test_filters_are_part_of_the_relevance_and_use_the_current_state(world):
    products, queries = world
    arr = cat.attribute_arrays(products)
    dyn = qs.dynamic_from_products(products)
    q = next(q for q in queries if q.subgroup == 'preco')
    gains = qs.gains_for(q, arr, dyn)
    assert (dyn['price'][gains > 0] <= q.filters['max_price']).all() and dyn['available'][gains > 0].all()
    dyn2 = {'price': dyn['price'] * 10, 'available': dyn['available']}               # o mundo mudou: tudo ficou 10x mais caro
    assert (qs.gains_for(q, arr, dyn2) > 0).sum() < (gains > 0).sum()


def test_typos_are_never_valid_catalog_words(world):
    products, queries = world
    vocabulary = {t for p in products for t in vocab.tokens(p.name + ' ' + p.description)}
    for q in [q for q in queries if q.group == 'digitacao']:
        assert any(t not in vocabulary for t in vocab.tokens(q.text)), q.text


def test_intent_queries_do_not_reuse_description_vocabulary(world):
    products, queries = world
    realized = vocab.catalog_stems(products) | vocab.description_stems()
    nouns = set().union(*[vocab.content_stems(w) for w in lx.CATEGORY_NOUN.values()]) | vocab.ALLOWED_STEMS
    type_stems = set().union(*[vocab.content_stems(t[2]) for t in lx.TYPES])
    for q in [q for q in queries if q.group in ('intencao', 'filtros')]:
        text = q.text
        words = vocab.content_stems(text) - nouns
        if q.subgroup == 'tipo_nivel':
            words -= type_stems
        # só as palavras do instrumento podem coincidir com o catálogo; as de nível e uso não
        assert not (words & realized & vocab.stems_of(p for t in (lx.LEVEL_QUERY, lx.USE_QUERY) for ph in t.values() for p in ph)), q.id


def test_name_queries_exist_in_both_scales(world):
    products, queries = world
    names = {p.name for p in products[:qs.NAME_POOL]}
    full_name = [q for q in queries if q.subgroup == 'nome_completo' and q.group == 'nome_codigo']
    assert full_name and all(any(p.name.casefold() == q.text.casefold() or vocab.fold(p.name) == q.text for p in products[:qs.NAME_POOL]) for q in full_name)
    assert len(names) == qs.NAME_POOL


def test_versioned_labeled_queries_are_exactly_what_the_generator_produces(world):
    import json
    stored = json.loads((Path(__file__).resolve().parents[1] / 'evals/s2_consultas.json').read_text(encoding='utf-8'))
    _, queries = world
    assert stored['seed'] == SEED and stored['sha256'] == qs.queries_hash(queries)
    from dataclasses import asdict
    assert stored['consultas'] == [asdict(q) for q in queries]
