# Requirements: Empório AI

**Defined:** 2026-10-31
**Core Value:** O avaliador clona o repositório público e `make setup && make ingest && make test` rodam verdes sem chave, Docker, GPU ou rede (com chave, `make chat` e `make eval` funcionam), e o agente nunca erra preço, estoque, status nem acesso a pedido.

Origem: não há PRD; os requisitos foram derivados mecanicamente de ADR-000 (§5, §6, §8, §11, §12, §16) e `docs/DECISIONS.md`, via `.planning/intel/requirements.md`. Os 33 slugs `REQ-*` do intel foram desdobrados em IDs `CAT-NN` (as ferramentas GSD só rastreiam IDs nesse padrão); cada requisito cita o slug de origem em `(intel: ...)`. A seção "Referência cruzada com o intel" no fim prova que nenhum slug ficou órfão. Quando `docs/DECISIONS.md` ou a §16 sobrescrevem texto anterior da ADR-000, vale o texto efetivo.

## v1 Requirements

Escopo comprometido, 63 requisitos. Cada um mapeia para exatamente uma fase (ver Traceability).

### Fundação e reprodutibilidade (FND)

- [ ] **FND-01**: O projeto é Python 3.11+ com dependências travadas por uv (`pyproject.toml` + `uv.lock`), layout `src/emporio/` e Makefile com `setup`, `ingest` e `test`; `make setup && make ingest && make test` rodam sem chave, Docker, GPU ou rede após a instalação. Os alvos `bench` (Fase 2), `chat` e `eval` (Fase 4) entram com as fases que os entregam. (intel: REQ-ci-make-test; DEC-08)
- [ ] **FND-02**: A CI do GitHub Actions (`ubuntu-latest`, Python 3.11, sem secrets) roda `make setup && make test` e fica verde. (intel: REQ-ci-make-test)
- [ ] **FND-03**: Configuração por `.env` (com `.env.example` versionado contendo `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`), relógio injetável (`EMPORIO_NOW`; valor fixo `2026-03-25T10:00-04:00` nos testes) e dinheiro em centavos inteiros expostos como `Decimal`. (intel: REQ-ci-make-test; DEC-08, DEC-09, S-h)
- [ ] **FND-04**: `domain`, `rules`, `security` e `tools` não importam `agent` nem `llm`; um teste de arquitetura falha se a regra for violada. (intel: CON-architecture-deps)

### Ingestão e qualidade dos dados (ING)

- [ ] **ING-01**: `make ingest` (CLI `emporio ingest`) gera `var/store.db`, `data/processed/policies.md` e `data/processed/QUALITY.md`; é idempotente (reexecução produz resultado equivalente), não toca `app.db` e nunca edita `data/raw/`. (intel: REQ-ingest-pipeline)
- [ ] **ING-02**: O loader localiza cada CSV (`categories`, `customers`, `order_items`, `orders`, `products`, `promotions`) pelo sufixo do nome, tolerando espaços (`desafio_tecnico_ai_eng - <tabela>.csv`); arquivo ausente ou ambíguo falha a ingestão (T-6). (intel: REQ-ingest-pipeline)
- [ ] **ING-03**: Todas as tabelas são validadas com Pydantic na ingestão; duas promoções ativas (`is_active = 1`) no mesmo produto falham a ingestão (T-7; dado atual não tem o caso, testado com dado sintético). (intel: REQ-ingest-pipeline, REQ-rule-promotion)
- [ ] **ING-04**: `data/processed/policies.md` contém o manual v2.1 completo (8 páginas, §1 a §10) com marcadores `[§seção · p.página]` (DEC-03). (intel: REQ-ingest-pipeline)
- [ ] **ING-05**: `data/processed/QUALITY.md` lista todas as inconsistências conhecidas (ADR-000 §13 mais a lista adicional verificada em 2026-10-31, incluindo divergência de telefone/e-mail do manual, T-3 e T-4), sem atribuir causa. (intel: REQ-ingest-quality-report)

### Repositório e store.db (REP)

- [ ] **REP-01**: Todo acesso aos dados da loja passa pela interface `StoreRepository` (Protocol), com `SQLiteRepository` como implementação oficial. (intel: ADR-D7)
- [ ] **REP-02**: O atendimento abre `store.db` em `mode=ro`; uma tentativa de escrita falha (teste). (intel: REQ-tools-eight; DEC-02)

