import json
from pathlib import Path
from emporio.ingest.pipeline import ingest
from emporio.search_bench import run_bench

ROOT = Path(__file__).resolve().parents[1]

def test_benchmark_runs_offline_and_reports_measured_results(tmp_path):
    database = tmp_path/'store.db'
    ingest(ROOT/'data/raw', database, tmp_path/'processed', ROOT/'docs/adr/ADR-000-especificacao-consolidada.md')
    output = tmp_path/'report.json'
    report = run_bench(database, ROOT/'evals/search_queries.yaml', output)
    assert report == json.loads(output.read_text())
    assert len(report['cases']) == 10
    assert {r['group'] for r in report['cases']} == {'nome', 'intencao', 'ambiguas'}
    assert report['recall_at_5'] == sum(r['recall_at_5'] for r in report['cases'])/10
    assert report['mrr'] == sum(r['reciprocal_rank'] for r in report['cases'])/10
