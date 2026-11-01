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
from emporio.llm import openai_compat
from emporio.llm.openai_compat import AdapterError, CaptureTransport, HttpTransport, OpenAICompatibleAdapter, SimulatedResponse
from emporio.llm.scripted import AssistantReply
from test_integration_offline import setup_registry
from test_order_security import env


def reply(message):
    return SimulatedResponse(body=json.dumps({'choices': [{'message': message}]}).encode())


def setup_adapter(responses):
    transport = CaptureTransport(responses)
    settings = Settings('https://example.invalid/v1', 'modelo-teste', 'segredo-super-privado')
    slept = []
    adapter = OpenAICompatibleAdapter(settings, transport, sleep=slept.append)
    adapter.slept = slept
    return adapter, transport


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
    assert body == {'model': 'modelo-teste', 'messages': messages, 'tools': tools, 'temperature': 0, 'max_tokens': 2048}
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
    (SimulatedResponse(status=401, body=b'segredo-super-privado'), 'http_error'),
    (SimulatedResponse(body=b'not json segredo-super-privado'), 'invalid_response'),
    (reply({'role': 'assistant', 'content': None}), 'invalid_response'),
    (reply({'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'x', 'type': 'function', 'function': {'name': 'tool', 'arguments': '[]'}}]}), 'invalid_response'),
    (reply({'role': 'user', 'content': 'x'}), 'invalid_response'),
])
def test_errors_are_structured_and_never_log_secret(response, code, caplog):
    adapter, _ = setup_adapter([response] * 3)
    with caplog.at_level(logging.DEBUG), pytest.raises(AdapterError) as error:
        adapter.complete([{'role': 'user', 'content': 'contato-privado@example.invalid'}])
    assert error.value.code == code and str(error.value) == code
    assert 'segredo-super-privado' not in caplog.text and 'contato-privado@example.invalid' not in caplog.text


def test_simulated_transport_never_touches_network_even_with_environment(env, monkeypatch):
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
        OpenAICompatibleAdapter(Settings.from_env(), object())
    entries = iter(['1', '2', 'sair'])
    assert chat_offline(Path.cwd(), clock=lambda: datetime.fromisoformat('2026-03-25T10:00:00-04:00'), read=lambda _: next(entries), write=lambda _: None) == 0
    assert attempts == []


def test_reject_invalid_requests_and_configuration_without_details():
    adapter, capture = setup_adapter([])
    with pytest.raises(AdapterError, match='invalid_request'):
        adapter.complete([{'role': 'injected', 'content': 'pessoa@example.invalid'}])
    assert capture.payloads == []
    with pytest.raises(AdapterError, match='invalid_config'):
        OpenAICompatibleAdapter(Settings('https://user:secret@example.invalid', 'model', 'key'), CaptureTransport([]))


def test_payload_for_gpt_oss_uses_low_reasoning_effort_and_roomy_max_tokens():
    transport = CaptureTransport([reply({'role': 'assistant', 'content': 'ok'})])
    adapter = OpenAICompatibleAdapter(Settings('https://example.invalid/v1', 'openai/gpt-oss-120b', 'k'), transport)
    adapter.complete([{'role': 'user', 'content': 'oi'}])
    body = json.loads(transport.payloads[0])
    assert body['reasoning_effort'] == 'low' and body['temperature'] == 0 and body['max_tokens'] >= 2048


def test_retries_429_and_5xx_with_backoff_then_succeeds():
    adapter, transport = setup_adapter([SimulatedResponse(status=429), SimulatedResponse(status=503), reply({'role': 'assistant', 'content': 'ok'})])
    assert adapter.complete([{'role': 'user', 'content': 'oi'}]).content == 'ok'
    assert len(transport.payloads) == 3 and adapter.slept == [1.0, 3.0]


def test_retries_are_bounded_and_failure_carries_status_only():
    adapter, transport = setup_adapter([SimulatedResponse(status=429, body=b'segredo-super-privado')] * 3)
    with pytest.raises(AdapterError) as error:
        adapter.complete([{'role': 'user', 'content': 'oi'}])
    assert (error.value.code, error.value.status, str(error.value)) == ('http_error', 429, 'http_error')
    assert len(transport.payloads) == 3  # 1 tentativa + 2 retries


def test_rate_limit_hint_from_provider_is_honored_up_to_the_cap():
    hint = b'{"error":{"message":"Rate limit reached ... Please try again in 46.065s. Need more tokens?"}}'
    adapter, _ = setup_adapter([SimulatedResponse(status=429, body=hint), SimulatedResponse(status=429, body=b'try again in 3m10s'),
                                reply({'role': 'assistant', 'content': 'ok'})])
    assert adapter.complete([{'role': 'user', 'content': 'oi'}]).content == 'ok'
    assert adapter.slept == [46.065, openai_compat.MAX_WAIT_SECONDS]


def test_client_errors_are_not_retried():
    adapter, transport = setup_adapter([SimulatedResponse(status=400, body=b'{}')])
    with pytest.raises(AdapterError) as error:
        adapter.complete([{'role': 'user', 'content': 'oi'}])
    assert error.value.status == 400 and len(transport.payloads) == 1 and adapter.slept == []


def test_timeouts_are_retried_and_reported():
    adapter, transport = setup_adapter([SimulatedResponse(timeout=True)] * 3)
    with pytest.raises(AdapterError) as error:
        adapter.complete([{'role': 'user', 'content': 'oi'}])
    assert error.value.code == 'timeout' and len(transport.payloads) == 3


def test_empty_content_without_tool_calls_is_invalid():
    adapter, _ = setup_adapter([reply({'role': 'assistant', 'content': '  '})])
    with pytest.raises(AdapterError, match='invalid_response'):
        adapter.complete([{'role': 'user', 'content': 'oi'}])


def test_http_transport_posts_json_with_bearer_to_a_real_server():
    """HTTP real em loopback: cabeçalhos, corpo, retentativa em 429 e resposta parseada."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers['Content-Length'])
            seen.append((self.path, self.headers['Authorization'], self.headers['Content-Type'], self.headers['User-Agent'], json.loads(self.rfile.read(length))))
            first = len(seen) == 1
            body = (b'{"error":{"message":"try again in 0.01s"}}' if first else
                    json.dumps({'choices': [{'message': {'role': 'assistant', 'content': 'olá do servidor'}}]}).encode())
            self.send_response(429 if first else 200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        settings = Settings(f'http://127.0.0.1:{server.server_port}/v1', 'openai/gpt-oss-120b', 'chave-teste')
        adapter = OpenAICompatibleAdapter(settings, HttpTransport(), sleep=lambda _: None)
        assert adapter.complete([{'role': 'user', 'content': 'oi'}]).content == 'olá do servidor'
    finally:
        server.shutdown()
        server.server_close()
    assert len(seen) == 2
    path, auth, ctype, agent, payload = seen[-1]
    assert (path, auth, ctype) == ('/v1/chat/completions', 'Bearer chave-teste', 'application/json')
    assert agent.startswith('emporio-agent') and payload['reasoning_effort'] == 'low' and payload['messages'][0]['content'] == 'oi'


def test_http_transport_maps_connection_failure_without_details():
    settings = Settings('http://127.0.0.1:1/v1', 'modelo', 'chave-secreta')
    adapter = OpenAICompatibleAdapter(settings, HttpTransport(), sleep=lambda _: None)
    with pytest.raises(AdapterError) as error:
        adapter.complete([{'role': 'user', 'content': 'oi'}])
    assert error.value.code == 'transport_error' and 'chave-secreta' not in str(error.value)
