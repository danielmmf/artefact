"""Motor de chamadas offline; a ativação de provedores externos está bloqueada."""
import json
import re
from pathlib import Path
from emporio.agent.prompt import build_system_prompt
from emporio.agent.money_validator import evidence_from_result, supported_money
from emporio.agent.history import load_history, save_turn, trim_history
from emporio.agent.offline import TOKEN
from emporio.agent.privacy import PrivacyError, protect_dynamic
from emporio.llm.scripted import AssistantReply, ConversationScriptedLLM
from emporio.tools.registry import ToolRegistry

SAFE = 'Não foi possível concluir o atendimento. Tente novamente ou fale com a equipe.'

class ConversationEngine:
    def __init__(self, registry: ToolRegistry, llm: ConversationScriptedLLM, trace: Path | None = None):
        if type(llm) is not ConversationScriptedLLM:
            raise TypeError('Somente o simulador offline está habilitado.')
        self.registry = registry
        self.llm = llm
        self.trace = trace

    def turn(self, message: str, system_prompt: str | None = None) -> tuple[str, list[dict]]:
        vault = self.registry.context.vault
        if system_prompt is None:
            system_prompt = build_system_prompt(Path('data/processed/policies.md'))
        try:
            sanitized_message = protect_dynamic(message, vault)
        except PrivacyError:
            return SAFE, []
        context = self.registry.context
        if context.state.session(context.session_id, context.clock()) is None:
            return SAFE, []
        try:
            history = load_history(context.state, context.session_id)
            history = [{'user':protect_dynamic(t['user'], vault), 'assistant':protect_dynamic(t['assistant'], vault)} for t in history]
        except (ValueError, PrivacyError):
            return SAFE, []
        tools = self.registry.definitions()
        system = {'role':'system', 'content':system_prompt}
        current = [{'role':'user', 'content':sanitized_message}]
        messages = []
        allowed = {x['function']['name'] for x in tools}
        events = []
        def finish(text, visible):
            finished_at = context.clock()
            if context.state.session(context.session_id, finished_at) is None:
                return SAFE, visible
            save_turn(context.state, context.session_id, finished_at, sanitized_message, text)
            if self.trace is not None:
                self.trace.parent.mkdir(parents=True, exist_ok=True)
                with self.trace.open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps({'tool_calls':events}, ensure_ascii=False) + '\n')
            return text, visible
        evidence = set()
        regenerated = False
        for iteration in range(5):
            messages = trim_history(system, history, current, tools)
            if messages is None:
                return SAFE, []
            try:
                reply = self.llm.complete(messages, tools=tools)
            except Exception:
                return SAFE, messages
            if isinstance(reply, str):
                try:
                    text = TOKEN.sub('[CONTATO PROTEGIDO]', protect_dynamic(reply, vault))
                except PrivacyError:
                    return SAFE, messages
                if supported_money(text, evidence):
                    return finish(text, messages)
                if regenerated:
                    return SAFE, messages
                regenerated = True
                current.append({'role':'assistant', 'content':text})
                current.append({'role':'user', 'content':'Reformule sem valores monetários não fundamentados nas ferramentas deste turno.'})
                continue
            if not isinstance(reply, AssistantReply):
                return SAFE, messages
            if not reply.tool_calls:
                try:
                    text = TOKEN.sub('[CONTATO PROTEGIDO]', protect_dynamic(reply.content or '', vault))
                except PrivacyError:
                    return SAFE, messages
                if supported_money(text, evidence):
                    return finish(text, messages)
                if regenerated:
                    return SAFE, messages
                regenerated = True
                current.append({'role':'assistant', 'content':text})
                current.append({'role':'user', 'content':'Reformule sem valores monetários não fundamentados nas ferramentas deste turno.'})
                continue
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
                event = {'tool':name, 'ok':result.ok, 'error':result.error.code if result.error else None}
                if name == 'search_products' and result.ok:
                    event['search_backend'] = result.data['search_backend']
                events.append(event)
                if result.ok:
                    evidence.update(evidence_from_result(result.model_dump(mode='json')['data']))
                try:
                    data = protect_dynamic(result.model_dump(mode='json'), vault)
                except PrivacyError:
                    return SAFE, messages
                results.append({'role':'tool', 'tool_call_id':call_id, 'content':json.dumps(data, ensure_ascii=False)})
            try:
                assistant_content = protect_dynamic(reply.content or '', vault)
            except PrivacyError:
                return SAFE, messages
            current.append({'role':'assistant', 'content':assistant_content, 'tool_calls':normalized})
            current.extend(results)
        return SAFE, messages
