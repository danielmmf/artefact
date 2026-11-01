# Matriz de aceite — auditoria verificável

Estados avaliam o requisito integral: aprovado = evidência offline suficiente para o escopo explicitado; parcial = componente ou evidência incompleta; bloqueado = dependência proibida ou ainda não aprovada; não implementado = ausente. Nenhuma linha aprova produção. Testes de simulador não são avaliação com LLM real. A aprovação de requisitos e a conciliação GSD cabem a Claude e ao responsável.

| ID | Estado | Evidência concreta | Risco / limitação e pendência para Claude |
| --- | --- | --- | --- |
| FND-01 | parcial | Makefile; pyproject.toml; uv.lock | Instalação pode requerer rede; chat/eval reais bloqueados. |
| FND-02 | aprovado | .github/workflows/ci.yml; CI do PR #4 | Referente ao commit executado, não a versões futuras. |
| FND-03 | aprovado | src/emporio/config.py; clock.py; money.py; tests/test_foundation.py | Configuração LLM não habilita adaptador. |
| FND-04 | aprovado | tests/test_foundation.py | A regra de importação não é prova de isolamento de rede. |
| ING-01 | aprovado | tests/test_foundation.py; make ingest | Saídas geradas são locais. |
| ING-02 | aprovado | src/emporio/ingest/pipeline.py; tests/test_foundation.py | Dados brutos devem continuar imutáveis. |
| ING-03 | aprovado | src/emporio/ingest/schemas.py; tests/test_foundation.py | Validação limitada aos contratos conhecidos. |
| ING-04 | aprovado | data/processed/policies.md; tests/test_foundation.py | Manual contém contatos divergentes; projeção externa pendente. |
| ING-05 | aprovado | data/processed/QUALITY.md; tests/test_foundation.py | Reavaliar se os insumos mudarem. |
| REP-01 | aprovado | src/emporio/repository/base.py; src/emporio/repository/sqlite.py | Auditar novos adaptadores antes de uso. |
| REP-02 | aprovado | tests/test_integration_offline.py | Somente leitura não substitui controle de acesso. |
| TRC-01 | aprovado | tests/test_integration_offline.py; tests/test_foundation.py | Simulação, sem LLM real. |
| TRC-02 | parcial | src/emporio/agent/trace.py; tests/test_trace_phase4.py | Teste de PII é limitado; falha de escrita é silenciosa; fluxo legado possui trace básico. |
| TLS-01 | aprovado | src/emporio/tools/contracts.py; tests/test_integration_offline.py | Erros de ferramentas devem permanecer sem texto privado. |
| TLS-02 | aprovado | src/emporio/tools/search.py; tests/test_search.py | Busca lexical; consultar limites do mini-eval. |
| TLS-03 | aprovado | src/emporio/tools/product.py; tests/test_product.py | Descrições são texto não confiável. |
| TLS-04 | parcial | src/emporio/tools/quote_payment.py; tests/test_quote_payment.py | Base de parcelas e arredondamento aguardam revisão comercial. |
| TLS-05 | aprovado | src/emporio/tools/store_status.py; tests/test_hours.py | Feriados fora do escopo. |
| TLS-06 | aprovado | src/emporio/tools/registry.py; tests/test_integration_offline.py | Só simulador exercitado. |
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
| SEC-05 | parcial | src/emporio/agent/privacy.py; tests/test_agent_loop.py | Regex não cobre tudo; manual em claro e gate externo pendente. |
| SEC-06 | parcial | tests/test_order_security.py; tests/test_agent_history.py; tests/test_trace_phase4.py | Varredura limitada aos artefatos e cenários exercitados. |
| SEC-07 | parcial | src/emporio/repository/sqlite.py; tests/test_order_security.py | Campos livres de outras fontes ainda podem conter dados privados. |
| SEC-08 | aprovado | tests/test_agent_loop.py; tests/test_order_security.py | Demonstração de autorização para os casos testados, não prova universal. |
| AGT-01 | bloqueado | src/emporio/agent/loop.py | Adaptador externo não implementado por decisão de segurança. |
| AGT-02 | bloqueado | docs/DECISIONS.md §7 | Modelo padrão e fonte oficial ainda não escolhidos. |
| AGT-03 | parcial | tests/test_agent_loop.py; src/emporio/agent/loop.py | Somente simulador; comportamento de modelo real não medido. |
| AGT-04 | parcial | src/emporio/agent/prompt.py; tests/test_agent_loop.py | Manual integral contém contatos em claro; projeção externa pendente. |
| AGT-05 | parcial | src/emporio/agent/prompt.py; evals/golden_set.json | Sem avaliação de modelo real; divergência de contatos pendente. |
| AGT-06 | parcial | tests/test_product.py; tests/test_agent_loop.py | Sem evidência de saída de modelo real. |
| AGT-07 | parcial | tests/test_money_validator.py; src/emporio/agent/money_validator.py | Padrões não reconhecem todas as formas de expressar valores. |
| AGT-08 | parcial | tests/test_agent_history.py; src/emporio/agent/history.py | Bytes UTF-8/3 não são tokens do modelo real. |
| AGT-09 | parcial | tests/test_agent_history.py; src/emporio/agent/history.py | Histórico persiste apenas usuário e resposta; proteção heurística. |
| AGT-10 | parcial | tests/test_agent_loop.py; tests/test_agent_history.py; tests/test_trace_phase4.py | Varredura e injeção restritas aos cenários testados. |
| EVL-01 | bloqueado | evals/golden_set.json; src/emporio/eval_gate.py; make eval | Sem adaptador, execução, relatório ou métricas reais. |
| CLI-01 | aprovado | Makefile; src/emporio/cli.py | A ingestão requer os arquivos de entrada. |
| CLI-02 | parcial | src/emporio/cli.py; tests/test_offline_phase4.py | Dois roteiros fixos; não é CLI Rich nem conversa com LLM real. |
| CLI-03 | aprovado | src/emporio/cli.py; tests/test_offline_phase4.py | Aviso não transforma verificação em autenticação. |
| TST-01 | aprovado | tests/test_pricing.py; tests/test_quote_payment.py; tests/test_hours.py | Limites testados não resolvem decisões comerciais pendentes. |
| TST-02 | parcial | tests/test_order_security.py; tests/test_trace_phase4.py; make test | Passar testes existentes não é prova de segurança completa. |
| DOC-01 | parcial | docs/DECISIONS.md §7 | Modelo e decisões comerciais e de privacidade continuam pendentes. |
| DOC-02 | bloqueado | docs/adr/ADR-000-especificacao-consolidada.md §12 | Cinco conversas reais dependem de LLM real autorizado; nenhuma foi fabricada. |
| DOC-03 | parcial | README.md | Métricas de golden set real ainda indisponíveis. |
| DOC-04 | parcial | docs/ACCEPTANCE-MATRIX.md; docs/VALIDACAO-CHECKOUT.md | Aceite final depende de gate, avaliação real e conversas reais. |
| DOC-05 | parcial | .gitignore; git ls-files; git history | Congelamento futuro e auditoria de segredos exigem verificação na entrega. |

## Critérios de aceite da ADR-000 §12 revisados pela §16

- `make setup` e `make test` e CI: evidência em `docs/VALIDACAO-CHECKOUT.md` e CI do PR; instalação pode usar rede.
- Limites e testes de segurança: testes locais passam, mas escopo de privacidade e rede não é universal.
- Interpretações e qualidade: `docs/DECISIONS.md` e `data/processed/QUALITY.md`; decisões abertas permanecem explícitas.
- Mini-eval: medido localmente, sem generalização presumida. Golden set real e suas metas: bloqueados.
- Verificação demonstrativa: documentada na CLI e README; não equivale a autenticação.
- Cinco conversas reais: bloqueadas; nenhuma simulação é apresentada como real.
- README e entrega: atualizados; revisão humana, CI do último commit e congelamento permanecem dependências.

Itens DEF-01 a DEF-08 são adiados pela ADR §16 e constam em “O que eu faria com mais tempo” no README; não são critérios implementados nesta rodada.
