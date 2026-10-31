"""Mini-avaliação offline; o arquivo JSON é também YAML válido."""
import json
from pathlib import Path
from emporio.repository.sqlite import SQLiteRepository
from emporio.tools.search import search_products


def run_bench(database: Path, cases_path: Path, output: Path) -> dict:
    cases = json.loads(cases_path.read_text(encoding='utf-8'))
    if not cases:
        raise ValueError('Mini-eval sem consultas')
    repo = SQLiteRepository(database)
    rows = []
    try:
        for case in cases:
            relevant = set(case['relevant'])
            if not relevant:
                raise ValueError('Consulta sem produtos relevantes')
            result = search_products(repo, {'query': case['query'], 'limit': 5})
            if not result.ok:
                raise ValueError('Consulta inválida no mini-eval')
            ids = [p['product_id'] for p in result.data['products']]
            recall = len(relevant.intersection(ids)) / len(relevant)
            rank = next((i for i, product_id in enumerate(ids, 1) if product_id in relevant), None)
            rows.append({'group': case['group'], 'query': case['query'], 'relevant': sorted(relevant),
                         'results': ids, 'recall_at_5': recall, 'reciprocal_rank': 1 / rank if rank else 0.0,
                         'backend': result.data['search_backend']})
    finally:
        repo.close()
    report = {'cases': rows, 'recall_at_5': sum(r['recall_at_5'] for r in rows)/len(rows),
              'mrr': sum(r['reciprocal_rank'] for r in rows)/len(rows),
              'limitations': 'Conjunto pequeno e rótulos manuais; relevância não exaustiva, não mede latência nem generalização.'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main() -> None:
    root = Path.cwd()
    report = run_bench(root/'var/store.db', root/'evals/search_queries.yaml', root/'evals/reports/search.json')
    print(f"Recall@5: {report['recall_at_5']:.3f} | MRR: {report['mrr']:.3f}")

if __name__ == '__main__':
    main()
