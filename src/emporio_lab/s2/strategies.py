"""As quatro estratégias de recuperação do S2 e a camada que confirma os candidatos na fonte de verdade (SQLite).

Contrato: toda estratégia devolve IDs candidatos (os product_id estáveis do SQLite); `hydrate` consulta a camada original
(`SQLiteRepository.get_product` / `get_product_pricing`) para preço, estoque e promoção ATUAIS e reaplica os filtros. Nenhum dado
comercial vem do índice vetorial. A: baseline original. B: Qdrant denso. C: Qdrant BM25 + denso com RRF. D: FTS5 + numpy exato + RRF.
"""
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from emporio.repository.sqlite import SQLiteRepository
from emporio.rules.pricing import discounted_cents
from emporio.money import to_cents

MODEL = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
DENSE_DIM = 384
BM25_MODEL = 'Qdrant/bm25'
BM25_LANGUAGE = 'portuguese'
STRATEGIES = ('A', 'B', 'C', 'D')


@dataclass
class Config:
    rrf_k: int = 60                  # constante do RRF (a mesma em C e D)
    depth: int = 100                 # candidatos por ramo antes da fusão (o mesmo em C e D)
    candidates: int = 30             # candidatos devolvidos à camada SQLite (sobra para descartes)
    hnsw_ef: int | None = None       # None = padrão do servidor


@dataclass
class Index:
    scale: str
    directory: Path                  # var/s2/<scale>/
    db: Path
    dense_collection: str
    hybrid_collection: str
    dense_url: str
    hybrid_url: str


def load_index(directory: Path) -> Index:
    meta = json.loads((directory / 'meta.json').read_text(encoding='utf-8'))
    return Index(meta['scale'], directory, Path(meta['db']), meta['dense_collection'], meta['hybrid_collection'], meta['dense_url'], meta['hybrid_url'])


def fts_query(query: str) -> str | None:
    tokens = re.findall(r'[^\W_]+', query, flags=re.UNICODE)
    return ' OR '.join('"' + t + '"' for t in tokens) if tokens else None


class Filters:
    """Filtros de uma consulta, resolvidos uma vez (a categoria usa o casamento da v1: `_match_categories`)."""
    def __init__(self, repo: SQLiteRepository, raw: dict):
        self.category = raw.get('category')
        self.category_ids = repo._match_categories(self.category) if self.category is not None else None
        self.min_cents = raw.get('min_price')
        self.max_cents = raw.get('max_price')
        self.only_available = raw.get('only_available', True)


def hydrate(repo: SQLiteRepository, ids: list[int], f: Filters, limit: int) -> tuple[list[int], int]:
    """Confirma candidatos na fonte de verdade. Devolve (ids válidos até `limit`, descartados). Estado atual manda, não o do índice."""
    kept, dropped = [], 0
    for product_id in ids:
        product = repo.get_product(product_id)
        pricing = repo.get_product_pricing(product_id)
        if product is None or pricing is None:
            dropped += 1
            continue
        promo = pricing.active_promotion
        final = discounted_cents(pricing.price_cents, promo.discount_percent) if promo else pricing.price_cents
        ok = ((f.category_ids is None or product.category_id in f.category_ids)
              and (not f.only_available or (pricing.status == 'active' and pricing.stock_quantity > 0))
              and (f.min_cents is None or final >= f.min_cents) and (f.max_cents is None or final <= f.max_cents))
        if ok:
            kept.append(product_id)
            if len(kept) == limit:
                break
        else:
            dropped += 1
    return kept, dropped


class Embedders:
    """Modelos locais (FastEmbed/ONNX). Carregamento preguiçoso: a primeira consulta a frio paga por ele."""
    def __init__(self, sparse: bool = False):
        self.sparse = sparse
        self._dense = None
        self._bm25 = None

    @property
    def dense(self):
        if self._dense is None:
            from fastembed import TextEmbedding
            self._dense = TextEmbedding(MODEL)
        return self._dense

    def bm25(self, avg_len: float):
        if self._bm25 is None:
            from fastembed import SparseTextEmbedding
            self._bm25 = SparseTextEmbedding(BM25_MODEL, language=BM25_LANGUAGE, avg_len=avg_len)
        return self._bm25

    def embed_query(self, text: str) -> np.ndarray:
        v = np.asarray(next(iter(self.dense.query_embed([text]))), dtype=np.float32)
        return v / np.linalg.norm(v)


