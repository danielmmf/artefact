"""Processo de medição de UMA estratégia (processo novo => primeira consulta realmente fria e RSS próprio).

Uso: python -m emporio_lab.s2.worker --strategy A --index var/s2/<escala> --queries q.json --config '{...}' --out saida.json
Passos: constrói a estratégia; 1 consulta fria; 1 passe de aquecimento (não medido); 1 passe medido com todas as consultas.
"""
import argparse
import json
import time
from pathlib import Path

from emporio_lab.s2 import strategies as st


def proc_mb(field: str) -> float:
    return int(open('/proc/self/status').read().split(field + ':')[1].split()[0]) / 1024


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--strategy', required=True, choices=st.STRATEGIES)
    ap.add_argument('--index', required=True)
    ap.add_argument('--queries', required=True)
    ap.add_argument('--config', default='{}')
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    queries = json.loads(Path(args.queries).read_text(encoding='utf-8'))
    index = st.load_index(Path(args.index))
    config = st.Config(**json.loads(args.config))
    t = time.perf_counter()
    strategy = st.REGISTRY[args.strategy](index, config)
    init_ms = (time.perf_counter() - t) * 1000
    rss_init = proc_mb('VmRSS')
    first = queries[0]
    cold = strategy.search(first['text'], first['filters'])
    for q in queries:                                   # aquecimento
        strategy.search(q['text'], q['filters'])
    rows = []
    t_pass = time.perf_counter()
    for q in queries:
        r = strategy.search(q['text'], q['filters'])
        rows.append({'id': q['id'], **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}})
    wall = time.perf_counter() - t_pass
    strategy.close()
    result = {'strategy': args.strategy, 'init_ms': round(init_ms, 2), 'cold': {k: (round(v, 3) if isinstance(v, float) else v) for k, v in cold.items()},
              'rss_after_init_mb': round(rss_init, 1), 'rss_end_mb': round(proc_mb('VmRSS'), 1), 'rss_peak_mb': round(proc_mb('VmHWM'), 1),
              'pass_wall_s': round(wall, 3), 'qps': round(len(queries) / wall, 2), 'queries': rows}
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
