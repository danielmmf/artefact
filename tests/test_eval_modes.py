"""`make eval` não falha por meta não atingida; `make eval-strict` falha; falha de execução falha nos dois."""
import json
from pathlib import Path

import pytest

from emporio.eval_runner import EXIT_INFRA, EXIT_NO_CONFIG, EXIT_OK, EXIT_TARGETS_MISSED, main
from emporio.llm.openai_compat import AdapterError
from emporio.llm.scripted import AssistantReply
from test_real_path import FakeProviderLLM

ROOT = Path(__file__).resolve().parents[1]
# golden-09 exige verify_order_ownership; responder sem a ferramenta deixa a meta de ferramentas em 0%.
MISSES_TARGET = ['--only', 'golden-09']
MEETS_TARGETS = ['--only', 'golden-12']


def run(args, llm, tmp_path, *extra):
    return main([*args, '--reports-dir', str(tmp_path), *extra], llm=llm)


def report(tmp_path):
    (path,) = sorted(tmp_path.glob('golden-*.json'))
    return json.loads(path.read_text(encoding='utf-8'))


def asks_for_contact():
    return FakeProviderLLM([AssistantReply(content='Preciso do e-mail ou telefone do pedido; a confirmação é demonstrativa, não autenticação real.')])


def scope_answer():
    return FakeProviderLLM([AssistantReply(content='Trabalhamos exclusivamente com instrumentos musicais; cabos e outros acessórios não vendemos.')])


def test_default_mode_exits_zero_even_when_a_target_is_missed_and_reports_it(tmp_path, capsys):
    assert run(MISSES_TARGET, asks_for_contact(), tmp_path) == EXIT_OK
    data = report(tmp_path)
    assert data['summary']['met']['tool_accuracy'] is False and data['run']['strict'] is False
    out = capsys.readouterr().out
    assert 'NÃO atingida' in out and 'make eval-strict' in out


def test_strict_mode_exits_one_when_a_target_is_missed_and_still_writes_the_report(tmp_path, capsys):
    assert run(MISSES_TARGET, asks_for_contact(), tmp_path, '--strict') == EXIT_TARGETS_MISSED == 1
    data = report(tmp_path)
    assert data['summary']['met']['tool_accuracy'] is False and data['run']['strict'] is True
    assert 'Modo --strict' in capsys.readouterr().out


@pytest.mark.parametrize('extra', [(), ('--strict',)])
def test_both_modes_exit_zero_when_every_target_is_met(tmp_path, extra):
    assert run(MEETS_TARGETS, scope_answer(), tmp_path, *extra) == EXIT_OK
    assert all(report(tmp_path)['summary']['met'].values())


@pytest.mark.parametrize('extra', [(), ('--strict',)])
def test_provider_failure_is_a_real_execution_failure_in_both_modes(tmp_path, capsys, extra):
    class Down:
        model = 'fake'
        def complete(self, messages, tools=None):
            raise AdapterError('http_error', 429)
    assert run(MEETS_TARGETS, Down(), tmp_path, *extra) == EXIT_INFRA == 3
    assert 'FALHA DE INFRAESTRUTURA' in capsys.readouterr().out
    assert report(tmp_path)['results'][0]['errors'][0]['code'] == 'http_error'     # o relatório fica gravado


@pytest.mark.parametrize('extra', [(), ('--strict',)])
def test_missing_configuration_is_an_error_in_both_modes(monkeypatch, capsys, extra):
    for name in ('LLM_BASE_URL', 'LLM_MODEL', 'LLM_API_KEY'):
        monkeypatch.setenv(name, '')
    assert main(list(extra)) == EXIT_NO_CONFIG == 2
    assert 'Configure' in capsys.readouterr().out


def test_an_unhandled_exception_propagates_so_the_process_exits_with_error(tmp_path):
    class Boom:
        model = 'fake'
        def complete(self, messages, tools=None):
            raise KeyboardInterrupt   # não é Exception: o motor não o captura e a execução aborta
    with pytest.raises(KeyboardInterrupt):
        run(MEETS_TARGETS, Boom(), tmp_path)


def test_makefile_targets_are_eval_without_strict_and_eval_strict_with_it():
    lines = (ROOT / 'Makefile').read_text(encoding='utf-8').splitlines()
    def recipe(target):
        i = lines.index(f'{target}:')
        return lines[i + 1].strip()
    assert recipe('eval').endswith('emporio.eval_runner') and '--strict' not in recipe('eval')
    assert recipe('eval-strict').endswith('emporio.eval_runner --strict')
    assert any(l.startswith('.PHONY') and 'eval-strict' in l for l in lines)
