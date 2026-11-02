"""LLM SIMULADO do lab: sem rede, com latência artificial e respostas fundamentadas nos resultados das ferramentas.

Não mede qualidade de linguagem: serve para carregar o motor (ferramentas, SQLite, validador, histórico) sob carga
com o custo do LLM fixado em um valor conhecido."""
import json
import re
import time
from decimal import Decimal


def brl(value) -> str:
    text = f'{Decimal(str(value)):,.2f}'
    return text.replace(',', 'X').replace('.', ',').replace('X', '.')


class SimulatedLLM:
    model = 'simulado'

    def __init__(self, latency_ms: int):
        self.latency = latency_ms / 1000
        self.calls = 0
        self.busy_seconds = 0.0          # tempo gasto "dentro do LLM" (a latência artificial), para separar a sobrecarga local

    def complete(self, messages, tools=None):
        started = time.perf_counter()
        time.sleep(self.latency)
        self.calls += 1
        try:
            return self._reply(messages)
        finally:
            self.busy_seconds += time.perf_counter() - started

    # --- decisão -----------------------------------------------------------------------------------------
    def _reply(self, messages):
        from emporio.llm.scripted import AssistantReply, FunctionCall
        last = messages[-1]
        if last['role'] == 'tool':
            return AssistantReply(content=self._compose(messages, last))
        text = last['content']
        call_id = f'call_{self.calls}'
        if text.startswith('Reescreva'):
            return AssistantReply(content='Desculpe, não consegui confirmar esse valor agora.')
        if re.search(r'hor[áa]rio|aberta|abrem|fecham', text, re.IGNORECASE):
            return AssistantReply(tool_calls=(FunctionCall(call_id, 'store_status', '{}'),))
        match = re.search(r'Quanto custa o (.+)\?$', text)
        if match:
            return AssistantReply(tool_calls=(FunctionCall(call_id, 'get_product', json.dumps({'name': match.group(1)}, ensure_ascii=False)),))
        match = re.search(r'Quais (\w+) vocês têm', text)
        if match:
            return AssistantReply(tool_calls=(FunctionCall(call_id, 'search_products', json.dumps({'category': match.group(1), 'limit': 20}, ensure_ascii=False)),))
        return AssistantReply(content='Posso ajudar com preços, estoque e horário de instrumentos musicais. O que você procura?')

    # --- resposta fundamentada -----------------------------------------------------------------------------
    @staticmethod
    def _tool_name(messages, tool_message) -> str:
        for message in reversed(messages):
            for call in message.get('tool_calls') or []:
                if call['id'] == tool_message.get('tool_call_id'):
                    return call['function']['name']
        return '?'

    def _compose(self, messages, tool_message) -> str:
        result = json.loads(tool_message['content'])
        name = self._tool_name(messages, tool_message)
        if not result.get('ok'):
            return 'Não consegui identificar esse item com certeza; pode me dar o nome completo?'
        data = result['data']
        if name == 'get_product':
            return f"O {data['name']} custa R$ {brl(data['price_info']['final_price'])} e temos {data['stock_quantity']} unidades em estoque."
        if name == 'search_products':
            shown = '; '.join(f"{p['name']} (R$ {brl(p['price_info']['final_price'])})" for p in data['products'][:3])
            return f"Encontrei {data['total_matches']} produtos. Por exemplo: {shown}." if shown else 'Não encontrei produtos com esse filtro.'
        if name == 'store_status':
            return 'Agora a loja está aberta.' if data.get('is_open') else 'Agora a loja está fechada.'
        return 'Pronto.'
