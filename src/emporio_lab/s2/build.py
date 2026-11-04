"""Constrói os índices de uma escala: SQLite sintético (ou a base original), embeddings em cache, coleções no Qdrant Server."""
import json
import os
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path

import numpy as np

from emporio.rules.pricing import discounted_cents
from emporio_lab.s2 import catalog as cat
from emporio_lab.s2 import strategies as st
from emporio_lab.s2 import vocab

S2_DIR = Path('var/s2')
DENSE_URL, HYBRID_URL = 'http://127.0.0.1:16333', 'http://127.0.0.1:16433'
SCALES = {'smoke65': None, 'catalogo5k': 5000, 'catalogo50k': 50000}
SERVERS_SCRIPT = Path('docker/qdrant/s2-servers.sh')


def servers_up(root: Path) -> None:
    subprocess.run([str(root / SERVERS_SCRIPT), 'up'], check=True)


def du(path: Path) -> int:
    return sum(f.stat().st_blocks * 512 for f in path.rglob('*') if f.is_file()) if path.exists() else 0   # uso real (arquivos esparsos)


def rss_mb() -> float:
    return int(open('/proc/self/status').read().split('VmRSS:')[1].split()[0]) / 1024


def load_rows(db: Path) -> list[dict]:
    import sqlite3
    con = sqlite3.connect(f'{db.resolve().as_uri()}?mode=ro', uri=True)
    rows = con.execute('''SELECT p.product_id, p.name, p.description, p.category_id, c.name, p.price_cents, p.status, p.stock_quantity, pr.discount_percent
                          FROM products p JOIN categories c ON c.category_id = p.category_id
                          LEFT JOIN promotions pr ON pr.product_id = p.product_id AND pr.is_active = 1 ORDER BY p.product_id''').fetchall()
    con.close()
    return [{'id': r[0], 'name': r[1], 'description': r[2], 'category_id': r[3], 'category': r[4],
             'price': discounted_cents(r[5], __import__('decimal').Decimal(r[8])) if r[8] is not None else r[5],
             'available': r[6] == 'active' and r[7] > 0} for r in rows]


def versions() -> dict:
    out = {p: metadata.version(p) for p in ('fastembed', 'qdrant-client', 'numpy', 'onnxruntime', 'rapidfuzz', 'py-rust-stemmers')}
    out['python'] = sys.version.split()[0]
    return out


def model_files(model: str) -> dict:
    """Revisão (commit no Hugging Face) e arquivo ONNX do modelo denso efetivamente baixado."""
    from fastembed import TextEmbedding
    info = next(m for m in TextEmbedding.list_supported_models() if m['model'] == model)
    return {'modelo': model, 'repositorio_onnx': info['sources']['hf'], 'arquivo': info['model_file'], 'dim': info['dim'], 'licenca': info['license'],
            'tamanho_gb': info['size_in_GB'], 'descricao': info['description']}


