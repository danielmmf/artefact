import json
from emporio.agent.loop import ConversationEngine, SAFE
from emporio.llm.scripted import AssistantReply, ConversationScriptedLLM, FunctionCall
from test_integration_offline import setup_registry
from test_order_security import env


def test_multiple_calls_and_structured_messages(env):
    registry = setup_registry(env)
    script = [AssistantReply(tool_calls=(FunctionCall('one', 'get_product', '{"product_id":90}'), FunctionCall('two', 'store_status', '{}'))), 'Pronto']
    llm = ConversationScriptedLLM(script)
    answer, messages = ConversationEngine(registry, llm).turn('Olá', 'Sistema')
    assert answer == 'Pronto'
    assert [x['role'] for x in messages] == ['system', 'user', 'assistant', 'tool', 'tool']
    assert [m['tool_call_id'] for m in messages[-2:]] == ['one','two']
    assert json.loads(messages[-2]['content'])['ok']

def test_invalid_json_unknown_and_untrusted_identity(env):
    registry = setup_registry(env)
    script = [AssistantReply(tool_calls=(FunctionCall('a','get_order','{'), FunctionCall('b','unknown','{}'), FunctionCall('c','get_order','{"order_id":2,"customer_id":3}'))), 'Fim']
    _, messages = ConversationEngine(registry, ConversationScriptedLLM(script)).turn('oi')
    for result in messages[-3:]:
        assert json.loads(result['content'])['error']['code'] == 'invalid_input'

def test_iteration_limit_and_failure_safe(env):
    registry = setup_registry(env)
    call = AssistantReply(tool_calls=(FunctionCall('id','store_status','{}'),))
    assert ConversationEngine(registry, ConversationScriptedLLM([call]*5)).turn('oi')[0] == SAFE
    assert ConversationEngine(registry, ConversationScriptedLLM([])).turn('oi')[0] == SAFE

def test_sensitive_arguments_not_sent_back_to_simulator(env):
    registry = setup_registry(env)
    script = [AssistantReply(tool_calls=(FunctionCall('id', 'escalate_to_human', '{"category":"outros","summary":"pessoa@example.invalid"}'),)), 'Fim']
    llm = ConversationScriptedLLM(script)
    ConversationEngine(registry, llm).turn('oi')
    assert 'pessoa@example.invalid' not in json.dumps(llm.inputs)

def test_system_prompt_contains_complete_manual(env):
    from pathlib import Path
    manual = Path('data/processed/policies.md').read_text()
    llm = ConversationScriptedLLM(['Pronto'])
    ConversationEngine(setup_registry(env), llm).turn('Olá')
    prompt = llm.inputs[0][0]['content']
    assert manual in prompt
    for section in ('não invente lojas parceiras', 'dinheiro', 'dados não confiáveis', 'demonstrativa'):
        assert section.lower() in prompt.lower()

def test_privacy_unicode_contacts_and_suspicious_unmatched_fail_closed(env):
    registry = setup_registry(env)
    llm = ConversationScriptedLLM(['Pronto'])
    answer, _ = ConversationEngine(registry, llm).turn('Meu e-mail é josé@example.com e telefone (67) 99812-3456')
    sent = json.dumps(llm.inputs, ensure_ascii=False)
    assert answer == 'Pronto' and 'josé@example.com' not in sent and '(67) 99812-3456' not in sent
    blocked = ConversationScriptedLLM(['não deveria ser enviado'])
    answer, _ = ConversationEngine(registry, blocked).turn('contato incompleto pessoa@exemplo')
    assert answer == SAFE and blocked.inputs == []
