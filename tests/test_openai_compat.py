import json
import logging
import socket
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from emporio.agent.loop import ConversationEngine
from emporio.config import Settings
from emporio.cli import chat_offline
from emporio.eval_gate import main as eval_main
from emporio.llm.openai_compat import AdapterError, CaptureTransport, OpenAICompatibleAdapter, SimulatedResponse
from emporio.llm.scripted import AssistantReply
from test_integration_offline import setup_registry
from test_order_security import env


def reply(message):
    return SimulatedResponse(body=json.dumps({'choices': [{'message': message}]}).encode())


def setup_adapter(responses):
    transport = CaptureTransport(responses)
    settings = Settings('https://example.invalid/v1', 'modelo-teste', 'segredo-super-privado')
    return OpenAICompatibleAdapter(settings, transport), transport


def test_serialized_capture_contains_roles_tools_and_no_header():
    adapter, capture = setup_adapter([reply({'role': 'assistant', 'content': 'Pronto'})])
    messages = [{'role': 'system', 'content': 'manual privado'}, {'role': 'user', 'content': 'olá'},
                {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'c1', 'type': 'function', 'function': {'name': 'store_status', 'arguments': '{}'}}]},
                {'role': 'tool', 'tool_call_id': 'c1', 'content': '{"ok":true}'},
                {'role': 'assistant', 'content': 'histórico'}]
    tools = [{'type': 'function', 'function': {'name': 'store_status', 'description': 'Horário', 'parameters': {'type': 'object', 'properties': {}}}}]
    result = adapter.complete(messages, tools)
    body = json.loads(capture.payloads[0])
    assert result == AssistantReply(content='Pronto')
    assert body == {'model': 'modelo-teste', 'messages': messages, 'tools': tools}
    assert b'segredo-super-privado' not in capture.payloads[0]
    capture.clear()
    assert capture.payloads == []


def test_multiple_function_calls_return_existing_contract():
    calls = [{'id': key, 'type': 'function', 'function': {'name': name, 'arguments': args}} for key, name, args in [('a', 'get_product', '{"product_id":90}'), ('b', 'store_status', '{}')]]
    adapter, _ = setup_adapter([reply({'role': 'assistant', 'content': None, 'tool_calls': calls})])
    result = adapter.complete([{'role': 'user', 'content': 'olá'}])
    assert [(c.call_id, c.name, json.loads(c.arguments_json)) for c in result.tool_calls] == [('a', 'get_product', {'product_id': 90}), ('b', 'store_status', {})]


@pytest.mark.parametrize(('response', 'code'), [
    (SimulatedResponse(timeout=True), 'timeout'),
    (SimulatedResponse(status=429, body=b'segredo-super-privado'), 'http_error'),
    (SimulatedResponse(body=b'not json segredo-super-privado'), 'invalid_response'),
    (reply({'role': 'assistant', 'content': None}), 'invalid_response'),
    (reply({'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'x', 'type': 'function', 'function': {'name': 'tool', 'arguments': '[]'}}]}), 'invalid_response'),
    (reply({'role': 'user', 'content': 'x'}), 'invalid_response'),
])
def test_errors_are_structured_and_never_log_secret(response, code, caplog):
    adapter, _ = setup_adapter([response])
    with caplog.at_level(logging.DEBUG), pytest.raises(AdapterError) as error:
        adapter.complete([{'role': 'user', 'content': 'contato-privado@example.invalid'}])
    assert error.value.code == code and str(error.value) == code
    assert 'segredo-super-privado' not in caplog.text and 'contato-privado@example.invalid' not in caplog.text


def test_no_external_transport_or_network_even_with_environment(env, monkeypatch):
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append(True)
        raise AssertionError('rede')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)
    monkeypatch.setattr(socket.socket, 'sendto', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setenv('LLM_BASE_URL', 'https://example.invalid/v1')
    monkeypatch.setenv('LLM_MODEL', 'modelo')
    monkeypatch.setenv('LLM_API_KEY', 'chave')
    adapter, _ = setup_adapter([reply({'role': 'assistant', 'content': 'Olá'})])
    assert adapter.complete([{'role': 'user', 'content': 'oi'}]).content == 'Olá'
    with pytest.raises(TypeError):
        ConversationEngine(setup_registry(env), adapter)
    with pytest.raises(TypeError):
        OpenAICompatibleAdapter(Settings.from_env(), object())
    entries = iter(['1', '2', 'sair'])
    assert chat_offline(Path.cwd(), clock=lambda: datetime.fromisoformat('2026-03-25T10:00:00-04:00'), read=lambda _: next(entries), write=lambda _: None) == 0
    assert eval_main() == 1
    assert attempts == []


def test_reject_invalid_requests_and_configuration_without_details():
    adapter, capture = setup_adapter([])
    with pytest.raises(AdapterError, match='invalid_request'):
        adapter.complete([{'role': 'injected', 'content': 'pessoa@example.invalid'}])
    assert capture.payloads == []
    with pytest.raises(AdapterError, match='invalid_config'):
        OpenAICompatibleAdapter(Settings('https://user:secret@example.invalid', 'model', 'key'), CaptureTransport([]))
