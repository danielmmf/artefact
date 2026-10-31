from datetime import datetime
from pathlib import Path
import pytest
from emporio.appdb.security_store import SecurityStore
from emporio.security.contacts import ContactVault

NOW = datetime.fromisoformat('2026-03-25T10:00-04:00')

def test_idempotent_schema_and_private_vault(tmp_path):
    app, store = tmp_path/'app.db', tmp_path/'store.db'
    state = SecurityStore(app, store_path=store)
    session = state.create_session(NOW)
    vault = ContactVault(session)
    reference = vault.add('test@example.invalid')
    assert vault.resolve(reference) == ('email', 'test@example.invalid')
    assert ContactVault(session).resolve(reference) is None
    state.close()
    state = SecurityStore(app, store_path=store)
    assert state.session(session, NOW)['mode'] == 'anonymous'
    state.close()
    assert b'test@example.invalid' not in app.read_bytes()
    with pytest.raises(ValueError): SecurityStore(app, store_path=app)
