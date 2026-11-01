"""Adaptador OpenAI-compatible: chat/completions com function calling.

Transporte HTTP pela biblioteca padrão (urllib), sem dependência adicional.
Segredos, corpos de requisição e corpos de resposta nunca entram em exceções
nem em logs; o chamador recebe apenas um código estruturado (e o status HTTP).
"""
import json
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from emporio.config import Settings
from emporio.llm.scripted import AssistantReply, FunctionCall

MAX_TOKENS = 2048  # o raciocínio de modelos como gpt-oss consome do mesmo orçamento; provedores contam isso no limite por minuto
RETRIES = 2
BACKOFF_SECONDS = (1.0, 3.0)
MAX_WAIT_SECONDS = 70.0  # teto da espera sugerida pelo provedor (limite de tokens por minuto)
HINT = re.compile(r'try again in (?:(\d+)m)?(?:([\d.]+)(ms|s))?', re.IGNORECASE)
USER_AGENT = 'emporio-agent/0.1'


class AdapterError(Exception):
    """Erro estruturado sem mensagens, corpos ou detalhes do provedor."""
    def __init__(self, code: str, status: int | None = None):
        self.code = code
        self.status = status
        super().__init__(code)


@dataclass(frozen=True)
class TransportResponse:
    status: int = 200
    body: bytes = field(default=b'{}', repr=False)
    timeout: bool = False


SimulatedResponse = TransportResponse  # nome usado pelos testes com transporte simulado


