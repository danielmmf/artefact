"""Segunda arquitetura do lab: o mesmo atendimento orquestrado nativamente pelo PydanticAI.

Orquestração do framework: `Agent`, `FunctionToolset` com ferramentas tipadas, `deps` injetadas (`RunContext`),
`output_validator` + `ModelRetry` (revalidação de valores em reais), `UsageLimits` (limite de iterações) e a
capacidade `ProcessHistory` (orçamento de contexto). O ConversationEngine NÃO é usado aqui.

Camada compartilhada, importada sem alteração: ToolRegistry (domínio, autorização, contratos), cofre de contatos,
`protect_dynamic`, validador monetário, histórico em SQLite, orçamento (`trim_history`), prompt e trace.
O que o framework não traz e precisou de cola local está marcado com `# COLA:`.
"""
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from time import perf_counter_ns
from typing import Annotated, Any

from pydantic import Field
from pydantic_ai import Agent, ModelRetry, RunContext, UsageLimits
from pydantic_ai.capabilities import ProcessHistory
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import (ModelMessage, ModelRequest, ModelResponse, RetryPromptPart, SystemPromptPart, TextPart,
                                  ToolCallPart, ToolReturnPart, UserPromptPart)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.toolsets import FunctionToolset

from emporio.agent.history import estimated_tokens, load_history, save_turn, trim_history
from emporio.agent.loop import SAFE
from emporio.agent.money_validator import (CLAIM, CONTEXT, evidence_from_filters, evidence_from_manual, evidence_from_result,
                                           parse_amount, supported_money)
from emporio.agent.offline import TOKEN
from emporio.agent.privacy import PrivacyError, protect_dynamic
from emporio.agent.prompt import build_system_prompt
from emporio.agent.trace import TurnTracer
from emporio.llm.scripted import AssistantReply
from emporio.tools.registry import DESCRIPTIONS, ToolRegistry

POLICIES = Path('data/processed/policies.md')       # mesmo caminho relativo que o ConversationEngine usa
MAX_ITERATIONS = 5                                  # mesmo limite do loop próprio
REWRITE = ('Reescreva a resposta ao cliente, em tom de conversa, usando como valores em reais apenas os das ferramentas deste turno ou do manual. '
           'Se um valor não veio das ferramentas deste turno (mesmo que tenha aparecido antes na conversa), chame a ferramenta (get_product, '
           'search_products ou quote_payment) antes de citá-lo; não calcule você mesmo nem cite diferenças ou somas de valores. Não copie dados técnicos.')
SESSION_NOTE = ('\n\nSESSÃO: o canal já identificou o cliente (identidade simulada). Não peça e-mail, telefone nem confirmação de posse; '
                'get_order e check_return_eligibility funcionam para os pedidos dele.')


class BudgetExceeded(Exception):
    pass


@dataclass
class Deps:
    """Dependências injetadas em cada execução: tudo o que as ferramentas e validadores precisam, sem globais."""
    registry: ToolRegistry
    record: dict
    system_prompt: str
    sanitized_message: str
    history_turns: list[dict]
    manual: frozenset
    evidence: set[Decimal] = field(default_factory=set)


# --- ferramentas tipadas -------------------------------------------------------------------------------------------
toolset: FunctionToolset[Deps] = FunctionToolset()


async def _call(ctx: RunContext[Deps], tool: str, /, **args: Any) -> str:
    """Todas as ferramentas passam pelo mesmo ToolRegistry.dispatch do loop próprio; aqui só entra o que é do framework."""
    deps, vault = ctx.deps, ctx.deps.registry.context.vault
    args = {key: value for key, value in args.items() if value is not None}      # COLA: o registry distingue "não informado" de None
    started = perf_counter_ns()
    protect_dynamic(args, vault)    # PrivacyError aborta o turno, como no loop próprio
    if tool == 'search_products':
        deps.evidence.update(evidence_from_filters(args, deps.sanitized_message))
    result = deps.registry.dispatch(tool, args)
    # COLA: o trace por turno (evento da ferramenta, eventos de autorização, backend de busca) é escrito à mão, como no loop próprio
    code = result.error.code if result.error and result.error.code in {'invalid_input', 'not_found', 'ambiguous', 'access_denied', 'not_verified', 'locked', 'internal_error'} else None
    event = {'tool': tool, 'arguments': '[REDACTED]', 'status': 'ok' if result.ok else 'error', 'ok': result.ok, 'error': code,
             'latency_ms': (perf_counter_ns() - started) / 1_000_000}
    if tool in {'get_order', 'check_return_eligibility', 'verify_order_ownership'}:
        deps.record['auth']['events'].append({'tool': tool, 'status': 'allowed' if result.ok else 'denied'})
    if tool == 'search_products' and result.ok and result.data['search_backend'] in {'sqlite_filters', 'sqlite_fts5_bm25', 'rapidfuzz'}:
        event['search_backend'] = deps.record['search_backend'] = result.data['search_backend']
    deps.record['tool_calls'].append(event)
    payload = result.model_dump(mode='json')
    if result.ok:
        deps.evidence.update(evidence_from_result(payload['data']))
    return json.dumps(protect_dynamic(payload, vault), ensure_ascii=False)       # COLA: o resultado da ferramenta também passa pela barreira de privacidade


