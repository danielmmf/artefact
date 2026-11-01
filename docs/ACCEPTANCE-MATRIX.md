# Matriz de aceite

Estados: **aprovado** = evidência (teste, execução real ou relatório) suficiente para o escopo explicitado; **parcial** = evidência incompleta ou limitação conhecida; **pendente** = ainda não executado. Nenhuma linha aprova produção. Atualizada em 2026-11-01 após a integração no `main` (PR #5).

| ID | Estado | Evidência concreta | Risco / limitação e pendência para Claude |
| --- | --- | --- | --- |
| FND-01 | aprovado | Makefile; pyproject.toml; uv.lock; `make setup/ingest/test/bench` sem chave | A instalação precisa de rede na primeira vez; `make chat` e `make eval` exigem o `.env`. |
| FND-02 | aprovado | .github/workflows/ci.yml; CI verde no PR #5 (`make setup && make test`) | Vale para o commit executado; consultar a CI do último commit. |
| FND-03 | aprovado | src/emporio/config.py; clock.py; money.py; tests/test_foundation.py | Só `LLM_BASE_URL`, `LLM_MODEL` e `LLM_API_KEY`; relógio injetável por `EMPORIO_NOW`. |
| FND-04 | aprovado | tests/test_foundation.py | A regra de importação não é prova de isolamento de rede. |
| ING-01 | aprovado | tests/test_foundation.py; make ingest | Saídas geradas são locais. |
| ING-02 | aprovado | src/emporio/ingest/pipeline.py; tests/test_foundation.py | Dados brutos devem continuar imutáveis. |
| ING-03 | aprovado | src/emporio/ingest/schemas.py; tests/test_foundation.py | Validação limitada aos contratos conhecidos. |
| ING-04 | aprovado | data/processed/policies.md; tests/test_foundation.py | Manual integral no prompt (DEC-03); divergência de contatos registrada no QUALITY.md. |
| ING-05 | aprovado | data/processed/QUALITY.md; tests/test_foundation.py | Reavaliar se os insumos mudarem. |
| REP-01 | aprovado | src/emporio/repository/base.py; src/emporio/repository/sqlite.py | Auditar novos adaptadores antes de uso. |
| REP-02 | aprovado | tests/test_integration_offline.py | Somente leitura não substitui controle de acesso. |
| TRC-01 | aprovado | tests/test_integration_offline.py; tests/test_foundation.py | Tracer bullet com roteiro; o caminho real é coberto pelo smoke test e pelo golden set. |
| TRC-02 | parcial | src/emporio/agent/trace.py; tests/test_trace_phase4.py | Teste de PII é limitado; falha de escrita é silenciosa; fluxo legado possui trace básico. |
| TLS-01 | aprovado | src/emporio/tools/contracts.py; tests/test_integration_offline.py | Erros de ferramentas devem permanecer sem texto privado. |
| TLS-02 | aprovado | src/emporio/tools/search.py; tests/test_search.py | Busca lexical; consultar limites do mini-eval. |
| TLS-03 | aprovado | src/emporio/tools/product.py; tests/test_product.py | Descrições são texto não confiável. |
| TLS-04 | parcial | src/emporio/tools/quote_payment.py; tests/test_quote_payment.py | Base de parcelas e arredondamento aguardam revisão comercial. |
| TLS-05 | aprovado | src/emporio/tools/store_status.py; tests/test_hours.py | Feriados fora do escopo. |
| TLS-06 | aprovado | src/emporio/tools/registry.py; tests/test_integration_offline.py; smoke test real | 8 tools expostas ao LLM real; schemas gerados dos contratos Pydantic. |
| DAT-01 | aprovado | src/emporio/repository/sqlite.py; tests/test_product.py | Não há validação de nome do produto na saída de LLM real. |
| PRC-01 | aprovado | tests/test_product.py; tests/test_pricing.py | Disponibilidade sujeita aos dados ingeridos. |
| PRC-02 | aprovado | tests/test_pricing.py; tests/test_product.py | Promoções futuras exigem reingestão. |
| PRC-03 | aprovado | tests/test_quote_payment.py | Cálculo em Python, sem avaliação real do agente. |
| PRC-04 | parcial | tests/test_pricing.py; tests/test_quote_payment.py | Distribuição de centavos e base aguardam revisão. |
| PRC-05 | parcial | tests/test_pricing.py; tests/test_quote_payment.py | Base sem frete aguarda decisão. |
| PRC-06 | aprovado | tests/test_pricing.py; tests/test_quote_payment.py | Municípios além de Campo Grande não possuem preço calculado. |
| PRC-07 | aprovado | tests/test_pricing.py; tests/test_product.py | A afirmação final por LLM real não foi avaliada. |
| PRC-08 | aprovado | tests/test_hours.py | Feriados excluídos. |
| SRC-01 | aprovado | src/emporio/repository/sqlite.py; tests/test_search.py; tests/test_trace_phase4.py | Busca lexical limitada aos dados indexados. |
| SRC-02 | aprovado | make bench; evals/reports/search.json | Dez casos: recall@5 0,800 e MRR 0,750; não prova generalização. |
| ORD-01 | aprovado | src/emporio/appdb/security_store.py; tests/test_appdb.py | Banco local não é implantação de produção. |
| ORD-02 | parcial | src/emporio/repository/sqlite.py; tests/test_order_security.py | Observações livres omitidas para privacidade; requisito pede observação. |
| ORD-03 | parcial | src/emporio/rules/returns.py; tests/test_returns.py | Nota livre em cancelamento omitida; falta conciliar requisito e privacidade. |
| ORD-04 | parcial | src/emporio/tools/escalation.py; tests/test_escalation.py | Resumo é descartado; utilidade do ticket aguarda decisão. |
| SEC-01 | aprovado | src/emporio/tools/registry.py; tests/test_order_security.py; src/emporio/cli.py | Identidade exclusivamente simulada. |
| SEC-02 | parcial | tests/test_order_security.py; src/emporio/security/access.py | Contatos compartilhados são negados; decisão de tratamento pendente. |
| SEC-03 | aprovado | tests/test_order_security.py; tests/test_agent_history.py | Verificação demonstrativa não é autenticação real. |
| SEC-04 | parcial | tests/test_order_security.py; src/emporio/appdb/security_store.py | Bloqueio persistente pode causar negação de serviço; desbloqueio pendente. |
| SEC-05 | parcial | src/emporio/agent/privacy.py; tests/test_real_path.py; tests/test_agent_loop.py | Tokenização heurística de contatos de clientes; formatos não previstos são bloqueados, sem garantia de cobertura total. |
| SEC-06 | parcial | tests/test_order_security.py; tests/test_agent_history.py; tests/test_trace_phase4.py | Varredura limitada aos artefatos e cenários exercitados. |
| SEC-07 | parcial | src/emporio/repository/sqlite.py; tests/test_order_security.py | Campos livres de outras fontes ainda podem conter dados privados. |
| SEC-08 | aprovado | tests/test_agent_loop.py; tests/test_order_security.py | Demonstração de autorização para os casos testados, não prova universal. |
| AGT-01 | aprovado | src/emporio/llm/openai_compat.py; tests/test_openai_compat.py (inclui HTTP real em loopback); smoke test real | Transporte `urllib`; timeout, retentativas e `reasoning_effort` baixo para gpt-oss. |
| AGT-02 | aprovado | docs/DECISIONS.md DEC-11 (seção 8) | Modelo padrão `openai/gpt-oss-120b` no Groq; o plano gratuito limita a 8.000 tokens/min e 200.000/dia. |
| AGT-03 | parcial | tests/test_agent_loop.py; tests/test_real_path.py; golden set (1ª rodada) | Comportamento do modelo real medido em 16 casos; ver README. |
| AGT-04 | aprovado | src/emporio/agent/prompt.py; docs/DECISIONS.md seção 8 | Manual integral no prompt; contatos institucionais da loja são dados públicos. |
| AGT-05 | parcial | src/emporio/agent/prompt.py; evals/golden_set.json | Persona e escopo avaliados no golden set; a rodada final está pendente. |
| AGT-06 | parcial | tests/test_product.py; tests/test_real_path.py; golden set | Nomes divergentes (T-2) cobertos em ferramenta; sem validador de nomes na saída do LLM. |
| AGT-07 | parcial | tests/test_money_validator.py; src/emporio/agent/money_validator.py | Padrões não reconhecem todas as formas de expressar valores. |
| AGT-08 | parcial | tests/test_agent_history.py; src/emporio/agent/history.py | Bytes UTF-8/3 não são tokens do modelo real. |
| AGT-09 | parcial | tests/test_agent_history.py; src/emporio/agent/history.py | Histórico persiste apenas usuário e resposta; proteção heurística. |
| AGT-10 | parcial | tests/test_agent_loop.py; tests/test_agent_history.py; tests/test_trace_phase4.py | Varredura e injeção restritas aos cenários testados. |
| EVL-01 | parcial | src/emporio/eval_runner.py; evals/reports/golden-20261101T200323Z.json | 1ª rodada medida: ferramentas 66,7%, exatidão 100%, recusas 87,5%. Rodada com as correções pendente (cota diária do Groq). |
| CLI-01 | aprovado | Makefile; src/emporio/cli.py | A ingestão requer os arquivos de entrada. |
| CLI-02 | aprovado | src/emporio/cli.py (`chat`, `chat --offline`); tests/test_real_path.py; tests/test_offline_phase4.py | Conversa livre com o LLM do `.env`; sem Rich. |
| CLI-03 | aprovado | src/emporio/cli.py; tests/test_offline_phase4.py | Aviso não transforma verificação em autenticação. |
| TST-01 | aprovado | tests/test_pricing.py; tests/test_quote_payment.py; tests/test_hours.py | Limites testados não resolvem decisões comerciais pendentes. |
| TST-02 | parcial | tests/test_order_security.py; tests/test_trace_phase4.py; make test | Passar testes existentes não é prova de segurança completa. |
| DOC-01 | aprovado | docs/DECISIONS.md | Decisões, suposições S-a..S-m, tratamento de dados T-1..T-9 e DEC-11. |
| DOC-02 | pendente | examples/ (vazio) | As cinco conversas reais aguardam cota do Groq; nenhuma foi fabricada. |
| DOC-03 | parcial | README.md | Métricas da rodada final do golden set pendentes. |
| DOC-04 | parcial | docs/ACCEPTANCE-MATRIX.md | Aceite final após golden set, conversas e CI do último commit. |
| DOC-05 | parcial | .gitignore; git ls-files; git history | Congelamento futuro e auditoria de segredos exigem verificação na entrega. |


## Critérios de aceite da ADR-000 §12 revisados pela §16

- `make setup`, `make test` e CI: aprovados no PR #5; conferir a CI do último commit.
- Limites e testes de segurança: testes locais passam; o escopo de privacidade e de rede não é universal.
- Interpretações e qualidade: `docs/DECISIONS.md` e `data/processed/QUALITY.md`.
- Mini-eval de busca: medido (`make bench`), sem generalização presumida.
- Golden set real: 1ª rodada medida e metas **não** atingidas; 3 dos 12 casos com ferramenta exigem argumentos que o cliente não fornece (ver README).
- Verificação demonstrativa: documentada na CLI e no README; não equivale a autenticação.
- Cinco conversas reais: pendentes.
- Itens adiados pela ADR §16 constam em "O que eu faria com mais tempo" no README.
