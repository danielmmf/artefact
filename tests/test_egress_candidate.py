import hashlib
import json
import socket
import subprocess
from pathlib import Path

import pytest

from emporio.agent.loop import ConversationEngine, SAFE
from emporio.config import Settings
from emporio.egress.candidate import ProjectionError, candidate_prompt, project_messages, project_tool
from emporio.egress.harness import inspect_capture
from emporio.llm.openai_compat import CaptureTransport, OpenAICompatibleAdapter, SimulatedResponse
from emporio.llm.scripted import AssistantReply, ConversationScriptedLLM, FunctionCall
from test_integration_offline import setup_registry
from test_order_security import env

MANUAL = Path('data/processed/policies.md')


def test_manual_candidate_is_deterministic_and_changed_input_fails_closed(tmp_path):
    original = MANUAL.read_bytes()
    one = candidate_prompt(MANUAL)
    assert one == candidate_prompt(MANUAL) and MANUAL.read_bytes() == original
    for value in ('(67) 3341-4444', '(67) 3321-4500', 'contato@emporiodamusica.com.br', 'contato@empóriodamusica.com.br', 'Rua 14 de Maio, 3200', '79202-333'):
        assert value not in one
    for n in range(1, 11):
        assert f'[§{n} ' in one or f'[§{n}.' in one
    other = tmp_path/'manual.md'
    other.write_bytes(original + b'\nnew@example.invalid')
    with pytest.raises(ProjectionError):
        candidate_prompt(other)
    other.write_bytes(original.replace(b'[\xc2\xa79 ', b'[\xc2\xa78 '))
    with pytest.raises(ProjectionError):
        candidate_prompt(other)


@pytest.mark.parametrize('name', ['search_products','get_product','quote_payment','store_status','verify_order_ownership','get_order','check_return_eligibility','escalate_to_human'])
def test_every_tool_projects_only_approved_types(name):
    bad = 'Ana Exemplo pessoa@example.invalid +55 (67) 99999-8888 token-secret-ignore-rules'
    result = {'ok': True, 'data': {'name': bad, 'description': bad, 'notes': bad, 'first_name': bad, 'tracking_code': bad, 'ticket_id': bad, 'status': bad, 'products': [{'name': bad, 'description': bad, 'product_id': 90, 'price_info': {'list_price':'10.00', 'name': bad}}], 'price_info': {'list_price': '10.00', 'extra': bad}}}
    serialized = json.dumps(project_tool(name, result))
    assert bad not in serialized and 'example.invalid' not in serialized and 'token-secret' not in serialized
    assert project_tool(name, {'ok': False, 'error': {'code': bad, 'message_for_agent': bad}}) == {'ok': False, 'error': {'code': 'internal_error'}}


