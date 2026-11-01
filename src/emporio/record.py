"""Grava uma conversa REAL (LLM do .env) em Markdown para `examples/`.

As mensagens do cliente são fornecidas por quem grava (o cliente é fictício); as respostas vêm do LLM
configurado, com as ferramentas rodando ao vivo. O texto exportado usa os contatos já tokenizados
([EMAIL_1], [PHONE_1]) e nunca grava prompts, argumentos de ferramentas ou chaves.

    uv run python -m emporio.record --out examples/01-catalogo.md --title "Catálogo" "Quais violões até R$ 1000?"
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from emporio.agent.loop import ConversationEngine, SAFE
from emporio.cli import configured, open_registry
from emporio.config import Settings
from emporio.llm.openai_compat import OpenAICompatibleAdapter

DEFAULT_NOW = '2026-03-25T10:00:00-04:00'  # S-h: relógio fixo das demonstrações (DECISIONS.md)


def tool_names(messages: list[dict]) -> list[str]:
    ids = {}
    for m in messages:
        for call in m.get('tool_calls') or []:
            ids[call['id']] = call['function']['name']
    out = []
    for m in messages:
        if m['role'] == 'tool':
            result = json.loads(m['content'])
            status = 'ok' if result.get('ok') else (result.get('error') or {}).get('code', 'erro')
            out.append(f"`{ids.get(m.get('tool_call_id'), '?')}` ({status})")
    return out


def render(title: str, model: str, clock: datetime, customer: int | None, turns: list[dict]) -> str:
    mode = f'identidade simulada `--customer {customer}`' if customer else 'anônimo (sem identidade)'
    lines = [f'# {title}', '',
             f'> **Conversa real** com o LLM `{model}` (ferramentas executadas ao vivo sobre os dados oficiais), gravada com `python -m emporio.record`.',
             f'> Relógio fixo: `{clock.isoformat()}` · Modo: {mode} · A verificação por contato é **demonstrativa**, não autenticação real.',
             '> As mensagens do cliente foram escritas por quem gravou (cliente fictício); contatos aparecem tokenizados.', '']
    for turn in turns:
        lines += [f"**Cliente:** {turn['user']}", '']
        if turn['tools']:
            lines += ['_Ferramentas consultadas: ' + ', '.join(turn['tools']) + '_', '']
        lines += ['**Atendente:** ' + turn['assistant'], '']
        if turn['assistant'] == SAFE:
            lines += ['_(resposta segura de contingência do agente)_', '']
    return '\n'.join(lines).rstrip('\n') + '\n'


def record(root: Path, messages: list[str], *, title: str, customer: int | None, now: str, llm=None,
           settings: Settings | None = None, trace: Path | None = None) -> str:
    settings = settings or Settings.from_env()
    when = datetime.fromisoformat(now)
    if llm is None:
        if not configured(settings):
            raise SystemExit('Configure LLM_BASE_URL, LLM_MODEL e LLM_API_KEY no .env para gravar conversas reais.')
        llm = OpenAICompatibleAdapter(settings)
    turns = []
    with open_registry(root, customer, lambda: when) as registry:
        engine = ConversationEngine(registry, llm, trace or root / 'var/traces/record.jsonl')
        for text in messages:
            answer, history = engine.turn(text)
            turns.append({'user': registry.context.vault.tokenize(text), 'assistant': answer, 'tools': tool_names(history)})
    return render(title, str(getattr(llm, 'model', settings.llm_model)), when, customer, turns)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='python -m emporio.record')
    parser.add_argument('messages', nargs='+', help='mensagens do cliente, em ordem')
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--title', required=True)
    parser.add_argument('--customer', type=int)
    parser.add_argument('--now', default=DEFAULT_NOW)
    args = parser.parse_args(argv)
    text = record(Path.cwd(), args.messages, title=args.title, customer=args.customer, now=args.now)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding='utf-8')
    print(f'Gravado: {args.out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
