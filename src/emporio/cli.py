"""Entradas locais; o gate para provedores permanece fechado."""
import argparse
import json
from pathlib import Path

from emporio.agent.loop import ConversationEngine, SAFE
from emporio.appdb.security_store import SecurityStore, timestamp
from emporio.clock import make_clock
from emporio.config import Settings
from emporio.ingest.pipeline import ingest
from emporio.llm.scripted import AssistantReply, ConversationScriptedLLM, FunctionCall
from emporio.repository.sqlite import SQLiteRepository
from emporio.security.contacts import ContactVault
from emporio.tools.registry import ToolContext, ToolRegistry


def ingest_project(root: Path) -> None:
    ingest(root / 'data/raw', root / 'var/store.db', root / 'data/processed', root / 'docs/adr/ADR-000-especificacao-consolidada.md')


def chat_offline(root: Path, customer: int | None = None, *, clock=None, read=input, write=print) -> int:
    """Executa somente cenários fixos; clock e I/O podem ser injetados em testes."""
    repo = state = None
    session = None
    clock = clock or make_clock(Settings.from_env())
    try:
        if not (root / 'var/store.db').exists() or not (root / 'data/processed/policies.md').exists():
            ingest_project(root)
        repo = SQLiteRepository(root / 'var/store.db')
        state = SecurityStore(root / 'var/app.db', store_path=root / 'var/store.db')
        session = state.create_session(clock(), customer)
        registry = ToolRegistry(ToolContext(repo, state, clock, session, ContactVault(session)))
        engine = ConversationEngine(registry, ConversationScriptedLLM([]), root / 'var/traces/offline.jsonl')
        write('DEMONSTRAÇÃO OFFLINE: respostas e ferramentas seguem roteiros fixos; não há raciocínio de IA real.')
        write('Identidade --customer <id> é simulada; verificação por contato é demonstrativa, não autenticação real.')
        while True:
            choice = read('Cenários: 1 horário da loja; 2 produto 90; sair: ').strip().lower()
            if choice in {'sair', 'q', 'quit'}:
                break
            if choice not in {'1', '2'}:
                write('Escolha 1, 2 ou sair.')
                continue
            name, args = ('store_status', '{}') if choice == '1' else ('get_product', '{"product_id":90}')
            engine.llm = ConversationScriptedLLM([AssistantReply(tool_calls=(FunctionCall('demo', name, args),)), 'Consulta demonstrativa concluída.'])
            answer, messages = engine.turn('Consulte o cenário demonstrativo selecionado.')
            write(answer)
            if answer != SAFE:
                result = next((json.loads(m['content']) for m in messages if m['role'] == 'tool'), None)
                if result and result['ok']:
                    data = result['data']
                    fields = ('is_open', 'today_hours') if choice == '1' else ('availability', 'price_info')
                    write(json.dumps({k: data[k] for k in fields if k in data}, ensure_ascii=False))
        return 0
    except (EOFError, KeyboardInterrupt):
        write('\nSessão demonstrativa encerrada.')
        return 0
    except Exception:
        write('Não foi possível executar a demonstração offline.')
        return 1
    finally:
        if state is not None:
            try:
                if session is not None:
                    with state.connection:
                        state.connection.execute('UPDATE sessions SET expires_at=? WHERE session_id=?', (timestamp(clock()), session))
            finally:
                state.close()
        if repo is not None:
            repo.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog='emporio')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('ingest')
    chat = sub.add_parser('chat')
    chat.add_argument('--offline', action='store_true')
    chat.add_argument('--customer', type=int)
    args = parser.parse_args()
    if args.command == 'ingest':
        ingest_project(Path.cwd())
        print('Ingestão concluída.')
    elif not args.offline:
        parser.error('Provedor externo bloqueado; use chat --offline para a demonstração.')
    else:
        raise SystemExit(chat_offline(Path.cwd(), args.customer))
