import argparse
from pathlib import Path
from emporio.ingest.pipeline import ingest

def main() -> None:
    parser = argparse.ArgumentParser(prog='emporio')
    parser.add_subparsers(dest='command', required=True).add_parser('ingest')
    parser.parse_args()
    root = Path.cwd()
    ingest(root / 'data/raw', root / 'var/store.db', root / 'data/processed', root / 'docs/adr/ADR-000-especificacao-consolidada.md')
    print('Ingestão concluída.')
