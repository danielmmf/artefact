"""Trace de metadados: nenhuma entrada ou saída textual é persistida."""
import fcntl
import hashlib
import json
import secrets
from pathlib import Path
from uuid import uuid4


class TurnTracer:
    def __init__(self, session_id: str, path: Path | None):
        # Chave efêmera por instância: não permite correlação entre reinícios.
        self.session = hashlib.blake2b(session_id.encode(), key=secrets.token_bytes(32), digest_size=32).hexdigest()
        self.path = path
        self.sequence = 0

    def new(self, model: str = 'unknown'):
        self.sequence += 1
        return {
            'session_hash': self.session, 'turn': self.sequence, 'turn_id': str(uuid4()),
            'iterations': 0, 'tool_calls': [],
            'llm': {'model': model, 'latency_ms': None, 'tokens': None, 'calls': 0},
            'search_backend': None,
            'validator': {'approved': 0, 'approved_values_brl': [], 'rejected': 0, 'regenerations': 0, 'fallback': False},
            'budget': {'estimated_tokens': None, 'limit': 16000, 'history_turns_truncated': 0},
            'auth': {'session': 'unknown', 'events': []}, 'errors': [],
        }

    def write(self, record):
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Um bloqueio entre processos impede linhas intercaladas em arquivos compartilhados.
        with self.path.open('a', encoding='utf-8') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                stream.write(json.dumps(record, ensure_ascii=True, separators=(',', ':')) + '\n')
                stream.flush()
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)
