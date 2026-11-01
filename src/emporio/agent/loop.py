"""Motor de conversa: loop de function calling sobre qualquer LLM do protocolo `complete`."""
import json
import re
import sys
import threading
from time import perf_counter_ns
from pathlib import Path
from emporio.agent.prompt import build_system_prompt
from emporio.agent.money_validator import CLAIM, CONTEXT, parse_amount, evidence_from_filters, evidence_from_manual, evidence_from_result, supported_money
from emporio.agent.history import BUDGET, estimated_tokens, load_history, save_turn, trim_history
from emporio.agent.offline import TOKEN
from emporio.agent.privacy import PrivacyError, protect_dynamic
from emporio.agent.trace import TurnTracer
from emporio.llm.scripted import AssistantReply
from emporio.tools.registry import ToolRegistry

SAFE = 'Não foi possível concluir o atendimento. Tente novamente ou fale com a equipe.'

class ConversationEngine:
    def __init__(self, registry: ToolRegistry, llm, trace: Path | None = None):
        # Protocolo: complete(messages, tools=None) -> str | AssistantReply (ScriptedLLM ou adaptador real).
        if not callable(getattr(llm, 'complete', None)):
            raise TypeError('O LLM deve implementar complete(messages, tools).')
        self.registry = registry
        self.llm = llm
        self.trace = trace
        self._tracer = TurnTracer(registry.context.session_id, trace)
        self._turn_lock = threading.Lock()

    def turn(self, message: str, system_prompt: str | None = None) -> tuple[str, list[dict]]:
        with self._turn_lock:
            record = self._tracer.new(str(getattr(self.llm, 'model', type(self.llm).__name__)))
            try:
                answer, messages = self._turn(message, system_prompt, record)
                if answer == SAFE:
                    record['validator']['fallback'] = True
                return answer, messages
            except Exception:
                record['errors'].append({'code': 'internal_error'})
                record['validator']['fallback'] = True
                return SAFE, []
            finally:
                try:
                    self._tracer.write(record)
                except OSError:
                    # Trace indisponível não expõe exceções ou texto privado.
                    pass

    def _turn(self, message, system_prompt, record):
        vault = self.registry.context.vault
        trusted_prompt = build_system_prompt(Path('data/processed/policies.md'))
        # Um prompt fornecido pelo chamador é dado, nunca uma instrução de sistema.
        if system_prompt is not None:
            try:
                message = protect_dynamic(system_prompt, vault) + '\n' + message
            except PrivacyError:
                return SAFE, []
        system_prompt = trusted_prompt
        try:
            sanitized_message = protect_dynamic(message, vault)
        except PrivacyError:
            record['errors'].append({'code': 'privacy_blocked'})
            return SAFE, []
        context = self.registry.context
        session = context.state.session(context.session_id, context.clock())
        if session is None:
            record['errors'].append({'code': 'session_invalid'})
            return SAFE, []
        record['auth']['session'] = session['mode']
        if session['mode'] == 'simulated_authenticated':
            system_prompt += '\n\nSESSÃO: o canal já identificou o cliente (identidade simulada). Não peça e-mail, telefone nem confirmação de posse; get_order e check_return_eligibility funcionam para os pedidos dele.'
        try:
            history = load_history(context.state, context.session_id)
            history = [{'user':protect_dynamic(t['user'], vault), 'assistant':protect_dynamic(t['assistant'], vault)} for t in history]
        except (ValueError, PrivacyError):
            record['errors'].append({'code': 'history_invalid'})
            return SAFE, []
        tools = self.registry.definitions()
        system = {'role':'system', 'content':system_prompt}
        current = [{'role':'user', 'content':sanitized_message}]
        messages = []
        allowed = {x['function']['name'] for x in tools}
        events = record['tool_calls']
        def finish(text, visible):
            finished_at = context.clock()
            if context.state.session(context.session_id, finished_at) is None:
                record['errors'].append({'code': 'session_expired'})
                return SAFE, visible
            save_turn(context.state, context.session_id, finished_at, sanitized_message, text)
            return text, visible
        evidence = set()
        manual = evidence_from_manual(Path('data/processed/policies.md').read_text(encoding='utf-8'))
        regenerated = False
        for iteration in range(5):
            record['iterations'] = iteration + 1
            messages = trim_history(system, history, current, tools)
            if messages is None:
                record['errors'].append({'code': 'budget_exceeded'})
                return SAFE, []
            record['budget']['estimated_tokens'] = estimated_tokens(messages, tools)
            record['budget']['history_turns_truncated'] = max(record['budget']['history_turns_truncated'], len(history) - (len(messages) - len(current) - 1) // 2)
            started = perf_counter_ns()
            try:
                reply = self.llm.complete(messages, tools=tools)
            except Exception:
                failure = sys.exc_info()[1]
                error = {'code': getattr(failure, 'code', None) or 'llm_error'}
                if getattr(failure, 'status', None) is not None:
                    error['status'] = failure.status
                record['errors'].append(error)
                return SAFE, messages
            finally:
                elapsed = (perf_counter_ns() - started) / 1_000_000
                llm = record['llm']
                llm['latency_ms'] = (llm['latency_ms'] or 0) + elapsed
                llm['calls'] += 1
            if isinstance(reply, str):
                try:
                    text = TOKEN.sub('[CONTATO PROTEGIDO]', protect_dynamic(reply, vault))
                except PrivacyError:
                    return SAFE, messages
                if supported_money(text, evidence, manual):
                    record['validator']['approved'] += 1
                    claims = [parse_amount(m.group('prefix') or m.group('suffix')) for m in CLAIM.finditer(text)]
                    claims += [parse_amount(m.group('amount')) for m in CONTEXT.finditer(CLAIM.sub('', text))]
                    record['validator']['approved_values_brl'] = sorted({str(v) for v in claims if v in evidence})
                    return finish(text, messages)
                record['validator']['rejected'] += 1
                if regenerated:
                    return SAFE, messages
                regenerated = True
                record['validator']['regenerations'] += 1
                current.append({'role':'assistant', 'content':text})
                current.append({'role':'user', 'content':'Reescreva a resposta ao cliente, em tom de conversa, usando como valores em reais apenas os das ferramentas deste turno ou do manual. Se faltar um valor (parcelas, total, desconto, frete), chame quote_payment em vez de calcular. Não copie dados técnicos.'})
                continue
            if not isinstance(reply, AssistantReply):
                record['errors'].append({'code': 'invalid_llm_reply'})
                return SAFE, messages
            if not reply.tool_calls:
                try:
                    text = TOKEN.sub('[CONTATO PROTEGIDO]', protect_dynamic(reply.content or '', vault))
                except PrivacyError:
                    return SAFE, messages
                if supported_money(text, evidence, manual):
                    record['validator']['approved'] += 1
                    claims = [parse_amount(m.group('prefix') or m.group('suffix')) for m in CLAIM.finditer(text)]
                    claims += [parse_amount(m.group('amount')) for m in CONTEXT.finditer(CLAIM.sub('', text))]
                    record['validator']['approved_values_brl'] = sorted({str(v) for v in claims if v in evidence})
                    return finish(text, messages)
                record['validator']['rejected'] += 1
                if regenerated:
                    return SAFE, messages
                regenerated = True
                record['validator']['regenerations'] += 1
                current.append({'role':'assistant', 'content':text})
                current.append({'role':'user', 'content':'Reescreva a resposta ao cliente, em tom de conversa, usando como valores em reais apenas os das ferramentas deste turno ou do manual. Se faltar um valor (parcelas, total, desconto, frete), chame quote_payment em vez de calcular. Não copie dados técnicos.'})
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
                started = perf_counter_ns()
                try:
                    args = json.loads(call.arguments_json)
                    if not isinstance(args, dict):
                        raise ValueError('Argumentos devem ser objeto')
                    safe_args = json.dumps(protect_dynamic(args, vault), ensure_ascii=False)
                    if name == 'search_products':
                        evidence.update(evidence_from_filters(args, sanitized_message))
                    result = self.registry.dispatch(name, args)
                except PrivacyError:
                    return SAFE, messages
                except (ValueError, TypeError):
                    result = self.registry.dispatch(name, None)
                    safe_args = '{}'
                normalized.append({'id': call_id, 'type':'function', 'function':{'name':name, 'arguments':safe_args}})
                code = result.error.code if result.error and result.error.code in {'invalid_input', 'not_found', 'ambiguous', 'access_denied', 'not_verified', 'locked', 'internal_error'} else None
                event = {'tool':name, 'arguments': '[REDACTED]', 'status': 'ok' if result.ok else 'error', 'ok': result.ok, 'error': code, 'latency_ms': (perf_counter_ns() - started) / 1_000_000}
                if name in {'get_order', 'check_return_eligibility', 'verify_order_ownership'}:
                    record['auth']['events'].append({'tool': name, 'status': 'allowed' if result.ok else 'denied'})
                if name == 'search_products' and result.ok:
                    backend = result.data['search_backend']
                    if backend in {'sqlite_filters', 'sqlite_fts5_bm25', 'rapidfuzz'}:
                        event['search_backend'] = backend
                        record['search_backend'] = backend
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
        record['errors'].append({'code': 'iteration_limit'})
        return SAFE, messages
