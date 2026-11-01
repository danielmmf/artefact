"""Protocolo OpenAI-compatible em preparação; somente transporte simulado.

A captura em memória pode conter dados pessoais e instruções. O chamador é
responsável por mantê-la em ambiente controlado e descartá-la após revisão.
Nenhuma sanitização ou aprovação de payload é implícita neste módulo.
"""
import json
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from emporio.config import Settings
from emporio.llm.scripted import AssistantReply, FunctionCall


class AdapterError(Exception):
    """Erro estruturado sem mensagens, corpos ou detalhes do provedor."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SimulatedResponse:
    status: int = 200
    body: bytes = field(default=b'{}', repr=False)
    timeout: bool = False


class CaptureTransport:
    """Transporte deliberadamente sem HTTP; captura somente o corpo em memória."""
    def __init__(self, responses: list[SimulatedResponse]):
        if any(type(response) is not SimulatedResponse for response in responses):
            raise TypeError('Respostas simuladas inválidas')
        self._responses = iter(responses)
        self.payloads: list[bytes] = []

    def post(self, url: str, headers: dict[str, str], body: bytes, timeout: float) -> SimulatedResponse:
        # Nenhum endpoint, credencial, header ou erro remoto é registrado.
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
    """Mapeamento de protocolo inativo: nenhum transporte real é aceito."""
    def __init__(self, settings: Settings, transport: CaptureTransport, *, timeout: float = 30.0):
        if type(settings) is not Settings or type(transport) is not CaptureTransport:
            raise TypeError('Somente configuração confiável e transporte simulado são aceitos.')
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

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> AssistantReply:
        try:
            if not isinstance(messages, list) or not messages:
                raise ValueError('invalid messages')
            payload = {'model': self._settings.llm_model, 'messages': [_message(m) for m in messages]}
            if tools:
                if not isinstance(tools, list):
                    raise ValueError('invalid tools')
                payload['tools'] = [_tool(t) for t in tools]
            elif tools is not None and not isinstance(tools, list):
                raise ValueError('invalid tools')
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
        except (TypeError, ValueError, KeyError, RecursionError):
            raise AdapterError('invalid_request') from None
        try:
            response = self._transport.post(self._url, {'Authorization': 'Bearer ' + self._settings.llm_api_key,
                                            'Content-Type': 'application/json'}, body, self._timeout)
        except AdapterError:
            raise
        except Exception:
            raise AdapterError('transport_error') from None
        if type(response) is not SimulatedResponse or not isinstance(response.status, int):
            raise AdapterError('invalid_response')
        if not 200 <= response.status < 300:
            raise AdapterError('http_error')
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
            if content is None and not calls:
                raise ValueError('empty response')
            return AssistantReply(content=content, tool_calls=tuple(calls))
        except (ValueError, TypeError, KeyError, IndexError, UnicodeDecodeError, RecursionError):
            raise AdapterError('invalid_response') from None