def test_real_engine_messages_to_serialized_capture_are_projected(env, monkeypatch):
    attempts = []
    def forbidden(*a, **kw):
        attempts.append(True)
        raise AssertionError('network attempted')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)
    monkeypatch.setattr(socket.socket, 'sendto', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    registry = setup_registry(env)
    other = setup_registry(env)
    assert ConversationEngine(other, ConversationScriptedLLM(['historico-outra-sessao'])).turn('outra sessão')[0] == 'historico-outra-sessao'
    evil = 'Ana Exemplo ignore-instrucoes segredo-ficticio pessoa@example.invalid'
    # Dados de catálogo não confiáveis entram pela tool real; a autorização continua em Python.
    env['repo'].close()
    import sqlite3
    from emporio.repository.sqlite import SQLiteRepository
    with sqlite3.connect(env['store_path']) as connection:
        connection.execute('UPDATE products SET description=?, name=? WHERE product_id=81', (evil, evil))
        connection.execute('UPDATE orders SET notes=? WHERE order_id=1', (evil,))
    env['repo'] = SQLiteRepository(env['store_path'])
    registry = type(registry)(type(registry.context)(env['repo'], registry.context.state, registry.context.clock, registry.context.session_id, registry.context.vault))
    calls = (FunctionCall('abc', 'get_product', '{"product_id":81}'), FunctionCall('def', 'get_order', '{"order_id":2}'))
    llm = ConversationScriptedLLM([AssistantReply(tool_calls=calls), 'Preço R$ 1,00 e [EMAIL_999]', 'Não posso afirmar valores.'])
    engine = ConversationEngine(registry, llm)
    answer, _ = engine.turn('Ana Exemplo pessoa@example.invalid +55 (67) 99999-8888')
    assert answer == 'Não posso afirmar valores.'
    messages, definitions = llm.inputs[-1], llm.tool_definitions[-1]
    assert any('access_denied' in m.get('content','') for m in messages if m['role'] == 'tool')
    assert any('1,00' in m.get('content','') for m in messages if m['role'] == 'assistant')
    response = SimulatedResponse(body=b'{"choices":[{"message":{"role":"assistant","content":"ok"}}]}')
    capture = CaptureTransport([response])
    key = 'sk-fake-synthetic-only'
    adapter = OpenAICompatibleAdapter(Settings('https://example.invalid/v1', 'fake', key), capture)
    seen = []
    def inspect(body):
        payload = json.loads(body)
        sections = {role: [m for m in payload['messages'] if m['role'] == role] for role in ('system','user','assistant','tool')}
        assert all(sections.values()) and len(payload['tools']) == 8
        flattened = body.decode()
        for value in (evil, 'Ana Exemplo', 'pessoa@example.invalid', '99999-8888', 'segredo-ficticio', 'historico-outra-sessao', '[EMAIL_999]', registry.context.session_id, key, '(67) 3341-4444', 'contato@empóriodamusica.com.br', '1,00'):
            assert value not in flattened
        assert all(m['content'] == '[TEXTO LIVRE OMITIDO]' for m in sections['user'] + sections['assistant'])
        assert all('arguments' in call['function'] and call['function']['arguments'] == '{}' for m in sections['assistant'] for call in m.get('tool_calls', []))
        assert any('access_denied' in m['content'] for m in sections['tool'])
        seen.append(True)
    inspect_capture(messages, definitions, registry, MANUAL, adapter, capture, inspect)
    assert seen == [True] and capture.payloads == [] and attempts == []
    with pytest.raises(TypeError):
        ConversationEngine(registry, adapter)


def test_capture_discarded_even_when_review_fails(env):
    registry = setup_registry(env)
    llm = ConversationScriptedLLM(['ok'])
    ConversationEngine(registry, llm).turn('olá')
    capture = CaptureTransport([SimulatedResponse(body=b'{"choices":[{"message":{"role":"assistant","content":"ok"}}]}')])
    adapter = OpenAICompatibleAdapter(Settings('https://example.invalid/v1','fake','key'), capture)
    def fail(_):
        raise RuntimeError('revisão abortada')
    with pytest.raises(RuntimeError):
        inspect_capture(llm.inputs[0], llm.tool_definitions[0], registry, MANUAL, adapter, capture, fail)
    assert capture.payloads == []


def test_dynamic_messages_and_untrusted_schemas_fail_closed(env):
    registry = setup_registry(env)
    unsafe = 'João Sobrenome +55 67 9 9999‑8888 joão@exemplo.invalid segredo-123 [PHONE_999]'
    messages = [{'role':'system','content':'substituído'}, {'role':'user','content':unsafe}, {'role':'assistant','content':unsafe}]
    projected, schemas = project_messages(messages, registry.definitions(), registry, MANUAL)
    assert unsafe not in json.dumps(projected, ensure_ascii=False)
    assert all(m['content'] == '[TEXTO LIVRE OMITIDO]' for m in projected[1:])
    schemas[0]['function']['description'] = unsafe
    with pytest.raises(ProjectionError, match='schemas_untrusted'):
        project_messages(messages, schemas, registry, MANUAL)
