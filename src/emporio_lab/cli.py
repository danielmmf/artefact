"""emporio-lab scenario list | run <nome> [--strict] [--allow-dirty]"""
import argparse
from pathlib import Path

from emporio_lab import runner
from emporio_lab import scenario as sc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='emporio-lab')
    sub = parser.add_subparsers(dest='group', required=True)
    group = sub.add_parser('scenario').add_subparsers(dest='action', required=True)
    group.add_parser('list')
    run = group.add_parser('run')
    run.add_argument('name')
    run.add_argument('--strict', action='store_true', help='sai com 1 se algum critério for reprovado (padrão: sai com 0 e registra no relatório)')
    run.add_argument('--allow-dirty', action='store_true', help='permite rodar com o cenário não commitado (o relatório registra que não foi pré-registrado)')
    run.add_argument('--escalas', help='só estas escalas, separadas por vírgula (execução de desenvolvimento; padrão: todas do YAML)')
    prereg = group.add_parser('preregister', help='registra o SHA do commit e o hash dos critérios de uma comparação, antes de executá-la')
    prereg.add_argument('name')
    args = parser.parse_args(argv)
    root = Path.cwd()
    if args.action == 'list':
        for s in sc.list_all(root):
            print(f'{s.nome:26} [{s.status:10}] {s.resumo()}')
        return 0
    if args.action == 'preregister':
        from emporio_lab import compare
        from emporio_lab.s2 import run as s2run
        try:
            print((s2run.preregister if sc.load(args.name, root).tipo == 'busca' else compare.preregister)(args.name, root))
        except sc.ScenarioError as error:
            print(f'ERRO: {error}')
            return runner.EXIT_INVALID
        return 0
    return runner.run(args.name, root, strict=args.strict, allow_dirty=args.allow_dirty, only_scales=args.escalas.split(',') if args.escalas else None)


if __name__ == '__main__':
    raise SystemExit(main())
