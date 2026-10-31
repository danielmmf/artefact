import json
import socket
import subprocess
from datetime import datetime
from pathlib import Path

from emporio.agent.loop import ConversationEngine
from emporio.cli import chat_offline
from emporio.eval_gate import main as eval_main
from emporio.llm.scripted import ConversationScriptedLLM
from test_integration_offline import setup_registry
from test_order_security import env


def test_offline_paths_never_attempt_connections_or_subprocesses(env, monkeypatch, capsys):
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append(True)
        raise AssertionError('network or process attempted')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(socket.socket, 'sendto', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    assert ConversationEngine(setup_registry(env), ConversationScriptedLLM(['Olá'])).turn('oi')[0] == 'Olá'
    entries = iter(['1', '2', 'sair'])
    output = []
    assert chat_offline(Path.cwd(), clock=lambda: datetime.fromisoformat('2026-03-25T10:00:00-04:00'), read=lambda _: next(entries), write=output.append) == 0
    assert any('DEMONSTRAÇÃO OFFLINE' in line for line in output)
    assert any('não autenticação real' in line for line in output)
    assert sum('Consulta demonstrativa concluída' in line for line in output) == 2
    assert eval_main() == 1 and 'bloqueado' in capsys.readouterr().out
    assert attempts == []


def test_golden_labels_complete_before_evaluation():
    golden = json.loads(Path('evals/golden_set.json').read_text())
    assert golden['status'] == 'labels_pre_execution' and len(golden['cases']) == 16
    for case in golden['cases']:
        assert set(case) == {'id', 'label', 'input', 'session_context', 'expected_behavior', 'expected_tools', 'prohibitions', 'pass_criteria'}
        assert case['input'] and case['prohibitions'] and case['pass_criteria']
