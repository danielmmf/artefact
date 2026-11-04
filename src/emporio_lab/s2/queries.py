"""Consultas rotuladas do S2. A relevância é um predicado sobre ATRIBUTOS (nunca sobre o texto da descrição).

Ganho de cada produto para uma consulta: 2 se satisfaz `full` (e os filtros), 1 se satisfaz algum predicado de `partial` (e os filtros), 0 senão.
`full`/`partial` mapeiam atributo -> lista de códigos aceitos; `partial` é uma lista de predicados (OU). Predicado vazio {} = qualquer produto.
"""
import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from decimal import Decimal

import numpy as np

from emporio.rules.pricing import discounted_cents
from emporio_lab.s2 import lexicon as lx
from emporio_lab.s2 import vocab
from emporio_lab.s2.catalog import FIRST_ID, TYPE_INDEX, Product, attribute_arrays

GROUPS = ('nome_codigo', 'digitacao', 'intencao', 'sinonimos', 'ambiguas', 'filtros', 'sem_correspondencia')
COUNTS = {'nome_codigo': 80, 'digitacao': 60, 'intencao': 120, 'sinonimos': 60, 'ambiguas': 40, 'filtros': 60, 'sem_correspondencia': 30}
MIN_RELEVANT_AT_5K = 8          # toda consulta tem ao menos 8 produtos de ganho 2 já no catálogo de 5.000
NAME_POOL = 4000                # consultas por nome usam só os 4.000 primeiros produtos (séries completas nos dois tamanhos)


@dataclass
class Query:
    id: str
    group: str
    subgroup: str
    split: str
    text: str
    full: dict = field(default_factory=dict)
    partial: list = field(default_factory=list)
    filters: dict = field(default_factory=dict)       # category (nome), min_price/max_price (centavos, preço final), only_available


