import csv
import json
from concurrent.futures import ThreadPoolExecutor
from emporio.agent.loop import ConversationEngine, SAFE
from emporio.agent.trace import TurnTracer
from emporio.ingest.pipeline import locate
from emporio.llm.scripted import AssistantReply, ConversationScriptedLLM, FunctionCall
from test_integration_offline import setup_registry
from test_order_security import env, RAW


def test_trace_schema_redaction_and_failure(env, tmp_path):
    path = tmp_path / 'trace.jsonl'
    registry = setup_registry(env)
    llm = ConversationScriptedLLM([AssistantReply(tool_calls=(FunctionCall('x', 'search_products', '{"query":"violão"}'),)), 'Pronto'])
    engine = ConversationEngine(registry, llm, path)
    assert engine.turn('contato privado pessoa@example.invalid')[0] == 'Pronto'
    assert engine.turn('outro')[0] == SAFE
    first, second = [json.loads(x) for x in path.read_text().splitlines()]
    assert set(first) == {'session_hash', 'turn', 'turn_id', 'iterations', 'tool_calls', 'llm', 'search_backend', 'validator', 'budget', 'auth', 'errors'}
    assert first['turn'] == 1 and second['turn'] == 2 and first['turn_id'] != second['turn_id']
    assert first['session_hash'] == second['session_hash'] and registry.context.session_id not in path.read_text()
    assert first['iterations'] == 2 and first['llm']['calls'] == 2 and first['llm']['latency_ms'] >= 0 and first['llm']['tokens'] is None
    assert first['tool_calls'][0]['arguments'] == '[REDACTED]' and first['tool_calls'][0]['latency_ms'] >= 0
    assert first['search_backend'] in {'sqlite_filters', 'sqlite_fts5_bm25', 'rapidfuzz'}
    assert second['errors'] == [{'code': 'simulator_error'}]
    assert 'pessoa@example.invalid' not in path.read_text() and 'violão' not in path.read_text()
    with locate(RAW, 'customers').open(encoding='utf-8-sig') as stream:
        for customer in csv.DictReader(stream):
            for field in ('email', 'phone'):
                assert not customer[field] or customer[field] not in path.read_text()


def test_trace_concurrent_writes_and_unlinkable_instances(tmp_path):
    path = tmp_path / 'trace.jsonl'
    tracers = [TurnTracer('session-test', path) for _ in range(80)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda tracer: tracer.write(tracer.new()), tracers))
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 80 and len({r['turn_id'] for r in rows}) == 80
    assert len({r['session_hash'] for r in rows}) == 80


def test_trace_iteration_limit(env, tmp_path):
    path = tmp_path / 'trace.jsonl'
    call = AssistantReply(tool_calls=(FunctionCall('x', 'store_status', '{}'),))
    assert ConversationEngine(setup_registry(env), ConversationScriptedLLM([call] * 5), path).turn('oi')[0] == SAFE
    record = json.loads(path.read_text())
    assert record['iterations'] == 5 and record['errors'] == [{'code': 'iteration_limit'}] and record['validator']['fallback']


def test_trace_write_failure_does_not_expose_error_or_break_turn(env, monkeypatch, capsys):
    def fail_write(record):
        raise OSError('pessoa@example.invalid')
    engine = ConversationEngine(setup_registry(env), ConversationScriptedLLM(['Resposta segura']))
    monkeypatch.setattr(engine._tracer, 'write', fail_write)
    assert engine.turn('Olá')[0] == 'Resposta segura'
    assert 'pessoa@example.invalid' not in str(capsys.readouterr())


def test_free_text_tool_arguments_never_enter_trace(env, tmp_path):
    path = tmp_path / 'trace.jsonl'
    call = FunctionCall('a', 'escalate_to_human', '{"category":"outros","summary":"pessoa@example.invalid texto livre privado"}')
    llm = ConversationScriptedLLM([AssistantReply(tool_calls=(call,)), 'Concluído'])
    answer, _ = ConversationEngine(setup_registry(env), llm, path).turn('Olá')
    assert answer == 'Concluído'
    trace = path.read_text()
    assert 'pessoa@example.invalid' not in trace and 'texto livre privado' not in trace
    assert json.loads(trace)['tool_calls'][0]['arguments'] == '[REDACTED]'