### Trace e tracer bullet (TRC)

- [ ] **TRC-01**: Tracer bullet ponta a ponta: ScriptedLLM pede `get_product`, a tool real executa sobre o `store.db` ingerido, o loop mínimo devolve a resposta e grava um trace JSONL básico por turno em `var/traces/`; roda na CI sem chave. (intel: CON-planning)
- [ ] **TRC-02**: O trace JSONL por turno carrega os campos essenciais (hash da sessão, turno, iteração máx. 5, `tool_calls[]` com args redigidos/status/erro/latência, `llm` com modelo/latência/tokens, `search_backend`, `validator`, `budget`, `auth` sem contato, `errors[]`) e nunca contém contato de cliente; não há comando `emporio trace`. (intel: REQ-trace-jsonl)

### Ferramentas (TLS)

- [ ] **TLS-01**: Existe o envelope `ToolResult {ok, data, error{code, message_for_agent}}` com os códigos `invalid_input`, `not_found`, `ambiguous`, `access_denied`, `not_verified`, `locked`, `internal_error`; as tools são Python puro, sem importar `agent`/`llm`. (intel: REQ-tools-eight)
- [ ] **TLS-02**: `search_products` (`query?`, `category?`, `min_price?`, `max_price?`, `only_available=true`, `limit=5`) devolve `ProductSummary[]` (id, nome, categoria, `availability`, estoque, `PriceInfo`), `total_matches` e `search_backend`. (intel: REQ-tools-eight)
- [ ] **TLS-03**: `get_product` (por `product_id` ou `name`) devolve `ProductDetail` (specs, `PriceInfo`, `inactive_promotions`, `alternatives`); nome ambíguo devolve `ambiguous` com candidatos. (intel: REQ-tools-eight)
- [ ] **TLS-04**: `quote_payment` (`items[{product_id, quantity}]`, `destination_city?`) devolve, por item, preço de tabela, final, promoção, elegibilidade e preço PIX; totais; `installments[{n, valor, valid, reason}]`; `combined_payment_allowed`; `shipping`; itens não vendáveis entram como `not_purchasable`, fora dos totais. (intel: REQ-tools-eight)
- [ ] **TLS-05**: `store_status` (sem entrada) devolve `now_local`, `is_open`, horário de hoje e próxima abertura, usando o relógio injetável. (intel: REQ-tools-eight)
- [ ] **TLS-06**: As 8 tools (`search_products`, `get_product`, `quote_payment`, `store_status`, `verify_order_ownership`, `get_order`, `check_return_eligibility`, `escalate_to_human`) ficam registradas com contratos Pydantic expostos ao LLM como definições de function calling, com despacho e erros estruturados. (intel: REQ-tools-eight)

### Dados da loja (DAT)

- [ ] **DAT-01**: Nenhuma tool envia ao LLM a descrição dos produtos 135, 136, 137, 139, 140, 142 e 144 (nome e specs são a fonte de verdade; a descrição fica só no índice de busca), nem em `search_products` nem em `get_product` (T-2). (intel: REQ-data-treatment-rules)

### Regras de negócio: catálogo, preço, pagamento e atendimento (PRC)

