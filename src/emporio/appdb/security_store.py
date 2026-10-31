"""Estado de segurança local; não armazena contatos nem mensagens."""
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

SCHEMA = '''
CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, mode TEXT NOT NULL CHECK(mode IN ('anonymous','simulated_authenticated')), customer_id INTEGER, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
 CHECK((mode='anonymous' AND customer_id IS NULL) OR (mode='simulated_authenticated' AND customer_id > 0)));
CREATE TABLE IF NOT EXISTS order_access (session_id TEXT NOT NULL REFERENCES sessions(session_id), order_id INTEGER NOT NULL, granted_at TEXT NOT NULL, expires_at TEXT NOT NULL, PRIMARY KEY(session_id, order_id));
CREATE TABLE IF NOT EXISTS verification_attempts (id INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id), order_id INTEGER NOT NULL, attempted_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS attempts_order ON verification_attempts(order_id);
CREATE TABLE IF NOT EXISTS order_locks (order_id INTEGER PRIMARY KEY, locked_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS session_locks (session_id TEXT PRIMARY KEY REFERENCES sessions(session_id), locked_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS attempts_session ON verification_attempts(session_id);
CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id), created_at TEXT NOT NULL, content_tokenized TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY, order_id INTEGER, category TEXT NOT NULL, summary_tokenized TEXT NOT NULL, created_at TEXT NOT NULL);
PRAGMA user_version = 1;
'''

def timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Relógio precisa de fuso horário')
    return value.astimezone(timezone.utc).isoformat(timespec='microseconds')

class SecurityStore:
    def __init__(self, path: Path, *, store_path: Path):
        if path.resolve() == store_path.resolve() or (path.exists() and store_path.exists() and path.samefile(store_path)):
            raise ValueError('app.db e store.db devem ser distintos')
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=10)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA foreign_keys = ON')
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def create_session(self, at: datetime, customer_id: int | None = None) -> str:
        if customer_id is not None and (isinstance(customer_id, bool) or not isinstance(customer_id, int) or customer_id <= 0 or customer_id > 2**63-1):
            raise ValueError('Cliente inválido')
        session_id = str(uuid4())
        with self.connection:
            self.connection.execute('INSERT INTO sessions VALUES (?,?,?,?,?)', (session_id, 'anonymous' if customer_id is None else 'simulated_authenticated', customer_id, timestamp(at), timestamp(at + timedelta(minutes=15))))
        return session_id

    def session(self, session_id: str, at: datetime):
        current = timestamp(at)
        return self.connection.execute('SELECT mode, customer_id FROM sessions WHERE session_id = ? AND created_at <= ? AND expires_at > ?', (session_id, current, current)).fetchone()

    def locked(self, order_id: int) -> bool:
        return self.connection.execute('SELECT 1 FROM order_locks WHERE order_id = ?', (order_id,)).fetchone() is not None

    def session_locked(self, session_id: str) -> bool:
        return self.connection.execute('SELECT 1 FROM session_locks WHERE session_id = ?', (session_id,)).fetchone() is not None

    def record_verification(self, session_id: str, order_id: int, at: datetime, verified: bool) -> tuple[str, str | None]:
        current = timestamp(at)
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            session = self.session(session_id, at)
            if not session:
                self.connection.rollback()
                return 'not_verified', None
            if self.locked(order_id) or self.session_locked(session_id):
                self.connection.rollback()
                return 'locked', None
            if verified:
                session_expiry = self.connection.execute('SELECT expires_at FROM sessions WHERE session_id = ?', (session_id,)).fetchone()[0]
                expires = min(timestamp(at + timedelta(minutes=15)), session_expiry)
                self.connection.execute('INSERT INTO order_access VALUES (?,?,?,?) ON CONFLICT(session_id,order_id) DO UPDATE SET granted_at=excluded.granted_at, expires_at=excluded.expires_at', (session_id, order_id, current, expires))
                self.connection.commit()
                return 'granted', expires
            self.connection.execute('INSERT INTO verification_attempts(session_id,order_id,attempted_at) VALUES (?,?,?)', (session_id, order_id, current))
            order_count = self.connection.execute('SELECT COUNT(*) FROM verification_attempts WHERE order_id = ?', (order_id,)).fetchone()[0]
            session_count = self.connection.execute('SELECT COUNT(*) FROM verification_attempts WHERE session_id = ?', (session_id,)).fetchone()[0]
            if order_count >= 3:
                self.connection.execute('INSERT OR IGNORE INTO order_locks VALUES (?,?)', (order_id, current))
                self.connection.execute("INSERT INTO tickets(order_id,category,summary_tokenized,created_at) VALUES (?,'security','Bloqueio após tentativas de verificação.',?)", (order_id, current))
            if session_count >= 3:
                self.connection.execute('INSERT OR IGNORE INTO session_locks VALUES (?,?)', (session_id, current))
                self.connection.execute("INSERT INTO tickets(order_id,category,summary_tokenized,created_at) VALUES (NULL,'security','Sessão bloqueada após tentativas de verificação.',?)", (current,))
            self.connection.commit()
            return ('locked' if order_count >= 3 or session_count >= 3 else 'not_verified'), None
        except BaseException:
            self.connection.rollback()
            raise

    def has_grant(self, session_id: str, order_id: int, at: datetime) -> bool:
        now = timestamp(at)
        return self.connection.execute('SELECT 1 FROM order_access WHERE session_id = ? AND order_id = ? AND granted_at <= ? AND expires_at > ?', (session_id, order_id, now, now)).fetchone() is not None