@toolset.tool(description=DESCRIPTIONS['search_products'])
async def search_products(
        ctx: RunContext[Deps], query: Annotated[str | None, Field(max_length=200)] = None,
        category: Annotated[str | None, Field(description='Categoria do catálogo: Guitarras, Baixos, Baterias e Percussão, Teclados e Pianos, Violões, Ukuleles (singular ou plural). Omita se não tiver certeza.')] = None,
        min_price: Decimal | None = None, max_price: Decimal | None = None, only_available: bool | None = None,
        limit: Annotated[int | None, Field(description='Quantos produtos devolver (1 a 20). Em perguntas de listagem ("quais violões até R$ 1000?") use 20 para mostrar todos; total_matches informa quantos existem.')] = None) -> str:
    return await _call(ctx, 'search_products', query=query, category=category, min_price=min_price, max_price=max_price,
                       only_available=only_available, limit=limit)


@toolset.tool(description=DESCRIPTIONS['get_product'])
async def get_product(ctx: RunContext[Deps], product_id: int | None = None, name: str | None = None) -> str:
    return await _call(ctx, 'get_product', product_id=product_id, name=name)


@toolset.tool(description=DESCRIPTIONS['quote_payment'])
async def quote_payment(ctx: RunContext[Deps], items: list[dict[str, int]], destination_city: str | None = None) -> str:
    return await _call(ctx, 'quote_payment', items=items, destination_city=destination_city)


@toolset.tool(description=DESCRIPTIONS['store_status'])
async def store_status(ctx: RunContext[Deps]) -> str:
    return await _call(ctx, 'store_status')


@toolset.tool(description=DESCRIPTIONS['verify_order_ownership'])
async def verify_order_ownership(ctx: RunContext[Deps], order_id: int, contact_ref: str) -> str:
    return await _call(ctx, 'verify_order_ownership', order_id=order_id, contact_ref=contact_ref)


@toolset.tool(description=DESCRIPTIONS['get_order'])
async def get_order(ctx: RunContext[Deps], order_id: int) -> str:
    return await _call(ctx, 'get_order', order_id=order_id)


@toolset.tool(description=DESCRIPTIONS['check_return_eligibility'])
async def check_return_eligibility(ctx: RunContext[Deps], order_id: int, reason: str, received_at: date | None = None,
                                   purchase_channel: str | None = None) -> str:
    return await _call(ctx, 'check_return_eligibility', order_id=order_id, reason=reason, received_at=received_at,
                       purchase_channel=purchase_channel)


@toolset.tool(description=DESCRIPTIONS['escalate_to_human'])
async def escalate_to_human(ctx: RunContext[Deps], category: str, summary: str) -> str:
    return await _call(ctx, 'escalate_to_human', category=category, summary=summary)


# --- orçamento de contexto -----------------------------------------------------------------------------------------
def tool_definitions() -> list[dict]:
    """As ferramentas como o framework as expõe ao modelo (esquemas gerados pelo PydanticAI, não pelo registry)."""
    return [{'type': 'function', 'function': {'name': name, 'description': tool.tool_def.description, 'parameters': tool.tool_def.parameters_json_schema}}
            for name, tool in toolset.tools.items()]


