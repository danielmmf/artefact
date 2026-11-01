"""Histórico apenas de mensagens tokenizadas e orçamento aproximado por chamada."""
import json
from emporio.agent.offline import TOKEN
from emporio.appdb.security_store import SecurityStore, timestamp
from datetime import datetime

BUDGET = 16000

def estimated_tokens(messages: list[dict], tools: list[dict]) -> int:
    # Estimativa intencionalmente conservadora de bytes UTF-8/3, não tokenizer do modelo.
    payload = json.dumps({'messages':messages, 'tools':tools}, ensure_ascii=False).encode('utf-8')
    return (len(payload) + 2) // 3

def load_history(state: SecurityStore, session_id: str) -> list[dict]:
    rows = state.connection.execute('SELECT content_tokenized FROM history WHERE session_id=? ORDER BY id', (session_id,)).fetchall()
    turns = []
    for row in rows:
        turn = json.loads(row[0])
        if not isinstance(turn, dict) or set(turn) != {'user','assistant'} or not all(isinstance(v, str) for v in turn.values()):
            raise ValueError('Histórico inválido')
        # Mapa de tokens não é persistido; não reaproveitar referências antigas ambiguamente.
        turns.append({k: TOKEN.sub('[CONTATO PROTEGIDO]', v) for k, v in turn.items()})
    return turns

def save_turn(state: SecurityStore, session_id: str, at: datetime, user: str, assistant: str) -> None:
    with state.connection:
        state.connection.execute('INSERT INTO history(session_id,created_at,content_tokenized) VALUES (?,?,?)',
                                 (session_id, timestamp(at), json.dumps({'user':user,'assistant':assistant}, ensure_ascii=False)))

def trim_history(system: dict, turns: list[dict], current: list[dict], tools: list[dict], budget: int = BUDGET) -> list[dict] | None:
    def flatten(selected):
        return [system] + [m for t in selected for m in ({'role':'user','content':t['user']}, {'role':'assistant','content':t['assistant']})] + current
    selected = list(turns)
    while selected and estimated_tokens(flatten(selected), tools) > budget:
        selected.pop(0)
    messages = flatten(selected)
    return messages if estimated_tokens(messages, tools) <= budget else None