# O RRF do Qdrant 1.20.0 não desempata scores iguais de forma estável: a mesma consulta, no mesmo índice, devolveu ordens diferentes
# (91 de 450 consultas variaram entre execuções num ensaio de desenvolvimento). Os candidatos de B e C são reordenados no cliente por
# (-score, id), a mesma regra de D e da v1 (`ORDER BY ..., product_id`). O ensaio está descrito no LAB_JOURNAL.

def rrf(rankings: list[list[int]], k: int) -> list[int]:
    score: dict[int, float] = {}
    for ranking in rankings:
        for rank, product_id in enumerate(ranking, 1):
            score[product_id] = score.get(product_id, 0.0) + 1.0 / (k + rank)
    return [i for i, _ in sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))]


class Base:
    name = '?'
    uses_embeddings = False

    def __init__(self, index: Index, config: Config):
        self.index, self.config = index, config
        self.repo = SQLiteRepository(index.db)

    def retrieve(self, text: str, f: Filters, timing: dict) -> tuple[list[int], dict]:
        raise NotImplementedError

    def search(self, text: str, raw_filters: dict, limit: int = 5) -> dict:
        t0 = time.perf_counter()
        f = Filters(self.repo, raw_filters)
        timing = {'embed_ms': 0.0, 'index_ms': 0.0}
        ids, info = self.retrieve(text, f, timing)
        t1 = time.perf_counter()
        final, dropped = hydrate(self.repo, ids, f, limit)
        t2 = time.perf_counter()
        return {'ids': final, 'candidates': len(ids), 'dropped': dropped, 'embed_ms': timing['embed_ms'], 'index_ms': timing['index_ms'],
                'hydrate_ms': (t2 - t1) * 1000, 'e2e_ms': (t2 - t0) * 1000, **info}

    def close(self):
        self.repo.close()


class A(Base):
    """Baseline: a implementação original de busca da v1 (FTS5/BM25 + RapidFuzz), sem nenhuma alteração."""
    name = 'A'

    def retrieve(self, text, f, timing):
        t = time.perf_counter()
        ids, backend = self.repo.search_product_ids(text, f.category, f.min_cents, f.max_cents, f.only_available)
        timing['index_ms'] = (time.perf_counter() - t) * 1000
        return ids[:self.config.candidates], {'backend': backend, 'matches': len(ids)}


def qdrant_filter(f: Filters):
    from qdrant_client import models as m
    must = []
    if f.category_ids is not None:
        must.append(m.FieldCondition(key='category_id', match=m.MatchAny(any=list(f.category_ids))))
    if f.only_available:
        must.append(m.FieldCondition(key='available', match=m.MatchValue(value=True)))
    if f.min_cents is not None or f.max_cents is not None:
        must.append(m.FieldCondition(key='price_cents', range=m.Range(gte=f.min_cents, lte=f.max_cents)))
    return m.Filter(must=must) if must else None


class B(Base):
    """Qdrant Server, só vetor denso (HNSW, cosseno)."""
    name = 'B'
    uses_embeddings = True

    def __init__(self, index, config):
        super().__init__(index, config)
        from qdrant_client import QdrantClient
        self.client = QdrantClient(url=index.dense_url, timeout=60, check_compatibility=False)
        self.emb = Embedders()

    def retrieve(self, text, f, timing):
        from qdrant_client import models as m
        t = time.perf_counter()
        vector = self.emb.embed_query(text)
        timing['embed_ms'] = (time.perf_counter() - t) * 1000
        t = time.perf_counter()
        params = m.SearchParams(hnsw_ef=self.config.hnsw_ef) if self.config.hnsw_ef else None
        points = self.client.query_points(self.index.dense_collection, query=vector.tolist(), using='dense', query_filter=qdrant_filter(f),
                                          limit=self.config.candidates, search_params=params, with_payload=False).points
        timing['index_ms'] = (time.perf_counter() - t) * 1000
        return [p.id for p in sorted(points, key=lambda p: (-p.score, p.id))], {}        # desempate por ID (ver `stable_order`)

    def close(self):
        super().close()
        self.client.close()