def build_scale(scale: str, root: Path, seed: int, out=print, *, rebuild: bool = False) -> Path:
    from qdrant_client import QdrantClient
    from qdrant_client import models as m
    directory = root / S2_DIR / scale
    if (directory / 'meta.json').exists() and not rebuild:
        return directory
    directory.mkdir(parents=True, exist_ok=True)
    timings: dict = {}
    if SCALES[scale] is None:
        db = root / 'var/store.db'
        products_hash, sqlite_timing = None, {'bytes': db.stat().st_size}
    else:
        products = cat.generate(SCALES[scale], seed)
        products_hash = cat.catalog_hash(products)
        db = directory / 'store.db'
        out(f'[{scale}] gerando SQLite sintético ({len(products)} produtos)...')
        sqlite_timing = cat.build_sqlite(products, db)
        db = db.resolve()
    rows = load_rows(db)
    texts = [cat.document_text(r['name'], r['description'], r['category']) for r in rows]
    ids = np.array([r['id'] for r in rows], dtype=np.int64)

    out(f'[{scale}] embeddings densos ({len(texts)} documentos)...')
    from fastembed import SparseTextEmbedding, TextEmbedding
    t = time.perf_counter()
    model = TextEmbedding(st.MODEL)
    timings['carregar_modelo_denso_s'] = round(time.perf_counter() - t, 2)
    t = time.perf_counter()
    matrix = np.array(list(model.embed(texts, batch_size=64)), dtype=np.float32)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    timings['embeddings_densos_s'] = round(time.perf_counter() - t, 2)
    np.save(directory / 'emb.npy', matrix)
    np.save(directory / 'ids.npy', ids)
    np.save(directory / 'snap_category.npy', np.array([r['category_id'] for r in rows]))
    np.save(directory / 'snap_price.npy', np.array([r['price'] for r in rows]))
    np.save(directory / 'snap_available.npy', np.array([r['available'] for r in rows]))

    avg_len = float(np.mean([len([w for w in vocab.tokens(x) if w not in vocab.STOPWORDS]) for x in texts]))
    t = time.perf_counter()
    sparse = list(SparseTextEmbedding(st.BM25_MODEL, language=st.BM25_LANGUAGE, avg_len=avg_len).embed(texts, batch_size=256))
    timings['embeddings_esparsos_bm25_s'] = round(time.perf_counter() - t, 2)

    def upload(url: str, collection: str, hybrid: bool) -> dict:
        client = QdrantClient(url=url, timeout=300, check_compatibility=False)
        if client.collection_exists(collection):
            client.delete_collection(collection)
        t0 = time.perf_counter()
        client.create_collection(collection, vectors_config={'dense': m.VectorParams(size=st.DENSE_DIM, distance=m.Distance.COSINE)},
                                 sparse_vectors_config={'bm25': m.SparseVectorParams(modifier=m.Modifier.IDF)} if hybrid else None)
        for key, schema in (('category_id', m.PayloadSchemaType.INTEGER), ('price_cents', m.PayloadSchemaType.INTEGER), ('available', m.PayloadSchemaType.BOOL)):
            client.create_payload_index(collection, key, schema)

        def points():
            for i, r in enumerate(rows):
                vec = {'dense': matrix[i].tolist()}
                if hybrid:
                    vec['bm25'] = m.SparseVector(indices=sparse[i].indices.tolist(), values=sparse[i].values.tolist())
                yield m.PointStruct(id=r['id'], vector=vec, payload={'category_id': r['category_id'], 'price_cents': r['price'], 'available': r['available']})
        client.upload_points(collection, points(), batch_size=256, parallel=1)
        t_upload = time.perf_counter() - t0
        while True:                                     # espera o otimizador terminar (índice HNSW pronto)
            info = client.get_collection(collection)
            if info.status == m.CollectionStatus.GREEN and info.indexed_vectors_count is not None:
                break
            time.sleep(0.5)
        total = time.perf_counter() - t0
        client.close()
        return {'enviar_pontos_s': round(t_upload, 2), 'indice_pronto_s': round(total, 2), 'pontos': info.points_count, 'vetores_indexados_hnsw': info.indexed_vectors_count}

    out(f'[{scale}] Qdrant denso...')
    timings['qdrant_denso'] = upload(DENSE_URL, f'{scale}_dense', False)
    out(f'[{scale}] Qdrant híbrido...')
    timings['qdrant_hibrido'] = upload(HYBRID_URL, f'{scale}_hybrid', True)
    server = json.loads(__import__('urllib.request').request.urlopen(DENSE_URL + '/').read())
    sizes = {'sqlite_total_bytes': db.stat().st_size, 'embeddings_npy_bytes': (directory / 'emb.npy').stat().st_size,
             'qdrant_denso_bytes': du(root / S2_DIR / 'qdrant-dense' / 'data' / 'collections' / f'{scale}_dense'),
             'qdrant_hibrido_bytes': du(root / S2_DIR / 'qdrant-hybrid' / 'data' / 'collections' / f'{scale}_hybrid')}
    meta = {'scale': scale, 'n': len(rows), 'db': str(db), 'dense_collection': f'{scale}_dense', 'hybrid_collection': f'{scale}_hybrid',
            'dense_url': DENSE_URL, 'hybrid_url': HYBRID_URL, 'bm25_avg_len': avg_len, 'catalog_sha256': products_hash, 'seed': seed,
            'tempos': timings | {'sqlite': sqlite_timing}, 'tamanhos': sizes, 'qdrant_server': server['version'], 'versoes': versions(), 'modelo': model_files(st.MODEL)}
    (directory / 'meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return directory
