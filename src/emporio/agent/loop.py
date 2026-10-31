"""Motor de chamadas offline; a ativação de provedores externos está bloqueada."""
import json
import re
from pathlib import Path
from emporio.agent.prompt import build_system_prompt
from emporio.agent.offline import TOKEN
from emporio.agent.privacy import PrivacyError, protect_dynamic
from emporio.llm.scripted import AssistantReply, ConversationScriptedLLM
from emporio.tools.registry import ToolRegistry

SAFE = 'Não foi possível concluir o atendimento. Tente novamente ou fale com a equipe.'

class ConversationEngine:
    def __init__(self, registry: ToolRegistry, llm: ConversationScriptedLLM):
        if type(llm) is not ConversationScriptedLLM:
            raise TypeError('Somente o simulador offline está habilitado.')
        self.registry = registry
        self.llm = llm

    def turn(self, message: str, system_prompt: str | None = None) -> tuple[str, list[dict]]:
        vault = self.registry.context.vault
        if system_prompt is None:
            system_prompt = build_system_prompt(Path('data/processed/policies.md'))
        try:
            sanitized_message = protect_dynamic(message, vault)
        except PrivacyError:
            return SAFE, []
        messages = [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': sanitized_message}]
        allowed = {x['function']['name'] for x in self.registry.definitions()}
        for iteration in range(5):
            try:
                reply = self.llm.complete(messages)
            except Exception:
                return SAFE, messages
            if isinstance(reply, str):
                try:
                    return TOKEN.sub('[CONTATO PROTEGIDO]', protect_dynamic(reply, vault)), messages
                except PrivacyError:
                    return SAFE, messages
            if not isinstance(reply, AssistantReply):
                return SAFE, messages
            if not reply.tool_calls:
                text = reply.content or ''
                try:
                    return TOKEN.sub('[CONTATO PROTEGIDO]', protect_dynamic(text, vault)), messages
                except PrivacyError:
                    return SAFE, messages
            normalized = []
            results = []
            used_ids = set()
            for position, call in enumerate(reply.tool_calls):
                call_id = call.call_id if isinstance(call.call_id, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', call.call_id) and call.call_id not in used_ids else f'call_{iteration}_{position}'
                if vault.tokenize(call_id) != call_id:
                    call_id = f'call_{iteration}_{position}'
                while call_id in used_ids:
                    call_id += '_x'
                used_ids.add(call_id)
                name = call.name if isinstance(call.name, str) and call.name in allowed else 'unknown'
                try:
                    args = json.loads(call.arguments_json)
                    if not isinstance(args, dict):
                        raise ValueError('Argumentos devem ser objeto')
                    safe_args = json.dumps(protect_dynamic(args, vault), ensure_ascii=False)
                    result = self.registry.dispatch(name, args)
                except PrivacyError:
                    return SAFE, messages
                except (ValueError, TypeError):
                    result = self.registry.dispatch(name, None)
                    safe_args = '{}'
                normalized.append({'id': call_id, 'type':'function', 'function':{'name':name, 'arguments':safe_args}})
                try:
                    data = protect_dynamic(result.model_dump(mode='json'), vault)
                except PrivacyError:
                    return SAFE, messages
                results.append({'role':'tool', 'tool_call_id':call_id, 'content':json.dumps(data, ensure_ascii=False)})
            try:
                assistant_content = protect_dynamic(reply.content or '', vault)
            except PrivacyError:
                return SAFE, messages
            messages.append({'role':'assistant', 'content':assistant_content, 'tool_calls':normalized})
            messages.extend(results)
        return SAFE, messages
