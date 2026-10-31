"""Registro de tools; identidade e dependências só vêm do contexto do canal."""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable
from pydantic import BaseModel, ConfigDict, ValidationError
from emporio.appdb.security_store import SecurityStore
from emporio.repository.base import StoreRepository
from emporio.security.access import OrderAccess, OrderInput, ReturnInput, VerifyInput
from emporio.security.contacts import ContactVault
from emporio.tools.contracts import ToolError, ToolResult
from emporio.tools.escalation import EscalationInput, escalate_to_human
from emporio.tools.product import GetProductInput, get_product
from emporio.tools.quote_payment import QuotePaymentInput, quote_payment
from emporio.tools.search import SearchInput, search_products
from emporio.tools.store_status import store_status

class EmptyInput(BaseModel):
    model_config = ConfigDict(extra='forbid')

@dataclass(frozen=True)
class ToolContext:
    repository: StoreRepository
    state: SecurityStore
    clock: Callable[[], datetime]
    session_id: str
    vault: ContactVault

    def __post_init__(self):
        if self.vault.session_id != self.session_id:
            raise ValueError('Cofre e sessão incompatíveis')

class ToolRegistry:
    def __init__(self, context: ToolContext):
        self.context = context
        access = OrderAccess(context.repository, context.state, context.clock)
        self._tools = {
            'search_products': (SearchInput, lambda args: search_products(context.repository, args)),
            'get_product': (GetProductInput, lambda args: get_product(context.repository, args)),
            'quote_payment': (QuotePaymentInput, lambda args: quote_payment(context.repository, args)),
            'store_status': (EmptyInput, lambda args: store_status(context.clock)),
            'verify_order_ownership': (VerifyInput, lambda args: access.verify_order_ownership(context.session_id, context.vault, args)),
            'get_order': (OrderInput, lambda args: access.get_order(context.session_id, args)),
            'check_return_eligibility': (ReturnInput, lambda args: access.check_return_eligibility(context.session_id, args)),
            'escalate_to_human': (EscalationInput, lambda args: escalate_to_human(context.state, context.clock, context.session_id, args)),
        }

    def definitions(self) -> list[dict]:
        return [{'type':'function', 'function':{'name': name, 'description': f'Executa {name}.', 'parameters': schema.model_json_schema()}}
                for name, (schema, _) in self._tools.items()]

    def dispatch(self, name: str, args: dict) -> ToolResult:
        entry = self._tools.get(name) if isinstance(name, str) else None
        if entry is None:
            return ToolResult(ok=False, error=ToolError(code='invalid_input', message_for_agent='Ferramenta desconhecida.'))
        schema, function = entry
        try:
            parsed = schema.model_validate(args)
        except ValidationError:
            return ToolResult(ok=False, error=ToolError(code='invalid_input', message_for_agent='Argumentos inválidos.'))
        try:
            return function(parsed.model_dump(mode='json', exclude_unset=True))
        except Exception as exc:
            # Apenas classe e nome conhecido: mensagens e argumentos podem conter PII.
            logging.getLogger(__name__).error('Falha interna em %s (%s)', name, type(exc).__name__)
            return ToolResult(ok=False, error=ToolError(code='internal_error', message_for_agent='Não foi possível executar a ferramenta.'))
