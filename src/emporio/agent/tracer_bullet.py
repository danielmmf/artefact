import json
from pathlib import Path
from emporio.llm.scripted import ScriptedLLM
from emporio.repository.base import StoreRepository
from emporio.tools.product import get_product

def run(message: str, llm: ScriptedLLM, repository: StoreRepository, trace: Path) -> str:
    call = llm.call(message)
    if call.name != 'get_product':
        raise ValueError('Ferramenta não suportada')
    result = get_product(repository, call.arguments)
    response = llm.respond(result.model_dump(mode='json'))
    # Allowlist: nunca gravar mensagem, argumentos, resposta ou dados do cliente.
    record = {'tool': 'get_product', 'ok': result.ok, 'error': result.error.code if result.error else None}
    trace.parent.mkdir(parents=True, exist_ok=True)
    with trace.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')
    return response