def fit_budget(ctx: RunContext[Deps], messages: list[ModelMessage]) -> list[ModelMessage]:
    """Processador de histórico: aplica o MESMO `trim_history` do loop próprio e corta os turnos mais antigos."""
    deps = ctx.deps
    keep_from = 2 * len(deps.history_turns)                       # COLA: o framework não separa "histórico" de "turno atual"
    current = to_wire(messages[keep_from:])
    current = [m for m in current if m['role'] != 'system']
    fitted = trim_history({'role': 'system', 'content': deps.system_prompt}, deps.history_turns, current, tool_definitions())
    if fitted is None:
        raise BudgetExceeded()
    kept = (len(fitted) - len(current) - 1) // 2
    deps.record['budget']['history_turns_truncated'] = max(deps.record['budget']['history_turns_truncated'], len(deps.history_turns) - kept)
    return messages[2 * (len(deps.history_turns) - kept):]


# --- agente --------------------------------------------------------------------------------------------------------
agent: Agent[Deps, str] = Agent(
    deps_type=Deps, output_type=str, toolsets=[toolset], retries={'tools': 1, 'output': 1},
    capabilities=[ProcessHistory(fit_budget)])


@agent.instructions
def system_instructions(ctx: RunContext[Deps]) -> str:
    return ctx.deps.system_prompt


@agent.output_validator
async def grounded_money(ctx: RunContext[Deps], text: str) -> str:
    """Resposta final: contatos protegidos e valores em reais só se vierem das ferramentas deste turno ou do manual."""
    deps = ctx.deps
    text = TOKEN.sub('[CONTATO PROTEGIDO]', protect_dynamic(text, deps.registry.context.vault))   # COLA: privacidade da resposta final
    validator = deps.record['validator']
    if supported_money(text, deps.evidence, deps.manual):
        validator['approved'] += 1
        claims = [parse_amount(m.group('prefix') or m.group('suffix')) for m in CLAIM.finditer(text)]
        claims += [parse_amount(m.group('amount')) for m in CONTEXT.finditer(CLAIM.sub('', text))]
        validator['approved_values_brl'] = sorted({str(v) for v in claims if v in deps.evidence})
        return text
    validator['rejected'] += 1
    validator['regenerations'] += 1
    raise ModelRetry(REWRITE)


# >>> PONTE: existe só porque o lab simula o LLM com o protocolo `complete(messages, tools)` do loop próprio. Com um modelo real
# do PydanticAI (OpenAIChatModel etc.) nada disto seria escrito; o `to_wire` também serve a `fit_budget`, que reaproveita `trim_history`.
def to_wire(messages: list[ModelMessage]) -> list[dict]:
    """Mensagens do framework no formato `{role, content, tool_calls}` do protocolo `complete` (o que o LLM simulado entende)."""
    wire: list[dict] = []
    instructions = next((m.instructions for m in reversed(messages) if isinstance(m, ModelRequest) and m.instructions), None)
    if instructions:
        wire.append({'role': 'system', 'content': instructions})
    for message in messages:
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, SystemPromptPart):
                    wire.append({'role': 'system', 'content': part.content})
                elif isinstance(part, UserPromptPart):
                    wire.append({'role': 'user', 'content': part.content if isinstance(part.content, str) else str(part.content)})
                elif isinstance(part, ToolReturnPart):
                    wire.append({'role': 'tool', 'tool_call_id': part.tool_call_id, 'content': part.model_response_str()})
                elif isinstance(part, RetryPromptPart):
                    if part.tool_name:
                        wire.append({'role': 'tool', 'tool_call_id': part.tool_call_id, 'content': part.model_response()})
                    else:
                        wire.append({'role': 'user', 'content': part.model_response()})
        else:
            text = ''.join(p.content for p in message.parts if isinstance(p, TextPart))
            calls = [{'id': p.tool_call_id, 'type': 'function', 'function': {'name': p.tool_name, 'arguments': p.args_as_json_str()}}
                     for p in message.parts if isinstance(p, ToolCallPart)]
            wire.append({'role': 'assistant', 'content': text, **({'tool_calls': calls} if calls else {})})
    return wire