- [ ] **PRC-01**: Disponibilidade: `active` com estoque > 0 é disponível; `active` com estoque 0 é indisponível, com alternativas; `discontinued` está fora do catálogo mesmo com estoque; `coming_soon` não é vendável (produtos 96, 113, 136, 130). (intel: REQ-rule-availability)
- [ ] **PRC-02**: Só promoções com `is_active = 1` valem; `PriceInfo` mostra preço original e percentual de desconto sempre juntos; promoções inativas aparecem em lista separada no detalhe do produto (GD20, produto 95; produto 90 com 18%). (intel: REQ-rule-promotion)
- [ ] **PRC-03**: O desconto PIX de 5% é aplicado item a item, apenas em itens sem promoção ativa (carrinho misto: 121 com promoção + 81 sem; S-j). (intel: REQ-rule-pix)
- [ ] **PRC-04**: Crédito 1x sem mínimo; 2x–3x com parcela >= R$ 50,00; 4x–6x com parcela >= R$ 80,00; 7x–12x com parcela >= R$ 100,00 (limites inclusivos; §3.1 prevalece sobre a tabela da §3); cada opção retorna `{n, valor, valid, reason}`. (intel: REQ-rule-installments; S-a, S-b)
- [ ] **PRC-05**: Pagamento combinado é permitido a partir de R$ 2.000,00, inclusive. (intel: REQ-rule-combined-payment; S-d)
- [ ] **PRC-06**: Frete só para a cidade de Campo Grande: grátis a partir de R$ 500,00 inclusive, abaixo R$ 35,00, base = subtotal com promoção antes do PIX, prazo de 1 a 3 dias úteis; outras cidades sem valor, com PAC, SEDEX e Jadlog e seus prazos (cálculo por CEP, peso e dimensões no fechamento). (intel: REQ-rule-shipping; S-c, S-e, S-f)
- [ ] **PRC-07**: `special_quote_required` vale apenas para a lista explícita 135, 136, 137, 138, 139, 140, 141, sem inferência pela descrição; o dado entregue ao agente permite dizer "pode exigir cotação especial", nunca que exige. (intel: REQ-rule-special-quote; S-i)
- [ ] **PRC-08**: Horário: segunda a sexta 9h–18h, sábado 9h–13h, domingo fechado (sábado 12:59 aberto, 13:00 fechado); feriados fora do escopo; relógio injetável. (intel: REQ-rule-store-hours)

### Busca (SRC)

- [ ] **SRC-01**: A busca usa SQLite FTS5/BM25 + rapidfuzz; filtros (categoria, faixa de preço, disponibilidade) são exatos em SQL; o índice só ordena IDs e os dados vêm do repositório; `search_backend` é informado na resposta da tool e no trace; não existe backend denso nem `auto`/`hybrid`. (intel: REQ-search-lexical)
- [ ] **SRC-02**: `make bench` roda, sem nenhum download, um mini-eval de ~10 consultas (`evals/search_queries.yaml`, três grupos: por nome / por intenção / ambíguas, ~3–4 cada) e grava recall@5 e MRR do backend lexical em `evals/reports/`; nenhum resultado é presumido. (intel: REQ-search-minieval)

### Pedidos, devoluções e escalonamento (ORD)

- [ ] **ORD-01**: Existe `app.db` separado do `store.db`, criado de forma idempotente, com histórico, sessões, `order_access`, tentativas de verificação e tickets de escalonamento. (intel: REQ-sec-order-access; DEC-02)
- [ ] **ORD-02**: `get_order` devolve status, data, itens, `total_brl` descrito como "total registrado no pedido", pagamento, rastreio, previsão, observação e apenas o primeiro nome do cliente; o pedido 3 retorna R$ 3.450,00 (e não a soma dos itens, 3.498,00). (intel: REQ-rule-order-total, REQ-tools-eight; T-1)
- [ ] **ORD-03**: `check_return_eligibility` retorna `ReturnStatus` em {`eligible`, `expired`, `not_applicable`, `not_yet_delivered`, `cancelled`, `insufficient_information`}: pedido cancelado → `cancelled` (com a observação); `pending`/`confirmed`/`shipped` → `not_yet_delivered`; arrependimento só online, 7 dias corridos do recebimento (sem `received_at` ou canal → `insufficient_information`; presencial → `not_applicable`); defeito em 30 dias corridos da `order_date`, depois `expired` com orientação de garantia do fabricante e garantia legal de 90 dias do recebimento; preferência em 7 dias do recebimento; exclusões (personalização, venda final, boquilhas) em `exclusions_to_confirm`; lista `missing_information`; `estimated_delivery` nunca é data de recebimento; nunca aprova devolução. (intel: REQ-rule-returns; S-g, T-8)
- [ ] **ORD-04**: `escalate_to_human` (`category`, `summary` tokenizado) grava o ticket no `app.db` sem PII e informa retorno em 24 horas úteis. (intel: REQ-tools-eight, REQ-rule-scope-contact)

### Segurança e privacidade (SEC)

