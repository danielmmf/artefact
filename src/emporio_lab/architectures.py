"""Arquiteturas que o lab sabe executar. Cada uma roda a MESMA carga sob as mesmas condições."""
import json
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from emporio.agent.loop import SAFE, ConversationEngine
from emporio.cli import open_registry
from emporio_lab.pydanticai_agent import PydanticAIAgent
from emporio_lab.simllm import SimulatedLLM
from emporio_lab.synthetic import Turn

FIXED_NOW = datetime.fromisoformat('2026-03-25T10:00:00-04:00')   # relógio fixo do projeto (S-h)


@dataclass
class TurnResult:
    user: int
    index: int
    kind: str
    total_s: float
    llm_s: float
    llm_calls: int
    safe_fallback: bool
    error: str | None = None
    tokens_estimated: int | None = None


class V102:
    """A v1.0.2 como foi entregue: loop próprio, SQLite, validador, histórico e trace, com o LLM trocado pelo simulado."""
    name = 'v1.0.2'
    orchestrator = staticmethod(ConversationEngine)

    def run_user(self, root: Path, turns: list[Turn], latency_ms: int) -> list[TurnResult]:
        results: list[TurnResult] = []
        llm = SimulatedLLM(latency_ms)
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / 'trace.jsonl'
            try:
                with open_registry(root, None, lambda: FIXED_NOW) as registry:
                    engine = self.orchestrator(registry, llm, trace)
                    for turn in turns:
                        busy_before, calls_before = llm.busy_seconds, llm.calls
                        started = time.perf_counter()
                        answer, _ = engine.turn(turn.text)
                        total = time.perf_counter() - started
                        results.append(TurnResult(turn.user, turn.index, turn.kind, total, llm.busy_seconds - busy_before,
                                                  llm.calls - calls_before, answer == SAFE))
            except Exception as error:                     # erro real de execução (por exemplo, banco travado)
                results.append(TurnResult(turns[0].user, len(results), 'erro', 0.0, 0.0, 0, False, error=f'{type(error).__name__}: {error}'))
            records = []
            if trace.exists():
                records = [json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines() if line.strip()]
        done = [r for r in results if r.error is None]
        for result, record in zip(done, records):
            result.tokens_estimated = record['budget']['estimated_tokens']
            if record['errors'] and result.error is None:
                result.error = 'trace:' + ','.join(str(e.get('code')) for e in record['errors'])
        return results


class PydanticAI(V102):
    """Mesma carga, mesmo registry, mesmo LLM simulado e mesmo histórico; a orquestração é do PydanticAI."""
    name = 'pydantic-ai'
    orchestrator = staticmethod(PydanticAIAgent)


ARCHITECTURES = {V102.name: V102, PydanticAI.name: PydanticAI}
