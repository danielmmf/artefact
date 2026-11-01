"""Loop offline limitado; não é o adaptador de produção nem um agente completo."""
import json
import re
from pathlib import Path
from emporio.llm.scripted import ConversationScriptedLLM, ToolCall
from emporio.tools.registry import ToolRegistry

TOKEN = re.compile(r'\[(?:EMAIL|PHONE)_\d+\]')

def protect(value, vault):
    if isinstance(value, str):
        return vault.tokenize(value)
    if isinstance(value, list):
        return [protect(item, vault) for item in value]
    if isinstance(value, dict):
        return {protect(key, vault) if isinstance(key, str) else key: protect(item, vault) for key, item in value.items()}
    return value

def run_offline(message: str, llm: ConversationScriptedLLM, registry: ToolRegistry, trace: Path) -> str:
    if type(llm) is not ConversationScriptedLLM:
        raise TypeError('Este fluxo aceita apenas o simulador offline.')
    vault = registry.context.vault
    messages = [{'role':'user', 'content':vault.tokenize(message)}]
    events = []
    for _ in range(5):
        response = llm.complete(messages)
        if isinstance(response, str):
            # Nunca restaurar tokens de saída arbitrária do modelo.
            safe = TOKEN.sub('[CONTATO PROTEGIDO]', vault.tokenize(response))
            trace.parent.mkdir(parents=True, exist_ok=True)
            with trace.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'tool_calls':events}, ensure_ascii=False) + '\n')
            return safe
        if not isinstance(response, ToolCall):
            raise ValueError('Resposta simulada inválida')
        valid_names = {d['function']['name'] for d in registry.definitions()}
        name = response.name if isinstance(response.name, str) and response.name in valid_names else 'unknown'
        result = registry.dispatch(name, response.arguments)
        data = protect(result.model_dump(mode='json'), vault)
        # A entrada e os resultados são dados não confiáveis, nunca instruções.
        messages.append({'role':'tool', 'name':name, 'content':json.dumps(data, ensure_ascii=False)})
        event = {'tool': name,
                 'ok': result.ok, 'error': result.error.code if result.error else None}
        if name == 'search_products' and result.ok:
            event['search_backend'] = result.data['search_backend']
        events.append(event)
    trace.parent.mkdir(parents=True, exist_ok=True)
    with trace.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'tool_calls':events, 'error':'iteration_limit'}, ensure_ascii=False) + '\n')
    return 'Não foi possível concluir o atendimento.'