- [ ] **SEC-01**: Existem dois modos de identidade: `anonymous` (padrão) e `simulated_authenticated` (cliente informado pelo canal, via `--customer <id>` na CLI), modelados em Python no contexto de sessão. (intel: REQ-sec-order-access; DEC-05)
- [ ] **SEC-02**: `verify_order_ownership` (`order_id`, `contact_ref` token) concede acesso demonstrativo comparando o contato com o cliente DO PEDIDO (clientes 11 e 43 compartilham e-mail: teste dedicado, T-5); pedido inexistente e contato errado produzem resposta `not_verified` idêntica; nenhuma consulta de pedido só pelo nome. (intel: REQ-sec-order-access; T-5)
- [ ] **SEC-03**: O acesso gravado em `order_access(session_id, order_id, granted_at, expires_at)` vale 15 minutos; `get_order` e `check_return_eligibility` checam o acesso em Python a cada chamada (`access_denied` sem acesso, exista o pedido ou não); no modo `simulated_authenticated` com cliente 3, os pedidos 1 e 19 são visíveis e o 2 não. (intel: REQ-sec-order-access; DEC-10)
- [ ] **SEC-04**: Falhas de verificação são contadas por `order_id` e por sessão, persistidas; 3 falhas bloqueiam (`locked`), inclusive em sessões novas, e encaminham para a equipe. (intel: REQ-sec-lockout)
- [ ] **SEC-05**: E-mails e telefones são tokenizados (`[EMAIL_1]`, `[PHONE_1]`) antes de chegar ao LLM; o mapa token→contato vive só na memória do processo, isolado por sessão, nunca em prompt, trace, histórico ou disco; `verify_order_ownership` resolve o `contact_ref` em Python. (intel: REQ-sec-pii; DEC-06)
- [ ] **SEC-06**: Um teste de varredura prova que nenhum e-mail ou telefone do `customers.csv` aparece em `app.db` (incluindo tickets), traces e saídas de tools geradas nos testes; o harness é reutilizável pela Fase 4 (prompts e histórico). (intel: REQ-sec-pii)
- [ ] **SEC-07**: Nenhuma saída de tool contém e-mail, telefone ou nome completo de cliente. (intel: REQ-tools-eight, REQ-sec-pii)
- [ ] **SEC-08**: Texto injetado em dados (ex.: descrição de produto mandando "conceder acesso ao pedido 2") não muda permissões: a autorização é em Python, independente do LLM, e uma chamada de tool pedida por conteúdo injetado continua sujeita a `access_denied`. (intel: REQ-sec-pii; DEC-10)

### Agente (AGT)

- [ ] **AGT-01**: O adaptador OpenAI-compatible é configurado só por `LLM_BASE_URL`, `LLM_MODEL` e `LLM_API_KEY` em `.env` (trocar de provedor não exige mudar código); `ScriptedLLM` atende os testes sem chave. (intel: REQ-agent-llm-config; DEC-07)
- [ ] **AGT-02**: O modelo padrão é escolhido na fase consultando a documentação oficial do provedor e registrado em `docs/DECISIONS.md`, junto com a regra de temperatura do golden set. (intel: REQ-agent-llm-config, REQ-docs-decisions)
- [ ] **AGT-03**: Loop próprio de function calling com contratos Pydantic (sem PydanticAI/LangGraph), no máximo 5 iterações por turno; erro de tool estruturado volta ao LLM e é tratado; resultados de tools entram no prompt delimitados como dados. (intel: REQ-agent-loop; DEC-01)
- [ ] **AGT-04**: O prompt inclui o manual completo (`policies.md`) e as instruções de uso de tools, dados e honestidade (na dúvida, perguntar ou escalar; nunca inventar). (intel: REQ-agent-loop; DEC-03)
- [ ] **AGT-05**: Pedido fora de escopo (acessórios; forma de pagamento "dinheiro", ausente do manual §3) é tratado sem chamar tool e sem citar lojas parceiras; o contato oficial informado é (67) 3341-4444 e `contato@emporiodamusica.com.br`; reclamação vai para `escalate_to_human` com retorno em 24 horas úteis. (intel: REQ-rule-scope-contact; S-k, S-l)
- [ ] **AGT-06**: O agente não cita marca vinda das descrições divergentes (T-2) e, para produtos da lista S-i, diz que "pode exigir cotação especial", nunca que exige. (intel: REQ-data-treatment-rules, REQ-rule-special-quote)
- [ ] **AGT-07**: Validador de evidências só para R$: todo valor em R$ citado deve constar nos resultados de tools do turno; senão regenera uma vez; persistindo, resposta segura. (intel: REQ-agent-validator-rs)
- [ ] **AGT-08**: Orçamento de 16k tokens por chamada: o histórico é truncado primeiro; manual e definições de tools nunca são truncados. (intel: REQ-agent-loop)
- [ ] **AGT-09**: O histórico da conversa é persistido no `app.db` (tokenizado) e retomado entre turnos. (intel: REQ-agent-loop)
- [ ] **AGT-10**: A varredura de PII cobre os artefatos reais do agente (prompts enviados ao LLM, histórico e traces gerados em execuções com ScriptedLLM), e injeção em descrição de produto não altera permissões também no nível do agente. (intel: REQ-sec-pii)