def protocol_model(llm, record: dict) -> FunctionModel:
    """Modelo do framework que delega a decisão ao MESMO objeto `complete(messages, tools)` usado pelo loop próprio."""
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        wire, tools = to_wire(messages), tool_definitions()
        record['budget']['estimated_tokens'] = estimated_tokens(wire, tools)      # o que o framework de fato envia
        record['iterations'] += 1
        started = perf_counter_ns()
        try:
            reply = llm.complete(wire, tools=tools)
        finally:
            record['llm']['latency_ms'] = (record['llm']['latency_ms'] or 0) + (perf_counter_ns() - started) / 1_000_000
            record['llm']['calls'] += 1
        if isinstance(reply, str):
            return ModelResponse(parts=[TextPart(reply)])
        if not isinstance(reply, AssistantReply):
            raise TypeError('invalid_llm_reply')
        parts: list[Any] = [TextPart(reply.content)] if reply.content else []
        parts += [ToolCallPart(call.name, call.arguments_json, tool_call_id=call.call_id) for call in reply.tool_calls]
        return ModelResponse(parts=parts or [TextPart('')])
    return FunctionModel(respond, model_name=str(getattr(llm, 'model', type(llm).__name__)))
# <<< PONTE


class PydanticAIAgent:
    """Mesma interface do ConversationEngine: `turn(message) -> (resposta, mensagens)`; histórico lógico no mesmo SQLite."""

    def __init__(self, registry: ToolRegistry, llm, trace: Path | None = None):
        if not callable(getattr(llm, 'complete', None)):
            raise TypeError('O LLM deve implementar complete(messages, tools).')
        self.registry, self.llm, self.trace = registry, llm, trace
        self._tracer = TurnTracer(registry.context.session_id, trace)

    def turn(self, message: str, system_prompt: str | None = None) -> tuple[str, list[dict]]:
        record = self._tracer.new(str(getattr(self.llm, 'model', type(self.llm).__name__)))
        try:
            answer, messages = self._turn(message, system_prompt, record)
        except Exception as failure:
            answer, messages = SAFE, []
            record['errors'].append(self._error(failure))
        if answer == SAFE:
            record['validator']['fallback'] = True
        try:
            self._tracer.write(record)
        except OSError:
            pass
        return answer, messages

    @staticmethod
    def _error(failure: Exception) -> dict:
        if isinstance(failure, PrivacyError):
            return {'code': 'privacy_blocked'}
        if isinstance(failure, UsageLimitExceeded):
            return {'code': 'iteration_limit'}
        if isinstance(failure, BudgetExceeded):
            return {'code': 'budget_exceeded'}
        if isinstance(failure, UnexpectedModelBehavior):
            return {'code': 'validator_rejected'}
        return {'code': getattr(failure, 'code', None) or 'llm_error'}

    def _turn(self, message: str, system_prompt: str | None, record: dict):
        context = self.registry.context
        vault = context.vault
        trusted = build_system_prompt(POLICIES)
        if system_prompt is not None:                                # COLA: texto do chamador é dado, não instrução
            message = protect_dynamic(system_prompt, vault) + '\n' + message
        sanitized = protect_dynamic(message, vault)                  # COLA: a barreira de privacidade da entrada é nossa
        session = context.state.session(context.session_id, context.clock())
        if session is None:
            record['errors'].append({'code': 'session_invalid'})
            return SAFE, []
        record['auth']['session'] = session['mode']
        if session['mode'] == 'simulated_authenticated':
            trusted += SESSION_NOTE
        try:
            turns = load_history(context.state, context.session_id)
            turns = [{'user': protect_dynamic(t['user'], vault), 'assistant': protect_dynamic(t['assistant'], vault)} for t in turns]
        except ValueError:
            record['errors'].append({'code': 'history_invalid'})
            return SAFE, []
        history: list[ModelMessage] = []
        for turn in turns:
            history += [ModelRequest(parts=[UserPromptPart(turn['user'])]), ModelResponse(parts=[TextPart(turn['assistant'])])]
        deps = Deps(self.registry, record, trusted, sanitized, turns, frozenset(evidence_from_manual(POLICIES.read_text(encoding='utf-8'))))
        try:                                                         # COLA: toda exceção vira a contingência segura
            result = agent.run_sync(sanitized, deps=deps, model=protocol_model(self.llm, record), message_history=history,
                                    usage_limits=UsageLimits(request_limit=MAX_ITERATIONS))
        except Exception as failure:
            record['errors'].append(self._error(failure))
            return SAFE, []
        finished_at = context.clock()                                # COLA: sessão que expirou durante o turno e persistência do histórico
        if context.state.session(context.session_id, finished_at) is None:
            record['errors'].append({'code': 'session_expired'})
            return SAFE, []
        save_turn(context.state, context.session_id, finished_at, sanitized, result.output)
        return result.output, to_wire(result.all_messages())