class C(Base):
    """Qdrant Server híbrido: BM25 esparso (stemmer e stopwords em português) + denso, fundidos por RRF no servidor (Query API)."""
    name = 'C'
    uses_embeddings = True

    def __init__(self, index, config):
        super().__init__(index, config)
        from qdrant_client import QdrantClient
        self.client = QdrantClient(url=index.hybrid_url, timeout=60, check_compatibility=False)
        self.emb = Embedders()
        self.avg_len = json.loads((index.directory / 'meta.json').read_text(encoding='utf-8'))['bm25_avg_len']

    def retrieve(self, text, f, timing):
        from qdrant_client import models as m
        t = time.perf_counter()
        vector = self.emb.embed_query(text)
        sparse = next(iter(self.emb.bm25(self.avg_len).query_embed(text)))
        timing['embed_ms'] = (time.perf_counter() - t) * 1000
        t = time.perf_counter()
        qf = qdrant_filter(f)
        prefetch = [m.Prefetch(query=vector.tolist(), using='dense', limit=self.config.depth, filter=qf),
                    m.Prefetch(query=m.SparseVector(indices=sparse.indices.tolist(), values=sparse.values.tolist()), using='bm25', limit=self.config.depth, filter=qf)]
        points = self.client.query_points(self.index.hybrid_collection, prefetch=prefetch, query=m.RrfQuery(rrf=m.Rrf(k=self.config.rrf_k)),
                                          limit=self.config.candidates, with_payload=False).points
        timing['index_ms'] = (time.perf_counter() - t) * 1000
        return [p.id for p in sorted(points, key=lambda p: (-p.score, p.id))], {}        # desempate por ID (ver `stable_order`)

    def close(self):
        super().close()
        self.client.close()


class D(Base):
    """Sem banco vetorial: FTS5/BM25 do SQLite + embeddings em numpy (produto escalar exato) + RRF no processo."""
    name = 'D'
    uses_embeddings = True

    def __init__(self, index, config):
        super().__init__(index, config)
        self.emb = Embedders()
        self.matrix = np.load(index.directory / 'emb.npy')                     # N x 384, float32, normalizada
        self.ids = np.load(index.directory / 'ids.npy')
        self.snap = {k: np.load(index.directory / f'snap_{k}.npy') for k in ('category', 'price', 'available')}

    def lexical(self, text, f) -> list[int]:
        q = fts_query(text)
        if q is None:
            return []
        conditions, params = [], []
        if f.category_ids is not None:
            conditions.append('p.category_id IN (' + ','.join('?' * len(f.category_ids)) + ')')
            params.extend(f.category_ids)
        if f.only_available:
            conditions.append("p.status = 'active' AND p.stock_quantity > 0")
        effective = 'CASE WHEN pr.discount_percent IS NULL THEN p.price_cents ELSE discounted_cents(p.price_cents, pr.discount_percent) END'
        if f.min_cents is not None:
            conditions.append(effective + ' >= ?'); params.append(f.min_cents)
        if f.max_cents is not None:
            conditions.append(effective + ' <= ?'); params.append(f.max_cents)
        sql = ('SELECT p.product_id FROM products p JOIN categories c ON c.category_id = p.category_id '
               'LEFT JOIN promotions pr ON pr.product_id = p.product_id AND pr.is_active = 1 JOIN products_fts ON products_fts.rowid = p.product_id '
               'WHERE ' + ' AND '.join([*conditions, 'products_fts MATCH ?']) + ' ORDER BY bm25(products_fts, 4.0, 1.0, 2.0), p.product_id LIMIT ?')
        return [r[0] for r in self.repo.connection.execute(sql, [*params, q, self.config.depth]).fetchall()]

    def dense(self, vector, f, depth) -> tuple[list[int], list[float]]:
        scores = self.matrix @ vector
        mask = np.ones(len(scores), dtype=bool)
        if f.category_ids is not None:
            mask &= np.isin(self.snap['category'], f.category_ids)
        if f.only_available:
            mask &= self.snap['available']
        if f.min_cents is not None:
            mask &= self.snap['price'] >= f.min_cents
        if f.max_cents is not None:
            mask &= self.snap['price'] <= f.max_cents
        scores = np.where(mask, scores, -np.inf)
        k = min(depth, int(mask.sum()))
        if k == 0:
            return [], []
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top], kind='stable')]
        return [int(self.ids[i]) for i in top], [float(scores[i]) for i in top]

    def retrieve(self, text, f, timing):
        t = time.perf_counter()
        vector = self.emb.embed_query(text)
        timing['embed_ms'] = (time.perf_counter() - t) * 1000
        t = time.perf_counter()
        lexical = self.lexical(text, f)
        dense_ids, _ = self.dense(vector, f, self.config.depth)
        fused = rrf([dense_ids, lexical], self.config.rrf_k)
        timing['index_ms'] = (time.perf_counter() - t) * 1000
        return fused[:self.config.candidates], {'dense_only': dense_ids[:5]}


REGISTRY = {'A': A, 'B': B, 'C': C, 'D': D}