def queries_hash(queries: list[Query]) -> str:
    return hashlib.sha256(json.dumps([asdict(q) for q in queries], ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def mutate(text: str, rng: random.Random, vocabulary: set[str]) -> str:
    """Erro de digitação determinístico em uma palavra de 5+ letras; a palavra resultante não pode ser uma palavra válida do catálogo."""
    words = text.split()
    candidates = [i for i, w in enumerate(words) if len(w) >= 5 and w.isalpha()]
    for _ in range(30):
        i = rng.choice(candidates)
        w = words[i]
        k = rng.randrange(1, len(w) - 1)
        op = rng.choice(('swap', 'drop', 'dup', 'sub'))
        if op == 'swap':
            new = w[:k] + w[k + 1] + w[k] + w[k + 2:]
        elif op == 'drop':
            new = w[:k] + w[k + 1:]
        elif op == 'dup':
            new = w[:k] + w[k] + w[k:]
        else:
            new = w[:k] + rng.choice('aeiourstnl') + w[k + 1:]
        if new != w and vocab.fold(new) not in vocabulary:
            words[i] = new
            return ' '.join(words)
    raise ValueError(f'sem mutação válida para {text!r}')


def build_queries(products: list[Product], seed: int) -> list[Query]:
    """Gera as consultas a partir do catálogo de 5.000 (prefixo do de 50.000). Determinístico."""
    rng = random.Random(seed + 7)
    pool = products[:NAME_POOL]
    arr = attribute_arrays(products[:5000])
    catalog_tokens = {t for p in products[:5000] for t in vocab.tokens(p.name + ' ' + p.description)}
    queries: list[Query] = []
    seq = {g: 0 for g in GROUPS}

    def add(group, subgroup, text, full, partial=(), filters=None):
        seq[group] += 1
        queries.append(Query(f'{group}-{seq[group]:03d}', group, subgroup, '', text, full, list(partial), filters or {}))

    def relevant_ok(full, filters) -> bool:
        return int(gains_for(Query('', '', '', '', '', full, [], filters), arr, dynamic_from_products(products[:5000])).__ge__(2).sum()) >= MIN_RELEVANT_AT_5K

    cat_of_noun = {'violão': (5,), 'guitarra': (1,), 'baixo': (2,), 'bateria': (3,), 'teclado': (4,), 'ukulele': (9,)}

    # --- nome e código de modelo -----------------------------------------------------------------------------------------
    chosen = rng.sample(range(len(pool)), 80)
    series_names = list(arr['series_names'])
    for n, i in enumerate(chosen):
        p = pool[i]
        series = p.attrs['series']
        code = series.split()[-1]
        if n < 30:                                  # nome completo (um produto exato; variantes da série valem ganho 1)
            text = p.name if n % 2 == 0 else vocab.fold(p.name)
            add('nome_codigo', 'nome_completo', text, {'product_id': [p.product_id]}, [{'series_name': [series]}], {'only_available': False})
        elif n < 55:                                # marca + código da série
            add('nome_codigo', 'serie', f'{series}' if n % 2 else f'{code} {series.split()[0]}', {'series_name': [series]}, [], {'only_available': False})
        else:                                       # só o código do modelo (pode existir em outras marcas)
            add('nome_codigo', 'codigo', code, {'code': [code]}, [], {'only_available': False})

    # --- erros de digitação (de nomes completos, séries e tipo+marca) ------------------------------------------------------
    bases = rng.sample(range(len(pool)), 60)
    for n, i in enumerate(bases):
        p = pool[i]
        series = p.attrs['series']
        if n < 25:
            text, full, partial, sub = p.name, {'product_id': [p.product_id]}, [{'series_name': [series]}], 'nome_completo'
        elif n < 45:
            text, full, partial, sub = series, {'series_name': [series]}, [], 'serie'
        else:
            term = lx.TYPES[p.attrs['type']][2]
            text, full, partial, sub = f'{term} {lx.BRANDS[p.attrs["brand"]]}', {'type': [p.attrs['type']], 'brand': [p.attrs['brand']]}, [{'type': [p.attrs['type']]}], 'tipo_marca'
        add('digitacao', sub, mutate(text, rng, catalog_tokens), full, partial, {'only_available': False} if sub != 'tipo_marca' else {})

    # --- intenção (vocabulário próprio das consultas; ver vocab.py) -----------------------------------------------------------
    nouns = list(cat_of_noun)
    kinds = ['cat_nivel'] * 30 + ['cat_uso'] * 30 + ['inst_nivel'] * 10 + ['inst_uso'] * 15 + ['cat_nivel_uso'] * 20 + ['tipo_nivel'] * 15
    rng.shuffle(kinds)
    for kind in kinds:
        for _ in range(200):
            level = rng.randrange(4)
            use = rng.randrange(len(lx.USES))
            lq = rng.choice(lx.LEVEL_QUERY[lx.LEVELS[level]])
            uq = rng.choice(lx.USE_QUERY[lx.USES[use]])
            noun = rng.choice(nouns)
            cats = list(cat_of_noun[noun])
            if kind == 'cat_nivel':
                text, full, partial = f'{noun} {lq}', {'category': cats, 'level': [level]}, [{'category': cats}]
            elif kind == 'cat_uso':
                text, full, partial = f'{noun} {uq}', {'category': cats, 'use': [use]}, [{'category': cats}]
            elif kind == 'inst_nivel':
                text, full, partial = f'instrumento {lq}', {'level': [level]}, []
            elif kind == 'inst_uso':
                text, full, partial = f'instrumento {uq}', {'use': [use]}, []
            elif kind == 'cat_nivel_uso':
                text, full, partial = f'{noun} {lq}, {uq}', {'category': cats, 'level': [level], 'use': [use]}, [{'category': cats, 'level': [level]}, {'category': cats, 'use': [use]}]
            else:
                t = rng.choice(lx.TYPES)
                text, full, partial = f'{t[2]} {lq}', {'type': [TYPE_INDEX[t[0]]], 'level': [level]}, [{'type': [TYPE_INDEX[t[0]]]}]
            if relevant_ok(full, {}) and text not in {q.text for q in queries}:
                add('intencao', kind, text, full, partial)
                break
        else:
            raise RuntimeError(f'sem consulta de intenção viável para {kind}')

    # --- sinônimos: o tipo é pedido por um termo que o catálogo não usa --------------------------------------------------------
    types = list(lx.TYPES)
    for n in range(60):
        t = types[n % len(types)] if n < len(types) else rng.choice(types)
        ti = TYPE_INDEX[t[0]]
        if n < 36 or n % 2:
            add('sinonimos', 'tipo', t[3], {'type': [ti]}, [{'category': [t[1]]}])
        else:
            for _ in range(50):
                level = rng.randrange(4)
                if relevant_ok({'type': [ti], 'level': [level]}, {}):
                    add('sinonimos', 'tipo_nivel', f'{t[3]} {rng.choice(lx.LEVEL_QUERY[lx.LEVELS[level]])}', {'type': [ti], 'level': [level]}, [{'type': [ti]}])
                    break
            else:
                add('sinonimos', 'tipo', t[3], {'type': [ti]}, [{'category': [t[1]]}])

    # --- ambíguas: uma marca, um acabamento ou só o nome do instrumento --------------------------------------------------------
    for b in rng.sample(range(len(lx.BRANDS)), 12):
        add('ambiguas', 'marca', lx.BRANDS[b], {'brand': [b]}, [])
    for f in range(len(lx.FINISHES)):
        add('ambiguas', 'acabamento', lx.FINISHES[f].lower(), {'finish': [f]}, [])
    generic = [('violão', {'category': [5]}), ('guitarra', {'category': [1]}), ('baixo', {'category': [2]}), ('bateria', {'category': [3]}),
               ('teclado', {'type': [TYPE_INDEX['teclado_arranjador']]}), ('ukulele', {'category': [9]}), ('flauta', {'type': [TYPE_INDEX['flauta_transversal'], TYPE_INDEX['flauta_doce']]}),
               ('saxofone', {'type': [TYPE_INDEX['sax_alto']]}), ('trompete', {'type': [TYPE_INDEX['trompete']]}), ('violino', {'type': [TYPE_INDEX['violino']]}),
               ('piano', {'type': [TYPE_INDEX['piano_digital']]}), ('sintetizador', {'type': [TYPE_INDEX['sintetizador']]}), ('cajón', {'type': [TYPE_INDEX['cajon']]}),
               ('violoncelo', {'type': [TYPE_INDEX['violoncelo']]}), ('clarinete', {'type': [TYPE_INDEX['clarinete']]}), ('trombone', {'type': [TYPE_INDEX['trombone']]})]
    for text, full in generic:
        add('ambiguas', 'instrumento', text, full, [])

    # --- filtros (categoria, preço, disponibilidade) ---------------------------------------------------------------------------
    for n in range(60):
        for _ in range(200):
            level = rng.randrange(4)
            use = rng.randrange(len(lx.USES))
            noun = rng.choice(nouns)
            cats = list(cat_of_noun[noun])
            cat_name = lx.CATEGORIES[cats[0]]
            lq = rng.choice(lx.LEVEL_QUERY[lx.LEVELS[level]])
            uq = rng.choice(lx.USE_QUERY[lx.USES[use]])
            if n < 20:                                  # categoria: o texto não cita o instrumento; o filtro sim
                sub, text, full, partial, filters = 'categoria', f'instrumento {lq}', {'category': cats, 'level': [level]}, [{'category': cats}], {'category': cat_name, 'only_available': True}
            elif n < 40:                                # preço final máximo
                limit = int(lx.BASE_PRICE[cats[0]] * rng.choice((0.7, 1.0, 1.5, 2.5))) // 1000 * 1000
                sub, text, full, partial, filters = 'preco', f'{noun} {uq}', {'category': cats, 'use': [use]}, [{'category': cats}], {'max_price': limit, 'only_available': True}
            else:                                       # disponibilidade: metade exige estoque, metade aceita esgotado
                avail = n % 2 == 0
                sub, text, full, partial, filters = ('disponibilidade_sim' if avail else 'disponibilidade_nao'), f'{noun} {lq}', {'category': cats, 'level': [level]}, [{'category': cats}], {'only_available': avail}
            if relevant_ok(full, filters):
                add('filtros', sub, text, full, partial, filters)
                break
        else:
            raise RuntimeError('sem consulta com filtro viável')

    # --- sem correspondência -----------------------------------------------------------------------------------------------------
    for text in lx.NO_MATCH:
        add('sem_correspondencia', 'ausente', text, {}, [])

    # --- subconjuntos: desenvolvimento (escolher configurações) e validação (medir de verdade), 50/50 por grupo -----------------------
    for g in GROUPS:
        members = [q for q in queries if q.group == g]
        assert len(members) == COUNTS[g], (g, len(members))
        order = list(range(len(members)))
        rng.shuffle(order)
        for rank, idx in enumerate(order):
            members[idx].split = 'dev' if rank % 2 == 0 else 'val'
    return queries


# --- relevância -------------------------------------------------------------------------------------------------------------------
def dynamic_from_products(products: list[Product]) -> dict:
    eff = np.array([discounted_cents(p.price_cents, Decimal(p.promo_percent)) if p.promo_percent else p.price_cents for p in products])
    avail = np.array([p.status == 'active' and p.stock > 0 for p in products])
    return {'price': eff, 'available': avail}


def dynamic_from_sqlite(con) -> dict:
    """Estado ATUAL da fonte de verdade (preço final promocional e disponibilidade), na ordem de product_id."""
    rows = con.execute('''SELECT p.product_id, p.price_cents, p.status, p.stock_quantity, pr.discount_percent FROM products p
                          LEFT JOIN promotions pr ON pr.product_id = p.product_id AND pr.is_active = 1 ORDER BY p.product_id''').fetchall()
    eff = np.array([discounted_cents(r[1], Decimal(r[4])) if r[4] is not None else r[1] for r in rows])
    avail = np.array([r[2] == 'active' and r[3] > 0 for r in rows])
    return {'price': eff, 'available': avail, 'ids': np.array([r[0] for r in rows])}


def _mask(spec: dict, arr: dict) -> np.ndarray:
    n = len(arr['product_id'])
    mask = np.ones(n, dtype=bool)
    for key, allowed in spec.items():
        if key == 'series_name':
            allowed = [i for i, s in enumerate(arr['series_names']) if s in set(allowed)]
            column = arr['series']
        elif key == 'code':
            allowed_codes = set(allowed)
            mask &= np.array([s.split()[-1] in allowed_codes for s in arr['series_names']])[arr['series']]
            continue
        else:
            column = arr[key]
        mask &= np.isin(column, allowed)
    return mask


def gains_for(q: Query, arr: dict, dyn: dict, category_ids: list[int] | None = None) -> np.ndarray:
    """Vetor de ganhos (0/1/2) por produto, já aplicando os filtros da consulta ao estado atual da fonte de verdade."""
    valid = np.ones(len(arr['product_id']), dtype=bool)
    f = q.filters
    if f.get('category') is not None:
        valid &= np.isin(arr['category'], category_ids if category_ids is not None else [c for c, n in lx.CATEGORIES.items() if n == f['category']])
    if f.get('only_available', True):
        valid &= dyn['available']
    if f.get('min_price') is not None:
        valid &= dyn['price'] >= f['min_price']
    if f.get('max_price') is not None:
        valid &= dyn['price'] <= f['max_price']
    full = _mask(q.full, arr) & valid if q.full else np.zeros_like(valid)
    partial = np.zeros_like(valid)
    for spec in q.partial:
        partial |= _mask(spec, arr) & valid
    return np.where(full, 2, np.where(partial, 1, 0)).astype(np.int8)