### Avaliação (EVL)

- [ ] **EVL-01**: `make eval` roda, com LLM real, um golden set de ~15 casos (catálogo, preço/pagamento, pedidos, devoluções, loja, fora de escopo, adversariais), 1 repetição, temperature 0 quando o modelo suporta (senão a exceção é documentada), e grava o relatório em `evals/reports/`; metas: acerto de tool >= 90%, exatidão de preço/estoque/status = 100%, recusas corretas = 100%. (intel: REQ-eval-golden)

### CLI (CLI)

- [ ] **CLI-01**: `emporio ingest` existe e é o comando por trás de `make ingest`. (intel: REQ-cli)
- [ ] **CLI-02**: `emporio chat` (Rich), com `--customer <id>` opcional, conduz a conversa com o agente; `make chat` o executa. (intel: REQ-cli)
- [ ] **CLI-03**: A CLI declara, ao iniciar, que a verificação de pedido é demonstrativa (e que a identidade de `--customer` é simulada). (intel: REQ-sec-verification-disclosure; DEC-05)

### Testes (TST)

- [ ] **TST-01**: Todos os testes de limite das regras de negócio (ADR-000 §11 "Regras") passam, incluindo frete em R$ 500,00 exatos. (intel: REQ-tests-boundary)
- [ ] **TST-02**: 100% dos testes de segurança (ADR-000 §11 "Segurança") passam. (intel: REQ-tests-boundary)

### Entrega (DOC)

- [ ] **DOC-01**: `docs/DECISIONS.md` está completo e coerente na entrega: toda interpretação do manual (S-a..S-l) com o trecho de origem, tratamento dos dados (T-1..T-9), modelo padrão do LLM, defaults do mini-eval e do golden set, dependências adicionadas fora da stack inicial. (intel: REQ-docs-decisions)
- [ ] **DOC-02**: `examples/` contém 5 conversas REAIS em `.md` (geradas com `emporio chat` e LLM real, não simuladas): catálogo, promoção, consulta protegida de pedido, devolução e tentativa de acesso indevido; cada uma declara o modelo e o relógio usados. (intel: REQ-docs-examples)
- [ ] **DOC-03**: O README contém instruções (`make setup/ingest/test/chat/eval/bench`), arquitetura, decisões, limitações, resultados do mini-eval de busca e do golden set, a declaração de verificação demonstrativa, o uso de assistentes de IA (revisão multi-IA da arquitetura + Claude Code com GSD na implementação) e "o que eu faria com mais tempo" com todos os itens adiados. (intel: REQ-docs-readme, REQ-sec-verification-disclosure)
- [ ] **DOC-04**: A checagem final de aceite contra ADR-000 §12 revisado pela §16 é executada e registrada com evidência (saída de comando ou teste) para cada critério, incluindo clone limpo e CI verde. (intel: REQ-tests-boundary, REQ-ci-make-test)
- [ ] **DOC-05**: Commits incrementais, sem force-push, sem `.env`, `var/`, `.claude/` ou `docs/private/` versionados, e repositório congelado em 2026-11-03 20:00. (intel: REQ-git-delivery; CON-repo-hygiene, CON-schedule)

