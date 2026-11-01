from datetime import datetime
from pathlib import Path

from emporio.llm.scripted import AssistantReply, FunctionCall
from emporio.record import record
from test_real_path import FakeProviderLLM

ROOT = Path(__file__).resolve().parents[1]
NOW = '2026-03-25T10:00:00-04:00'


def test_recorded_markdown_declares_real_run_tokenizes_contacts_and_lists_tools(tmp_path):
    llm = FakeProviderLLM([AssistantReply(tool_calls=(FunctionCall('c1', 'store_status', '{}'),)),
                           AssistantReply(content='Estamos abertos agora.'),
                           AssistantReply(content='Anotei seu contato.')])
    text = record(ROOT, ['A loja está aberta?', 'Meu e-mail é lucas.mendes@jmail.com e (67) 99812-3456'],
                  title='Teste', customer=None, now=NOW, llm=llm, trace=tmp_path / 't.jsonl')
    assert text.startswith('# Teste') and 'Conversa real' in text and NOW in text and 'demonstrativa' in text
    assert '**Cliente:** A loja está aberta?' in text and '_Ferramentas consultadas: `store_status` (ok)_' in text
    assert '**Atendente:** Estamos abertos agora.' in text
    assert '[EMAIL_1]' in text and '[PHONE_1]' in text
    assert 'lucas.mendes@jmail.com' not in text and '99812-3456' not in text
    assert datetime.fromisoformat(NOW).isoformat() in text
