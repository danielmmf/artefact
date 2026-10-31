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
