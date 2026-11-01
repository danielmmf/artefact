from decimal import Decimal
import pytest
from emporio.agent.money_validator import evidence_from_filters, evidence_from_result, supported_money, unsupported_amounts
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


MANUAL = frozenset(Decimal(v) for v in (35, 50, 80, 100, 500, 2000))


def test_manual_values_count_only_in_sentences_about_their_topic():
    for text in ['O frete é grátis para pedidos acima de R$ 500,00.', 'Abaixo disso, o frete é R$ 35,00.',
                 'A parcela mínima é de R$ 100,00 de 7x a 12x.', 'De 4x a 6x a parcela mínima é R$ 80,00.',
                 'Pagamento combinado a partir de R$ 2.000,00.', 'Dá para combinar formas de pagamento em compras acima de R$ 2.000,00.']:
        assert supported_money(text, set(), MANUAL), text
    for text in ['O preço do produto é R$ 500,00.', 'Esse violão custa R$ 100,00.', 'O Yamaha sai por R$ 35,00.',
                 'Desconto de R$ 50,00 na compra.', 'O frete custa R$ 100,00.', 'O ukulele custa R$ 2.000,00 no pix.']:
        assert not supported_money(text, set(), MANUAL), text
    assert supported_money('O violão custa R$ 500,00.', {Decimal('500')}, MANUAL)  # com evidência de ferramenta, vale
    assert unsupported_amounts('O preço do produto é R$ 500,00.', set(), MANUAL) == [Decimal('500')]


def test_the_dot_of_a_thousands_separator_does_not_end_the_sentence():
    assert supported_money('O combinado vale a partir de R$ 2.000,00 em compras no cartão e no PIX.', set(), MANUAL)
    assert not supported_money('Fica R$ 1.099,50. O produto é o R$ 500,00.', {Decimal('1099.5')}, MANUAL)


def test_filter_values_count_only_when_the_customer_said_them_this_turn():
    assert evidence_from_filters({'max_price': 1000}, 'Quais violões até R$ 1000?') == {Decimal(1000)}
    assert evidence_from_filters({'min_price': 500, 'max_price': 1000}, 'entre R$ 500 e R$ 1000') == {Decimal(500), Decimal(1000)}
    assert evidence_from_filters({'max_price': 1000}, 'violões até mil reais') == {Decimal(1000)}
    assert evidence_from_filters({'max_price': 17}, 'Quais violões vocês têm?') == set()   # valor inventado pelo modelo
    assert evidence_from_filters({'max_price': 17}, 'Quero ver o pedido 17') == set()      # número solto não é preço
    assert evidence_from_filters({'max_price': 1000}, 'Quero algo barato') == set()
