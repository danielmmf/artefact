from dataclasses import dataclass

@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict

class ScriptedLLM:
    """Simulador determinístico para testes; não é um adaptador de LLM real."""
    def __init__(self, product_id: int):
        self.product_id = product_id

    def call(self, message: str) -> ToolCall:
        return ToolCall('get_product', {'product_id': self.product_id})

    def respond(self, result: dict) -> str:
        if not result['ok']:
            return result['error']['message_for_agent']
        data = result['data']
        return f"{data['name']}: R$ {data['price']} (estoque: {data['stock_quantity']})."

class ConversationScriptedLLM:
    """Sequência fixa para testar o registry; nunca contata serviço externo."""
    def __init__(self, script: list[ToolCall | str]):
        self._script = iter(script)
        self.inputs: list[list[dict]] = []

    def complete(self, messages: list[dict]) -> ToolCall | str:
        from copy import deepcopy
        self.inputs.append(deepcopy(messages))
        return next(self._script)

@dataclass(frozen=True)
class FunctionCall:
    call_id: str
    name: str
    arguments_json: str

@dataclass(frozen=True)
class AssistantReply:
    content: str | None = None
    tool_calls: tuple[FunctionCall, ...] = ()
