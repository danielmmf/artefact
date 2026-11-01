# Verificação em checkout isolado

Data: 2026-11-01. Clone independente da branch publicada; commit testado `58ad5acb08bcb7cd3c28b3ea4fba49ba7f03fe06`. Este documento foi adicionado posteriormente: o commit de documentação que o contém não é o commit testado no clone. A CI do PR deve ser consultada para o head mais recente.

Ambiente: Linux, `uv 0.12.13`, Python do ambiente virtual **3.13.15** (o `python3` do shell era 3.14.4). `make setup` usou `uv sync --locked --extra dev`, resolveu 15 pacotes e instalou 14 no ambiente; o cache local estava disponível. A primeira instalação em uma máquina sem cache pode precisar de rede para obter Python ou dependências. `uv lock --check --offline` passou e `git diff --exit-code -- uv.lock` confirmou lockfile inalterado.

Após a instalação, `LLM_API_KEY`, `LLM_MODEL` e `LLM_BASE_URL` foram removidos do ambiente; `UV_OFFLINE=1` foi usado nos comandos abaixo:

| Comando | Resultado |
| --- | --- |
| `make ingest` | Passou; ingestão local concluída. |
| `make test` | **160 testes passaram** em 21,36 s. |
| `make bench` | Passou; recall@5 **0,800**, MRR **0,750** em dez consultas. |
| `git diff --check` | Passou; checkout sem alterações versionadas após os comandos. |
| `uv lock --check --offline` | Passou; 15 pacotes resolvidos. |

Os testes adicionais incluem `tests/test_trace_phase4.py` e `tests/test_offline_phase4.py`: argumentos livres omitidos do trace, falha de escrita sem vazamento, EOF e erro seguro na CLI, e interceptação de sockets/subprocessos nos fluxos exercitados. `tests/test_agent_history.py` cobre expiração durante geração. Esses testes não estabelecem privacidade ou isolamento universais.

Higiene no commit: `git ls-files` não encontrou `.env`, `var/`, `.claude/`, `docs/private/`, caches Python ou arquivos `.db`/`.pyc` versionados; `.env.example` é intencionalmente versionado. `git check-ignore` confirmou os caminhos privados citados e `.venv/`. Varredura de 90 arquivos versionados por padrões selecionados de chaves privadas, AWS, GitHub e OpenAI não encontrou correspondências; ela não prova ausência de todos os formatos de segredo nem examina histórico Git completo. Dados brutos e planejamento não foram alterados.

A CI dos commits anteriores ao relatório passou no PR #4. A aceitação final permanece parcial: não há avaliação de LLM real, conversas reais ou aprovação do gate de privacidade.
