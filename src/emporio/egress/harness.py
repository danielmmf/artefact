"""Revisão sintética em memória; jamais habilita o adaptador no agente."""
from emporio.egress.candidate import project_messages
from emporio.llm.openai_compat import CaptureTransport, OpenAICompatibleAdapter


def inspect_capture(messages, definitions, registry, manual_path, adapter, transport, inspect):
    if type(adapter) is not OpenAICompatibleAdapter or type(transport) is not CaptureTransport or adapter._transport is not transport:
        raise TypeError('Somente transporte simulado é aceito')
    try:
        projected, tools = project_messages(messages, definitions, registry, manual_path)
        adapter.complete(projected, tools)
        if len(transport.payloads) != 1:
            raise ValueError('captura inválida')
        # Callback apenas para revisão local; não deve persistir o conteúdo.
        inspect(transport.payloads[0])
    finally:
        transport.clear()
