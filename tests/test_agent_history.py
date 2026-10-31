import json
from pathlib import Path
from emporio.agent.history import estimated_tokens, trim_history
from emporio.agent.loop import ConversationEngine, SAFE
from emporio.agent.prompt import build_system_prompt
from emporio.llm.scripted import AssistantReply, ConversationScriptedLLM, FunctionCall
from test_integration_offline import setup_registry
from test_order_security import env


def test_history_continuity_isolation_and_no_contact_on_disk(env):
    first = setup_registry(env)
    llm = ConversationScriptedLLM(['Olá!', 'Tudo bem.'])
    engine = ConversationEngine(first, llm)
    assert engine.turn('Meu e-mail usuario@example.invalid')[0] == 'Olá!'
    assert engine.turn('E agora?')[0] == 'Tudo bem.'
    assert any(m['role']=='assistant' and m['content']=='Olá!' for m in llm.inputs[1])
    assert b'usuario@example.invalid' not in env['app_path'].read_bytes()
    assert 'usuario@example.invalid' not in json.dumps(llm.inputs)
    assert all('[EMAIL_1]' not in m['content'] for m in llm.inputs[1] if isinstance(m.get('content'), str))
    second = ConversationEngine(setup_registry(env), ConversationScriptedLLM(['Oi']))
    _, messages = second.turn('Oi')
    assert not any(m.get('content') == 'Olá!' for m in messages)

def test_budget_removes_history_preserves_manual_and_tools(env):
    registry = setup_registry(env)
    manual = Path('data/processed/policies.md').read_text()
    system = {'role':'system','content':build_system_prompt(Path('data/processed/policies.md'))}
    tools = registry.definitions()
    current = [{'role':'user','content':'Agora'}]
    old = [{'user':'X'*100000, 'assistant':'Y'*100000}, {'user':'recente', 'assistant':'ok'}]
    budget = estimated_tokens([system] + current, tools) + 100
    messages = trim_history(system, old, current, tools, budget)
    assert manual in messages[0]['content']
    assert not any('X'*100 in m['content'] for m in messages)
    assert any(m['content']=='recente' for m in messages)
    assert trim_history(system, [], current, tools, 1) is None
    llm = ConversationScriptedLLM(['OK'])
    ConversationEngine(registry, llm).turn('Olá')
    assert len(llm.tool_definitions[0]) == 8 and manual in llm.inputs[0][0]['content']

def test_trace_has_search_backend_and_no_contact(env, tmp_path):
    registry = setup_registry(env)
    llm = ConversationScriptedLLM([AssistantReply(tool_calls=(FunctionCall('c','search_products','{"query":"Yamaha C40"}'),)), 'Concluído'])
    trace = tmp_path/'trace.jsonl'
    answer, _ = ConversationEngine(registry, llm, trace).turn('Meu contato pessoa@example.invalid')
    assert answer == 'Concluído'
    event = json.loads(trace.read_text())
    assert event['tool_calls'][0]['search_backend'] == 'sqlite_fts5_bm25'
    assert 'pessoa@example.invalid' not in trace.read_text()

def test_history_and_prompts_do_not_persist_official_contacts(env):
    import csv
    from emporio.ingest.pipeline import locate
    from test_order_security import RAW
    with locate(RAW, 'customers').open(encoding='utf-8') as stream:
        customers = list(csv.DictReader(stream))
    registry = setup_registry(env)
    llm = ConversationScriptedLLM(['Combinado'])
    text = f"Contato {customers[0]['email']} ou {customers[0]['phone']}"
    assert ConversationEngine(registry, llm).turn(text)[0] == 'Combinado'
    artifacts = (env['app_path'].read_bytes(), json.dumps(llm.inputs, ensure_ascii=False).encode())
    for customer in customers:
        for key in ('email', 'phone'):
            if customer[key]:
                assert all(customer[key].encode() not in artifact for artifact in artifacts)


def test_session_expiring_during_generation_does_not_persist(env):
    from datetime import timedelta
    from test_order_security import NOW
    registry = setup_registry(env)
    llm = ConversationScriptedLLM(['não usado'])
    def delayed(messages, tools=None):
        env['time'][0] = NOW + timedelta(minutes=15)
        return 'Resposta'
    llm.complete = delayed
    answer, _ = ConversationEngine(registry, llm).turn('Olá')
    assert answer == SAFE
    assert env['state'].connection.execute('SELECT COUNT(*) FROM history').fetchone()[0] == 0
