import csv
from emporio.ingest.pipeline import locate
from emporio.security.contacts import ContactVault
from emporio.tools.escalation import escalate_to_human
from test_order_security import env, create_session, RAW

def test_ticket_discards_free_text_and_contains_no_contacts(env):
    session = create_session(env)
    with locate(RAW, 'customers').open(encoding='utf-8') as f:
        customers = list(csv.DictReader(f))
    customer = customers[0]
    secret = f"{customer['name']} {customer['email']} {customer['phone']} Nome Inventado Silva"
    result = escalate_to_human(env['state'], lambda:env['time'][0], session, {'category':'reclamacao', 'summary':secret})
    assert result.ok and result.data['response_time'] == '24 horas úteis'
    stored = env['state'].connection.execute('SELECT category,summary_tokenized FROM tickets').fetchone()
    assert stored[0] == 'reclamacao' and stored[1] == 'Solicitação encaminhada à equipe.'
    persisted = env['app_path'].read_bytes()
    result_text = result.model_dump_json()
    for customer in customers:
        for key in ('email', 'phone', 'name'):
            if customer[key]:
                assert customer[key].encode() not in persisted
                assert customer[key] not in result_text
    assert b'Nome Inventado Silva' not in persisted

def test_invalid_ticket_does_not_echo_private_data(env):
    s = create_session(env)
    result = escalate_to_human(env['state'], lambda:env['time'][0], s, {'category':'invalid@example.invalid', 'summary':'x'})
    assert result.error.code == 'invalid_input' and 'invalid@example.invalid' not in result.model_dump_json()
    assert env['state'].connection.execute('SELECT COUNT(*) FROM tickets').fetchone()[0] == 0
    assert escalate_to_human(env['state'], lambda:env['time'][0], 'unknown', {'category':'outros','summary':'x'}).error.code == 'access_denied'

def test_tokenization_roundtrip_and_isolation(env):
    a, b = ContactVault('session-a'), ContactVault('session-b')
    text = 'Contato: Pessoa.Example@example.invalid ou (67) 99812-3456.'
    redacted = a.tokenize(text)
    assert 'Pessoa.Example@example.invalid' not in redacted and '99812-3456' not in redacted
    assert '[EMAIL_1]' in redacted and '[PHONE_1]' in redacted
    assert a.restore(redacted) == text
    assert b.restore(redacted) == redacted
    assert a.resolve('[EMAIL_1]') == ('email', 'pessoa.example@example.invalid')
    assert b.resolve('[EMAIL_1]') is None

def test_tokenizer_covers_official_contacts_in_memory():
    with locate(RAW, 'customers').open(encoding='utf-8') as f:
        customers = list(csv.DictReader(f))
    for customer in customers:
        vault = ContactVault('test-session')
        for key in ('email', 'phone'):
            value = customer[key]
            if value:
                source = f'Contato: {value}'
                tokenized = vault.tokenize(source)
                assert value not in tokenized
                assert vault.restore(tokenized) == source
