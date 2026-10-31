import ast
import csv
import hashlib
import json
import shutil
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
from pypdf import PdfReader
from emporio.agent.tracer_bullet import run
from emporio.clock import now
from emporio.config import Settings
from emporio.ingest.pipeline import ingest, locate, policies
from emporio.llm.scripted import ScriptedLLM
from emporio.money import from_cents, to_cents
from emporio.repository.sqlite import SQLiteRepository
from emporio.tools.product import get_product

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw'
ADR = ROOT / 'docs/adr/ADR-000-especificacao-consolidada.md'

def hashes(path):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir() if p.is_file()}

def build(tmp_path, raw=RAW):
    db, processed = tmp_path / 'store.db', tmp_path / 'processed'
    ingest(raw, db, processed, ADR)
    return db, processed

def snapshot(db):
    with sqlite3.connect(db) as conn:
        return {t: conn.execute(f'SELECT * FROM {t} ORDER BY rowid').fetchall() for t in ('categories','customers','products','orders','order_items','promotions')}

def test_ingest_repeat_and_originals(tmp_path):
    before = hashes(RAW)
    db, processed = build(tmp_path)
    first = snapshot(db)
    outputs = hashes(processed)
    assert len(first['products']) == 65
    build(tmp_path)
    assert snapshot(db) == first
    assert hashes(processed) == outputs
    assert hashes(RAW) == before
    assert not (tmp_path / 'app.db').exists()

def test_csv_discovery(tmp_path):
    with pytest.raises(ValueError): locate(tmp_path, 'products')
    (tmp_path / 'products.csv').touch()
    assert locate(tmp_path, 'products').name == 'products.csv'
    (tmp_path / 'nome - products.csv').touch()
    with pytest.raises(ValueError): locate(tmp_path, 'products')

def test_duplicate_active_promotions_rejected_without_replacing_database(tmp_path):
    db, _ = build(tmp_path)
    old = snapshot(db)
    raw = tmp_path / 'raw'
    shutil.copytree(RAW, raw)
    path = locate(raw, 'promotions')
    with path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows, fields = list(reader), reader.fieldnames
    active = next(r for r in rows if r['is_active'] == '1')
    duplicate = dict(active, promotion_id='999')
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows + [duplicate])
    with pytest.raises(sqlite3.IntegrityError): build(tmp_path, raw)
    assert snapshot(db) == old

def test_integrity_invalid_row_and_foreign_key(tmp_path):
    raw = tmp_path / 'raw'; shutil.copytree(RAW, raw)
    path = locate(raw, 'order_items')
    with path.open('a', encoding='utf-8') as f: f.write('\n99999,1,81\n')
    with pytest.raises((ValueError, sqlite3.IntegrityError)): build(tmp_path, raw)

def test_money_clock_config(monkeypatch):
    assert to_cents('1.005') == 101
    assert to_cents('-1.005') == -101
    assert from_cents(59990) == Decimal('599.90')
    with pytest.raises(ValueError): to_cents('NaN')
    assert now('2026-03-25T10:00-04:00').utcoffset().total_seconds() == -14400
    with pytest.raises(ValueError): now('2026-03-25T10:00')
    monkeypatch.setenv('LLM_API_KEY', 'secret-value')
    assert 'secret-value' not in repr(Settings.from_env())

def test_read_only_and_tool(tmp_path):
    db, _ = build(tmp_path)
    repo = SQLiteRepository(db)
    with pytest.raises(sqlite3.OperationalError): repo.connection.execute('DELETE FROM products')
    assert get_product(repo, {'product_id': 81}).data['name'] == 'Yamaha C40 Nylon Natural'
    assert get_product(repo, {'product_id': 135}).data['description'] is None
    assert get_product(repo, {'product_id': 9999}).error.code == 'not_found'
    assert get_product(repo, {'product_id': '81'}).error.code == 'invalid_input'
    repo.close()

def test_policies_preserve_every_extracted_line(tmp_path):
    _, processed = build(tmp_path)
    result = (processed / 'policies.md').read_text()
    for n, page in enumerate(PdfReader(next(RAW.glob('*.pdf'))).pages, 1):
        assert f'· p.{n}]' in result
        for line in page.extract_text(extraction_mode='layout').splitlines():
            assert line in result
    for section in range(1, 11): assert f'[§{section} · p.' in result
    assert result == policies(next(RAW.glob('*.pdf')))

def test_quality_includes_adr_facts(tmp_path):
    _, processed = build(tmp_path)
    quality = (processed / 'QUALITY.md').read_text()
    expected = ADR.read_text().split('## 13. Inconsistências conhecidas dos dados\n', 1)[1].split('\n## 14.', 1)[0].strip()
    assert expected in quality

def test_tracer_no_personal_data(tmp_path):
    db, _ = build(tmp_path)
    repo = SQLiteRepository(db)
    trace = tmp_path / 'traces' / 'test.jsonl'
    with locate(RAW, 'customers').open(encoding='utf-8') as f:
        customers = list(csv.DictReader(f))
    person = customers[0]
    response = run(f"Olá {person['name']} {person['email']} {person['phone']}", ScriptedLLM(81), repo, trace)
    assert 'Yamaha C40' in response and '599.9' in response
    records = [json.loads(line) for line in trace.read_text().splitlines()]
    assert records == [{'tool': 'get_product', 'ok': True, 'error': None}]
    output = trace.read_text()
    for customer in customers:
        for field in ('name', 'email', 'phone'):
            if customer[field]: assert customer[field] not in output
    repo.close()

def test_layer_dependencies():
    for layer in ('domain', 'rules', 'security', 'tools'):
        for path in (ROOT / 'src/emporio' / layer).rglob('*.py'):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                modules = [x.name for x in node.names] if isinstance(node, ast.Import) else [node.module or ''] if isinstance(node, ast.ImportFrom) else []
                assert not any(m == 'emporio.agent' or m.startswith('emporio.agent.') or m == 'emporio.llm' or m.startswith('emporio.llm.') for m in modules), path