class HttpTransport:
    """POST real via urllib; falhas viram AdapterError sem detalhes remotos."""
    def post(self, url: str, headers: dict[str, str], body: bytes, timeout: float) -> TransportResponse:
        request = urllib.request.Request(url, data=body, method='POST',
                                         headers={**headers, 'User-Agent': USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return TransportResponse(status=response.status, body=response.read())
        except urllib.error.HTTPError as error:
            try:
                return TransportResponse(status=error.code, body=error.read())
            finally:
                error.close()
        except (TimeoutError, socket.timeout):
            raise AdapterError('timeout') from None
        except urllib.error.URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise AdapterError('timeout') from None
            raise AdapterError('transport_error') from None
        except OSError:
            raise AdapterError('transport_error') from None


class CaptureTransport:
    """Transporte de teste: sem HTTP; entrega respostas prontas e guarda os corpos."""
    def __init__(self, responses: list[TransportResponse]):
        if any(type(response) is not TransportResponse for response in responses):
            raise TypeError('Respostas simuladas inválidas')
        self._responses = iter(responses)
        self.payloads: list[bytes] = []

    def post(self, url: str, headers: dict[str, str], body: bytes, timeout: float) -> TransportResponse:
        self.payloads.append(body)
        try:
            response = next(self._responses)
        except StopIteration:
            raise AdapterError('transport_unavailable') from None
        if response.timeout:
            raise AdapterError('timeout')
        return response

    def clear(self) -> None:
        self.payloads.clear()


def _retry_hint(body: bytes) -> float | None:
    """Espera sugerida pelo provedor no corpo do 429 (ex.: 'try again in 46.065s'); None se ausente."""
    match = HINT.search(body[:2000].decode('utf-8', 'replace'))
    if not match or not (match.group(1) or match.group(2)):
        return None
    seconds = int(match.group(1) or 0) * 60
    if match.group(2):
        seconds += float(match.group(2)) / (1000 if match.group(3).lower() == 'ms' else 1)
    return seconds


def _text(value):
    if not isinstance(value, str):
        raise ValueError('invalid string')
    return value


def _function_call(value):
    if not isinstance(value, dict) or value.get('type') != 'function':
        raise ValueError('invalid function call')
    function = value['function']
    if not isinstance(function, dict):
        raise ValueError('invalid function')
    return {'id': _text(value['id']), 'type': 'function',
            'function': {'name': _text(function['name']), 'arguments': _text(function['arguments'])}}


def _message(value):
    if not isinstance(value, dict) or value.get('role') not in {'system', 'user', 'assistant', 'tool'}:
        raise ValueError('invalid message')
    role = value['role']
    content = value.get('content')
    if content is not None:
        content = _text(content)
    if role != 'assistant' and content is None:
        raise ValueError('missing content')
    result = {'role': role, 'content': content}
    if role == 'tool':
        result['tool_call_id'] = _text(value['tool_call_id'])
    if role == 'assistant' and 'tool_calls' in value:
        calls = value['tool_calls']
        if not isinstance(calls, list) or not calls:
            raise ValueError('invalid calls')
        result['tool_calls'] = [_function_call(call) for call in calls]
        if content == '':
            result['content'] = None
    if role == 'assistant' and content is None and 'tool_calls' not in result:
        raise ValueError('missing assistant content')
    return result


def _tool(value):
    if not isinstance(value, dict) or value.get('type') != 'function':
        raise ValueError('invalid tool')
    fn = value['function']
    if not isinstance(fn, dict) or not isinstance(fn.get('parameters'), dict):
        raise ValueError('invalid tool function')
    return {'type': 'function', 'function': {'name': _text(fn['name']),
            'description': _text(fn['description']), 'parameters': fn['parameters']}}


class OpenAICompatibleAdapter:
    """Cliente de chat/completions; `transport` é injetável para testes."""
    def __init__(self, settings: Settings, transport=None, *, timeout: float = 60.0, sleep=time.sleep):
        if type(settings) is not Settings:
            raise TypeError('Somente configuração confiável é aceita.')
        transport = HttpTransport() if transport is None else transport
        if not callable(getattr(transport, 'post', None)):
            raise TypeError('Transporte inválido.')
        try:
            if not all(isinstance(value, str) and value for value in (settings.llm_base_url, settings.llm_model, settings.llm_api_key)):
                raise ValueError('invalid configuration')
            base = urlsplit(settings.llm_base_url)
            if (base.scheme not in {'http', 'https'} or not base.hostname or base.username or base.password
                    or base.query or base.fragment or not settings.llm_model or not settings.llm_api_key
                    or any(c in settings.llm_api_key for c in '\r\n')
                    or isinstance(timeout, bool) or not 0 < timeout <= 120):
                raise ValueError('invalid configuration')
        except (TypeError, ValueError):
            raise AdapterError('invalid_config') from None
        self._settings = settings
        self._transport = transport
        self._url = settings.llm_base_url.rstrip('/') + '/chat/completions'
        self._timeout = timeout
        self._sleep = sleep
        self.model = settings.llm_model

    def _send(self, body: bytes) -> TransportResponse:
        headers = {'Authorization': 'Bearer ' + self._settings.llm_api_key, 'Content-Type': 'application/json'}
        last: AdapterError | None = None
        wait = 0.0
        for attempt in range(RETRIES + 1):
            if attempt:
                self._sleep(max(BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)], wait))
            wait = 0.0
            try:
                response = self._transport.post(self._url, headers, body, self._timeout)
            except AdapterError as error:
                if error.code not in {'timeout', 'transport_error'}:
                    raise
                last = error
                continue
            except Exception:
                raise AdapterError('transport_error') from None
            if not isinstance(response, TransportResponse) or not isinstance(response.status, int):
                raise AdapterError('invalid_response')
            if 200 <= response.status < 300:
                return response
            retryable = response.status == 429 or response.status >= 500 or (
                response.status == 400 and b'tool_use_failed' in response.body)
            last = AdapterError('http_error', response.status)
            if not retryable:
                raise last
            wait = min(_retry_hint(response.body) or 0.0, MAX_WAIT_SECONDS)
        raise last

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> AssistantReply:
        try:
            if not isinstance(messages, list) or not messages:
                raise ValueError('invalid messages')
            payload = {'model': self._settings.llm_model, 'messages': [_message(m) for m in messages],
                       'temperature': 0, 'max_tokens': MAX_TOKENS}
            if 'gpt-oss' in self._settings.llm_model.lower():
                payload['reasoning_effort'] = 'low'
            if tools:
                if not isinstance(tools, list):
                    raise ValueError('invalid tools')
                payload['tools'] = [_tool(t) for t in tools]
            elif tools is not None and not isinstance(tools, list):
                raise ValueError('invalid tools')
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
        except (TypeError, ValueError, KeyError, RecursionError):
            raise AdapterError('invalid_request') from None
        response = self._send(body)
        try:
            data = json.loads(response.body)
            choices = data['choices']
            if not isinstance(choices, list) or not choices:
                raise ValueError('missing choices')
            message = choices[0]['message']
            if not isinstance(message, dict) or message.get('role') != 'assistant':
                raise ValueError('invalid role')
            content = message.get('content')
            if content is not None:
                content = _text(content)
            raw_calls = message.get('tool_calls', [])
            if not isinstance(raw_calls, list):
                raise ValueError('invalid calls')
            calls = []
            ids = set()
            for raw in raw_calls:
                call = _function_call(raw)
                parsed = json.loads(call['function']['arguments'])
                if not isinstance(parsed, dict) or not call['id'] or not call['function']['name'] or call['id'] in ids:
                    raise ValueError('invalid call')
                ids.add(call['id'])
                calls.append(FunctionCall(call['id'], call['function']['name'], call['function']['arguments']))
            if not (content or '').strip() and not calls:
                raise ValueError('empty response')
            return AssistantReply(content=content, tool_calls=tuple(calls))
        except (ValueError, TypeError, KeyError, IndexError, UnicodeDecodeError, RecursionError):
            raise AdapterError('invalid_response') from None
