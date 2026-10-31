"""Encaminhamento interno sem persistir texto livre recebido do usuário."""
from datetime import datetime
from typing import Callable, Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from emporio.appdb.security_store import SecurityStore, timestamp
from emporio.tools.contracts import ToolError, ToolResult

class EscalationInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    category: Literal['pedido', 'devolucao', 'reclamacao', 'produto', 'outros']
    summary: str = Field(min_length=1, max_length=1000, strict=True)

    @field_validator('summary')
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('Resumo vazio')
        return value


def escalate_to_human(state: SecurityStore, clock: Callable[[], datetime], session_id: str, args: dict) -> ToolResult:
    try:
        request = EscalationInput.model_validate(args)
    except ValidationError:
        return ToolResult(ok=False, error=ToolError(code='invalid_input', message_for_agent='Dados de encaminhamento inválidos.'))
    now = clock()
    if state.session(session_id, now) is None:
        return ToolResult(ok=False, error=ToolError(code='access_denied', message_for_agent='Sessão indisponível.'))
    # Resumo livre não é persistido: nem nomes não cadastrados, nem PII escapam por esse campo.
    with state.connection:
        cursor = state.connection.execute('INSERT INTO tickets(order_id, category, summary_tokenized, created_at) VALUES (NULL,?,?,?)',
                                          (request.category, 'Solicitação encaminhada à equipe.', timestamp(now)))
    return ToolResult(ok=True, data={'ticket_id': cursor.lastrowid, 'ticket_id_type': 'interno', 'response_time': '24 horas úteis'})