## v2 Requirements

Adiados pela ADR-000 §16; entram só como itens do README em "o que eu faria com mais tempo" (DOC-03). Não estão no roadmap.

### Adiados

- **DEF-01**: Qdrant e busca densa/híbrida (RRF, backend `auto`/`hybrid`).
- **DEF-02**: ReplayLLM, `make demo` e `recordings/`.
- **DEF-03**: Adapter Firestore para `StoreRepository`.
- **DEF-04**: LLM-as-judge no golden set.
- **DEF-05**: Comando `emporio trace`.
- **DEF-06**: Login ou OTP real no lugar da identidade simulada.
- **DEF-07**: Golden set com múltiplas repetições.
- **DEF-08**: Validador de evidências para estoque, número de pedido e nome de produto.

## Out of Scope

| Feature | Reason |
|---------|--------|
| PydanticAI, LangGraph | DEC-01: 8 tools e fluxo linear não justificam framework |
| Firebase/Firestore obrigatório | Dependência externa sem ganho para o protótipo |
| RAG das políticas como caminho principal | DEC-03: manual de 8 páginas cabe no contexto; RAG adiciona risco de trecho errado |
| Roteador de intenções paralelo ao LLM | Duplica a decisão que o function calling já toma |
| Embeddings via API paga | Quebra a reprodutibilidade sem chave |
| Consulta de pedido por nome do cliente | Nomes não identificam ninguém com segurança |
| Filtro de injeção por palavras-chave | Contornável; a defesa é a autorização em Python |
| Sleep fixo contra ataque de timing | Não resolve; respostas idênticas e bloqueio por tentativas resolvem |
| Lojas parceiras para acessórios | S-k: o manual não lista parceiros; acessórios são recusados |
| Feriados e municípios além de Campo Grande | S-f e ADR-000 §6: fora do MVP |
| Validação de exclusões de troca (personalização, venda final, boquilhas) | Não estão nos dados; retornam em `exclusions_to_confirm` |

## Traceability

Cada requisito mapeia para exatamente uma fase.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FND-01 | Phase 1 | Pending |
| FND-02 | Phase 1 | Pending |
| FND-03 | Phase 1 | Pending |
| FND-04 | Phase 1 | Pending |
| ING-01 | Phase 1 | Pending |
| ING-02 | Phase 1 | Pending |
| ING-03 | Phase 1 | Pending |
| ING-04 | Phase 1 | Pending |
| ING-05 | Phase 1 | Pending |
| REP-01 | Phase 1 | Pending |
| REP-02 | Phase 1 | Pending |
| TRC-01 | Phase 1 | Pending |
| TLS-01 | Phase 1 | Pending |
| CLI-01 | Phase 1 | Pending |
| TLS-02 | Phase 2 | Pending |
| TLS-03 | Phase 2 | Pending |
| TLS-04 | Phase 2 | Pending |
| TLS-05 | Phase 2 | Pending |
| DAT-01 | Phase 2 | Pending |
| PRC-01 | Phase 2 | Pending |
| PRC-02 | Phase 2 | Pending |
| PRC-03 | Phase 2 | Pending |
| PRC-04 | Phase 2 | Pending |
| PRC-05 | Phase 2 | Pending |
| PRC-06 | Phase 2 | Pending |
| PRC-07 | Phase 2 | Pending |
| PRC-08 | Phase 2 | Pending |
| SRC-01 | Phase 2 | Pending |
| SRC-02 | Phase 2 | Pending |
| TST-01 | Phase 2 | Pending |
| ORD-01 | Phase 3 | Pending |
| ORD-02 | Phase 3 | Pending |
| ORD-03 | Phase 3 | Pending |
| ORD-04 | Phase 3 | Pending |
| SEC-01 | Phase 3 | Pending |
| SEC-02 | Phase 3 | Pending |
| SEC-03 | Phase 3 | Pending |
| SEC-04 | Phase 3 | Pending |
| SEC-05 | Phase 3 | Pending |
| SEC-06 | Phase 3 | Pending |
| SEC-07 | Phase 3 | Pending |
| SEC-08 | Phase 3 | Pending |
| TST-02 | Phase 3 | Pending |
| TRC-02 | Phase 4 | Pending |
| TLS-06 | Phase 4 | Pending |
| AGT-01 | Phase 4 | Pending |
| AGT-02 | Phase 4 | Pending |
| AGT-03 | Phase 4 | Pending |
| AGT-04 | Phase 4 | Pending |
| AGT-05 | Phase 4 | Pending |
| AGT-06 | Phase 4 | Pending |
| AGT-07 | Phase 4 | Pending |
| AGT-08 | Phase 4 | Pending |
| AGT-09 | Phase 4 | Pending |
| AGT-10 | Phase 4 | Pending |
| EVL-01 | Phase 4 | Pending |
| CLI-02 | Phase 4 | Pending |
| CLI-03 | Phase 4 | Pending |
| DOC-01 | Phase 5 | Pending |
| DOC-02 | Phase 5 | Pending |
| DOC-03 | Phase 5 | Pending |
| DOC-04 | Phase 5 | Pending |
| DOC-05 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 63 total
- Mapped to phases: 63
- Unmapped: 0 ✓
- Por fase: Fase 1 = 14, Fase 2 = 16, Fase 3 = 13, Fase 4 = 15, Fase 5 = 5

