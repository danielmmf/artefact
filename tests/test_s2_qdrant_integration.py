"""Integração com o Qdrant Server local (pulada se o servidor não estiver no ar): B e C propõem IDs, o SQLite confirma."""
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def server_up() -> bool:
    try:
        return all(urllib.request.urlopen(u + '/readyz', timeout=1).status == 200 for u in ('http://127.0.0.1:16333', 'http://127.0.0.1:16433'))
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not server_up(), reason='Qdrant Server do S2 fora do ar (docker/qdrant/s2-servers.sh up)')


@pytest.fixture(scope='module')
def smoke():
    from emporio_lab.s2 import build
    from emporio_lab.s2 import strategies as st
    directory = build.build_scale('smoke65', ROOT, 20261103, out=lambda *_: None, rebuild=True)
    return st.load_index(directory)


def test_b_and_c_return_the_product_of_an_exact_name_and_sqlite_confirms_it(smoke):
    from emporio_lab.s2 import strategies as st
    for cls in (st.B, st.C, st.D, st.A):
        s = cls(smoke, st.Config())
        r = s.search('Takamine GD20', {'only_available': True})
        assert 95 in r['ids'][:3], (cls.name, r['ids'])
        s.close()


def test_filters_run_inside_qdrant_and_results_are_valid_in_sqlite(smoke):
    from emporio.repository.sqlite import SQLiteRepository
    from emporio_lab.s2 import strategies as st
    repo = SQLiteRepository(smoke.db)
    for cls in (st.B, st.C):
        s = cls(smoke, st.Config())
        r = s.search('instrumento', {'category': 'Ukuleles', 'only_available': True})
        assert r['ids'] and all(repo.get_product(i).category_id == 9 for i in r['ids'])
        s.close()
    repo.close()


def test_the_payload_holds_no_commercial_authority(smoke):
    from qdrant_client import QdrantClient
    client = QdrantClient(url=smoke.hybrid_url, check_compatibility=False)
    point = client.retrieve(smoke.hybrid_collection, ids=[95], with_payload=True)[0]
    assert set(point.payload) == {'category_id', 'price_cents', 'available'}          # só pré-filtro; sem nome, descrição, estoque ou promoção
    client.close()


def test_server_version_is_the_pinned_one():
    import json
    assert json.loads(urllib.request.urlopen('http://127.0.0.1:16333/').read())['version'] == '1.20.0'
