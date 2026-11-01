from decimal import Decimal
import pytest
from emporio.agent.money_validator import evidence_from_result, supported_money
from emporio.agent.loop import ConversationEngine, SAFE
from emporio.llm.scripted import AssistantReply, ConversationScriptedLLM, FunctionCall
from test_integration_offline import setup_registry
from test_order_security import env

@pytest.mark.parametrize('text', ['R$ 1.967,18', '1967,18 reais', 'R$ 1967.18', 'preço é 1967,18'])
def test_supported_formats(text):
    assert supported_money(text, {Decimal('1967.18')})
    assert not supported_money(text, {Decimal('1967.19')})

def test_unknown_shipping_and_other_numeric_fields_not_evidence():
    evidence = evidence_from_result({'fee':None, 'stock_quantity':35, 'discount_percent':'18', 'list_price':'100.00', 'amounts':['50.00','50.00']})
    assert supported_money('Parcela R$ 50,00; preço R$ 100,00.', evidence)
    assert not supported_money('Frete R$ 35,00.', evidence)
    assert not supported_money('Desconto R$ 18,00.', evidence)
    assert not supported_money('Custa mil reais.', evidence)
    assert not supported_money('Por apenas 35,00.', evidence)
    assert not supported_money('R $ 35,00', evidence)
    assert not supported_money('BRL 35,00', evidence)
    assert not supported_money('Oferta: 120', evidence)
    assert not supported_money('R$ 1000.000,000', evidence)

def test_single_regeneration_and_safe_fallback(env):
    call = AssistantReply(tool_calls=(FunctionCall('id','get_product','{"product_id":90}'),))
    llm = ConversationScriptedLLM([call, 'R$ 1,00', 'O preço é R$ 1.967,18.'])
    answer, _ = ConversationEngine(setup_registry(env), llm).turn('Quero pagar R$ 1,00')
    assert answer == 'O preço é R$ 1.967,18.' and len(llm.inputs) == 3
    llm = ConversationScriptedLLM([call, 'R$ 1,00', 'R$ 2,00'])
    assert ConversationEngine(setup_registry(env), llm).turn('Quero pagar R$ 1,00')[0] == SAFE