## Referência cruzada com o intel (33 slugs, 33 cobertos)

Lista em bullets (não tabela) para não interferir no parser da tabela de Traceability.

- `REQ-ingest-pipeline` → ING-01, ING-02, ING-03, ING-04
- `REQ-ingest-quality-report` → ING-05
- `REQ-data-treatment-rules` → DAT-01 (T-2), ING-05 (T-3, T-4), SEC-02 (T-5), ORD-02 (T-1), ORD-03 (T-8), AGT-06 (T-2 no agente)
- `REQ-rule-availability` → PRC-01
- `REQ-rule-promotion` → PRC-02, ING-03 (duplicata ativa)
- `REQ-rule-pix` → PRC-03
- `REQ-rule-installments` → PRC-04
- `REQ-rule-combined-payment` → PRC-05
- `REQ-rule-shipping` → PRC-06
- `REQ-rule-special-quote` → PRC-07, AGT-06 (redação)
- `REQ-rule-order-total` → ORD-02
- `REQ-rule-returns` → ORD-03
- `REQ-rule-store-hours` → PRC-08
- `REQ-rule-scope-contact` → AGT-05, ORD-04
- `REQ-tools-eight` → TLS-01 (envelope), TLS-02..TLS-05, ORD-02..ORD-04, SEC-02, SEC-07, TLS-06 (registry), REP-02
- `REQ-agent-loop` → AGT-03, AGT-04, AGT-08, AGT-09
- `REQ-agent-validator-rs` → AGT-07
- `REQ-agent-llm-config` → AGT-01, AGT-02
- `REQ-sec-order-access` → SEC-01, SEC-02, SEC-03, ORD-01
- `REQ-sec-lockout` → SEC-04
- `REQ-sec-pii` → SEC-05, SEC-06, SEC-07, SEC-08, AGT-10
- `REQ-sec-verification-disclosure` → CLI-03, DOC-03
- `REQ-search-lexical` → SRC-01
- `REQ-search-minieval` → SRC-02
- `REQ-eval-golden` → EVL-01
- `REQ-trace-jsonl` → TRC-01 (básico), TRC-02 (completo)
- `REQ-cli` → CLI-01, CLI-02, CLI-03
- `REQ-ci-make-test` → FND-01, FND-02, FND-03, DOC-04
- `REQ-docs-decisions` → AGT-02, DOC-01
- `REQ-docs-examples` → DOC-02
- `REQ-docs-readme` → DOC-03
- `REQ-tests-boundary` → TST-01, TST-02, DOC-04
- `REQ-git-delivery` → DOC-05

Requisitos derivados (sem slug próprio no intel, extraídos de constraints e do plano): FND-04 (CON-architecture-deps), TRC-01 e a divisão do trace em básico/completo (CON-planning, CON-trace-schema), REP-01 (ADR-D7), TLS-01 (CON-tool-envelope).

## Matriz de testes (ADR-000 §11 revisado pela §16, mais itens do dono)

