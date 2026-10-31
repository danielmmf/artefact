"""Autorização e confirmação demonstrativa de posse; não representa login real."""
from datetime import datetime
from typing import Callable
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from emporio.appdb.security_store import SecurityStore
from emporio.repository.base import StoreRepository
from emporio.security.contacts import ContactVault
from emporio.tools.contracts import ToolError, ToolResult

class OrderInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    order_id: int = Field(gt=0, le=2**63-1, strict=True)

class VerifyInput(OrderInput):
    contact_ref: str = Field(min_length=1, max_length=30, strict=True)

class OrderAccess:
    def __init__(self, store: StoreRepository, state: SecurityStore, clock: Callable[[], datetime]):
        self.store, self.state, self.clock = store, state, clock

    def verify_order_ownership(self, session_id: str, vault: ContactVault, args: dict) -> ToolResult:
        try:
            request = VerifyInput.model_validate(args)
        except ValidationError:
            return ToolResult(ok=False, error=ToolError(code='invalid_input', message_for_agent='Dados de verificação inválidos.'))
        contact = vault.resolve(request.contact_ref) if vault.session_id == session_id else None
        valid = contact is not None and self.store.verify_order_contact(request.order_id, contact)
        state = self.state.record_verification(session_id, request.order_id, self.clock(), valid)
        if state == 'granted':
            return ToolResult(ok=True, data={'granted': True, 'valid_for_minutes': 15, 'verification': 'demonstrativa'})
        if state == 'locked':
            return ToolResult(ok=False, error=ToolError(code='locked', message_for_agent='Verificação bloqueada; encaminhe à equipe.'))
        return ToolResult(ok=False, error=ToolError(code='not_verified', message_for_agent='Não foi possível confirmar a posse.'))

    def get_order(self, session_id: str, args: dict) -> ToolResult:
        try:
            request = OrderInput.model_validate(args)
        except ValidationError:
            return ToolResult(ok=False, error=ToolError(code='invalid_input', message_for_agent='Pedido inválido.'))
        current = self.clock()
        session = self.state.session(session_id, current)
        authorized = False
        if session is not None:
            if session['mode'] == 'simulated_authenticated':
                owner = self.store.order_customer_id(request.order_id)
                authorized = owner is not None and owner == session['customer_id']
            else:
                authorized = not self.state.locked(request.order_id) and self.state.has_grant(session_id, request.order_id, current)
        if not authorized:
            return ToolResult(ok=False, error=ToolError(code='access_denied', message_for_agent='Acesso ao pedido não autorizado.'))
        details = self.store.order_details(request.order_id)
        if details is None:
            return ToolResult(ok=False, error=ToolError(code='access_denied', message_for_agent='Acesso ao pedido não autorizado.'))
        return ToolResult(ok=True, data=details)