Cada item de teste tem uma única fase de origem; extensões em fases posteriores aparecem entre parênteses. O grupo "Demo" do §11 está fora do escopo (§16).

| Teste | Grupo §11 | Fase |
|-------|-----------|------|
| `QUALITY.md` completo (cada item do §13 e da lista adicional) | Ingestão e tools | Phase 1 |
| Escrita em `store.db` falha | Ingestão e tools | Phase 1 |
| Promoção duplicada ativa falha (dado sintético, T-7) | Regras | Phase 1 |
| Loader por sufixo tolerante a espaços; ausente/ambíguo falha (T-6) | Ingestão (dono) | Phase 1 |
| Ingestão idempotente; `data/raw/` inalterado; `policies.md` com marcadores | Ingestão (derivado) | Phase 1 |
| Arquitetura: tools/rules/domain/security não importam agent/llm | Derivado | Phase 1 |
| Tracer bullet ScriptedLLM → `get_product` → resposta → trace | Derivado (CON-planning) | Phase 1 |
| Frete 499,99 / 500,00 / 500,01; subtotal 510,00 com PIX; outra cidade | Regras | Phase 2 |
| Bateria acústica e lista S-i (135–141; 143 sem flag) | Regras (dono) | Phase 2 |
| Parcelamento 2x 100,00/99,98, 3x 150,00/149,97, 4x 320,00/319,96, 7x 700,00/699,93, 12x 1.200,00/1.199,88, com motivo | Regras | Phase 2 |
| Combinado 1.999,99 / 2.000,00 | Regras | Phase 2 |
| PIX em carrinho misto (121 com promoção + 81 sem) | Regras | Phase 2 |
| GD20 (95) com promoção inativa; produto 90 com 18% | Regras | Phase 2 |
| Disponibilidade 96, 113, 136, 130 | Regras | Phase 2 |
| Horário sáb 12h59 / 13h00 e domingo | Regras | Phase 2 |
| Nome ambíguo devolve `ambiguous` com candidatos | Ingestão e tools | Phase 2 |
| Sem descrição para 135, 136, 137, 139, 140, 142, 144 (T-2, nível de tool) | Ingestão e tools (dono) | Phase 2 |
| Mini-eval de busca medido (`make bench`) | §12 | Phase 2 |
| Devolução: sem `received_at`, sem canal, presencial, defeito por `order_date`, pedido 20 cancelado, pedido 13 não entregue | Regras | Phase 3 |
| Pedido 3 retorna R$ 3.450,00 | Ingestão e tools | Phase 3 |
| Anônimo sem acesso; respostas idênticas (inexistente x contato errado) | Segurança | Phase 3 |
| Bloqueio após 3 falhas entre sessões; expiração em 15 min | Segurança | Phase 3 |
| `--customer 3` vê 1 e 19, não o 2 (nível de tool/contexto; CLI na Fase 4) | Segurança | Phase 3 |
| Acesso só por nome negado | Segurança | Phase 3 |
| E-mail repetido nos clientes 11 e 43: contato comparado com o cliente do pedido (T-5) | Segurança (dono) | Phase 3 |
| Injeção em descrição não muda permissões (nível de tool; agente na Fase 4) | Segurança | Phase 3 |
| Varredura: nenhum contato do CSV em app.db/tickets/traces/saídas de tools (prompts e histórico na Fase 4) | Segurança | Phase 3 |
| Agente: 5 iterações; erro de tool estruturado; validador regenera e cai em resposta segura; orçamento preserva o manual; fora de escopo sem tool; histórico persiste | Agente (ScriptedLLM) | Phase 4 |
| Agente não cita marca vinda de descrição divergente (T-2) e usa "pode exigir cotação especial" (S-i) | Agente (dono) | Phase 4 |
| "Dinheiro": forma de pagamento fora do manual §3 não é inventada (interpretação a confirmar) | Regras | Phase 4 |
| Varredura de PII sobre prompts, histórico e traces do agente | Segurança | Phase 4 |
| Golden set (~15 casos, `make eval`) | Golden set | Phase 4 |
| Clone limpo + CI verde + checagem §12 revisada | §12 | Phase 5 |

---
*Requirements defined: 2026-10-31*
*Last updated: 2026-10-31 after roadmap creation*
