# ADR-000 — Especificação consolidada do Agente Empório da Música

- **Status:** Aceita — escopo revisado em 2026-10-31 (seção 16, que prevalece sobre as seções anteriores)
- **Data:** 2026-10-31
- **Responsável:** Daniel Medeiros
- **Insumos:** propostas e revisões de Claude, ChatGPT, Gemini, DeepSeek e GLM, validadas contra os CSVs oficiais e o manual `políticas_da_loja.pdf` (v2.1, jun/2025).

Esta ADR é a referência de arquitetura do projeto. Mudanças exigem nova ADR com motivo técnico comprovado.

---

## 1. Princípios

1. O LLM escolhe a ferramenta; o código garante preço, estoque, promoção, parcelamento, frete e acesso a pedidos.
2. Reprodutibilidade antes de sofisticação: `make test` e `make demo` rodam sem chave, sem Docker, sem GPU e sem rede após a instalação.
3. Na dúvida, o agente pergunta ou encaminha para a equipe; nunca inventa.
4. Cada camada é testável isoladamente.
5. Interpretações de IAs não viram regra da loja sem trecho do manual que as sustente; toda interpretação fica registrada em ADR.

## 2. Decisões aprovadas

| ID | Decisão |
| --- | --- |
| D1 | Python 3.11+, dependências travadas com uv |
| D2 | Loop próprio de function calling com contratos Pydantic. **Sem PydanticAI e sem LangGraph** (decisão fechada; ver ADR-001) |
| D3 | `store.db` (SQLite) com os dados da loja, aberto em modo somente leitura (`mode=ro`) no atendimento |
| D4 | `app.db` (SQLite) separado para histórico, sessões, acesso a pedidos, tentativas e encaminhamentos |
| D5 | Ingestão explícita e idempotente com validação Pydantic e relatório `data/processed/QUALITY.md` |
| D6 | Valores monetários em centavos (inteiros), expostos como `Decimal` |
| D7 | Interface `StoreRepository`; `SQLiteRepository` é a implementação oficial |
| D8 | Manual completo no contexto, convertido para `data/processed/policies.md` com marcadores `[§seção · p.página]` |
| D9 | Busca: SQLite FTS5/BM25 + rapidfuzz como baseline; Qdrant local + fastembed só se vencer o benchmark (seção 7) |
| D10 | E-mail e telefone tokenizados antes de chegar ao LLM |
| D11 | Adaptador de LLM OpenAI-compatible; provedor hospedado padrão (pendente, ADR-008); Ollama opcional |
| D12 | Interface principal: CLI com Rich |
| D13 | Firestore apenas como adapter futuro do `StoreRepository`, fora do núcleo obrigatório |

## 3. Ajustes finais aprovados

| # | Ajuste | Especificação |
| --- | --- | --- |
| A1 | Verificação não é autenticação | Dois modos: sessão autenticada **simulada** pelo canal (`--customer <id>`) e confirmação de posse **demonstrativa** (pedido + contato). Produção exige login ou OTP |
| A2 | Devolução sem data real nem canal | `estimated_delivery` nunca é usado como data de recebimento. Faltando data ou canal, retorno `insufficient_information` com a lista do que falta |
| A3 | Totais históricos | Sempre `orders.total_brl`, descrito como "total registrado no pedido". Divergências com os itens vão ao `QUALITY.md` sem atribuir causa |
| A4 | Demo offline sem embeddings | Busca `auto` cai para lexical sem modelo em cache; gravações do demo feitas com backend lexical |
| A5 | Frete em exatamente R$ 500 | Manual cobre "acima" e "abaixo", não o valor exato. Suposição: R$ 500,00 tem frete grátis (interpretação mais favorável ao consumidor, CDC art. 47). Testado em 499,99 / 500,00 / 500,01 |

## 4. Estrutura de arquivos

```
emporio-agent/
├── pyproject.toml · uv.lock · Makefile · .env.example · README.md
├── .github/workflows/ci.yml        # make test + make demo, sem chave e sem rede
├── data/
│   ├── raw/                        # CSVs e PDF oficiais, intocados
│   └── processed/                  # policies.md, QUALITY.md
├── var/                            # gitignored: store.db, app.db, traces/
├── docs/adr/                       # ADR-000 a ADR-011
├── src/emporio/
│   ├── config.py · clock.py · money.py
│   ├── domain/                     # entidades e enums Pydantic
│   ├── ingest/                     # loader, schemas, validação, QUALITY.md, extração do PDF
│   ├── repository/                 # base.py (Protocol), sqlite.py
│   ├── rules/                      # availability, pricing, installments, shipping, returns, hours
│   ├── search/                     # lexical.py, dense.py, hybrid.py, factory.py
│   ├── security/                   # auth_context.py, access.py, pii.py
│   ├── tools/                      # contracts.py, registry.py, impl/
│   ├── agent/                      # loop.py, prompt.py, validator.py, budget.py, session.py
│   ├── llm/                        # base.py, openai_compat.py, scripted.py, replay.py
│   ├── appdb/                      # migrações, histórico, acesso, tentativas, tickets
│   ├── tracing/                    # tracer.py, schema.py, redação
│   └── cli.py                      # chat, trace, ingest
├── evals/                          # search_queries.yaml, golden_set.yaml, runner.py, reports/
├── recordings/                     # gravações do ReplayLLM (JSONL)
├── examples/                       # 5 conversas reais em .md
└── tests/                          # unit/ tools/ security/ agent/ demo/ llm/
```

Regra de dependência: `domain`, `rules`, `security` e `tools` não importam `agent` nem `llm`.

## 5. Contratos das tools

Envelope comum:

```
ToolResult = { ok: bool, data: <modelo> | null, error: { code, message_for_agent } | null }
codes: invalid_input · not_found · ambiguous · access_denied · not_verified · locked · internal_error
```

| Tool | Entrada | Saída principal | Erros e regras |
| --- | --- | --- | --- |
| `search_products` | `query?`, `category?`, `min_price?`, `max_price?`, `only_available=true`, `limit=5` | `ProductSummary[]` (id, nome, categoria, `availability`, estoque, `PriceInfo`), `total_matches`, `search_backend` | filtros exatos em SQL; índice só ordena IDs |
| `get_product` | `product_id` ou `name` | `ProductDetail`: descrição, specs, `PriceInfo`, `inactive_promotions`, `alternatives` | `ambiguous` com candidatos |
| `quote_payment` | `items[{product_id, quantity}]`, `destination_city?` | por item: tabela, final, promoção, elegível a PIX, preço PIX; totais; `installments[{n, valor, valid, reason}]`; `combined_payment_allowed`; `shipping` | itens não vendáveis como `not_purchasable`, fora dos totais |
| `store_status` | — | `now_local`, `is_open`, horário de hoje, próxima abertura | relógio injetável |
| `verify_order_ownership` | `order_id`, `contact_ref` (token) | `granted` com validade | `not_verified` idêntico para inexistente ou contato errado; `locked` após 3 falhas |
| `get_order` | `order_id` | status, data, itens, `total_brl`, pagamento, rastreio, previsão, observação, primeiro nome | `access_denied` sem acesso, exista ou não |
| `check_return_eligibility` | `order_id`, `reason` (arrependimento, defeito, preferência), `received_at?`, `purchase_channel?` | `status`, regra (§), prazo, dias restantes, `missing_information`, condições, `exclusions_to_confirm` | exige acesso; nunca aprova devolução |
| `escalate_to_human` | `category`, `summary` (tokenizado) | `ticket_id`, retorno em 24 horas úteis | grava no `app.db` sem PII |

Modelos de apoio:

- `PriceInfo`: `list_price`, `final_price`, `active_promotion {name, discount_percent}` ou nulo. Preço original e percentual sempre juntos (§6.2).
- `availability`: `available`, `out_of_stock`, `discontinued`, `coming_soon`.
- `ReturnStatus`: `eligible`, `expired`, `not_applicable`, `not_yet_delivered`, `cancelled`, `insufficient_information`.
- `shipping`: `region` (metro, other, unknown), `fee` (nulo fora da região), `free`, `rule_ref`, `modalities`, `special_quote_required`.

Nenhuma saída de tool contém e-mail, telefone ou nome completo de cliente.

## 6. Regras de negócio (Python, com testes)

### Catálogo, preço e pagamento

| Regra | Especificação | Base |
| --- | --- | --- |
| Disponibilidade | `active` + estoque > 0: disponível. `active` + 0: indisponível, com alternativas. `discontinued`: fora do catálogo, mesmo com estoque. `coming_soon`: não vendável | §7.3 |
| Promoção | Só `is_active = 1`. Duas ativas no mesmo produto falham na ingestão | §6.2 |
| PIX | 5% item a item, apenas em itens sem promoção ativa | §3, §6.2 |
| Crédito 1x | Sem parcela mínima | §3 |
| Crédito 2–3x | Parcela mínima de R$ 50 (suposição sobre "exceto abaixo de R$ 50") | §3.1 |
| Crédito 4–6x | Parcela mínima de R$ 80, inclusiva | §3.1 |
| Crédito 7–12x | Parcela mínima de R$ 100, inclusiva. §3.1 prevalece sobre a tabela da §3 (suposição) | §3.1 |
| Pagamento combinado | A partir de R$ 2.000,00, inclusive (suposição, mesma lógica de A5) | §3.1 |
| Frete Grande Campo Grande | Grátis a partir de R$ 500,00; abaixo, R$ 35. Base: subtotal com promoção, antes do PIX. 1 a 3 dias úteis | §5.1, A5 |
| Região metropolitana | No MVP, só a cidade de Campo Grande (suposição) | — |
| Outras cidades | Sem valor: PAC, SEDEX e Jadlog com prazos; cálculo por CEP, peso e dimensões no fechamento | §5.2 |
| Cotação especial | Baterias acústicas, pianos digitais e contrabaixos: `special_quote_required` | §5.2 |

### Pedidos e devoluções

| Regra | Especificação | Base |
| --- | --- | --- |
| Total do pedido | Sempre `orders.total_brl` ("total registrado") | A3 |
| Cancelado | `cancelled`, com a observação do pedido | dados |
| Não entregue | `pending`, `confirmed` ou `shipped`: `not_yet_delivered` | dados |
| Arrependimento | Só compra online, 7 dias corridos após o recebimento. Sem `received_at` ou canal: `insufficient_information`. Presencial: `not_applicable` | §4.1, A2 |
| Defeito | 30 dias corridos após a compra (`order_date`). Depois: `expired`, com orientação de garantia do fabricante e garantia legal de 90 dias a partir do recebimento | §4.2, §8 |
| Preferência | 7 dias, mediante disponibilidade, contados do recebimento (suposição). Sem `received_at`: `insufficient_information` | §4.3 |
| Exclusões | Personalização, venda final e boquilhas não estão nos dados: `exclusions_to_confirm` | §4.4 |
| Previsão de entrega | Só informação de referência, nunca data de recebimento | A2 |

### Atendimento

| Regra | Especificação | Base |
| --- | --- | --- |
| Horário | Seg–sex 9h–18h, sáb 9h–13h, domingo fechado; feriados fora do escopo | §2 |
| Escopo | Só instrumentos; acessórios recusados sem citar lojas parceiras (o manual não lista nenhuma) | §1, §7.1 |
| Contato | (67) 3341-4444 e `contato@emporiodamusica.com.br`; divergências do manual registradas | §1.2 |
| Reclamação | `escalate_to_human`, retorno em 24 horas úteis | §7.3 |

## 7. Busca de produtos (P2 — benchmark obrigatório)

Pipeline: filtros exatos em SQL → ranqueamento pelo backend → índice devolve só IDs → dados vêm do repositório.

Dataset `evals/search_queries.yaml` (15 a 20 consultas): 1/3 por nome ("Takamine GD20", "FG800"), 1/3 por intenção sem palavra em comum ("algo pra criança começar a tocar"), 1/3 ambíguas ("Yamaha elétrico").

Critério, fixado antes da execução:

- Métricas por grupo: recall@5, MRR e latência p50/p95.
- Lexical com recall@5 ≥ 0,8 nas consultas por intenção: fica lexical; Qdrant documentado como evolução.
- Senão: denso (fastembed, CPU) + lexical por RRF. Qdrant adotado se ganhar ≥ 10 pontos de recall@5 nas consultas por intenção sem perder nas por nome.
- Nenhum resultado é presumido. Resultado registrado em `evals/reports/` e na ADR-004.

Backends (`SEARCH_BACKEND`): `lexical`, `hybrid`, `auto` (padrão; híbrido só se o modelo estiver em cache e aprovado no benchmark). O backend usado aparece na resposta da tool e no trace.

## 8. Identidade e privacidade

| Modo | Ativação | Permite |
| --- | --- | --- |
| `simulated_authenticated` | `emporio chat --customer <id>` | Apenas pedidos desse cliente |
| `anonymous` | padrão | Um pedido por vez, após confirmação de posse demonstrativa (pedido + e-mail ou telefone) |

- Acesso em `app.db`: `order_access(session_id UUID, order_id, granted_at, expires_at)`, validade de 15 minutos.
- `get_order` e `check_return_eligibility` checam acesso em Python a cada chamada, independentemente do LLM.
- Pedido inexistente e contato errado: mesma resposta. Nenhuma consulta só pelo nome.
- Falhas contadas por `order_id` e por sessão, persistidas; 3 falhas bloqueiam e encaminham para a equipe.
- Tokenização: e-mails e telefones viram `[EMAIL_1]`, `[PHONE_1]` antes do LLM. Mapa só na memória do processo, isolado por sessão; nunca em prompt nem em disco.
- Resultados de tools delimitados como dados; a defesa contra injeção é a autorização em Python, não filtro de palavras.
- Validador de evidências: R$, estoque, número de pedido e nome de produto citados precisam constar nos resultados de tools do turno. Senão, regenera uma vez; persistindo, resposta segura.
- Orçamento de 16 mil tokens por chamada: histórico truncado primeiro; manual e definições de tools nunca.

## 9. Reprodutibilidade

| Comando | Chave? | Função |
| --- | --- | --- |
| `make setup` | não | `uv sync` |
| `make ingest` | não | `store.db`, `policies.md`, `QUALITY.md`; idempotente; não toca `app.db` |
| `make test` | não | unitários, tools, segurança, agente com ScriptedLLM, demo |
| `make demo` | não | ingere se preciso e roda as 5 conversas com ReplayLLM, **identificadas como simulação** |
| `make chat` | sim | CLI com LLM real |
| `make eval` | sim | golden set com LLM real |
| `make bench` | não* | benchmark de busca (*modelo de embedding baixado uma vez) |

- ReplayLLM: grava respostas do LLM em execuções reais; tools rodam ao vivo; hash dos resultados de tools divergente faz o replay falhar explicitamente.
- O demo não substitui as 5 conversas reais em `examples/`.
- Relógio da demo: `EMPORIO_NOW=2026-03-25T10:00-04:00`.
- CI: `ubuntu-latest`, Python 3.11, sem secrets, `HF_HUB_OFFLINE=1` após `uv sync`.

## 10. Observabilidade

Trace JSONL por turno em `var/traces/`: `session` (hash), `turn`, `iteration` (máx. 5), `tool_calls[]` (nome, args redigidos, status, erro, latência), `llm` (modelo, latência, tokens), `search_backend`, `validator`, `budget`, `auth` (eventos sem contato), `errors[]`. Comando `emporio trace <session>`.

## 11. Testes

**Regras:** frete 499,99 / 500,00 / 500,01, subtotal 510,00 com PIX, outra cidade, bateria acústica · parcelamento 2x 100,00/99,98, 3x 150,00/149,97, 4x 320,00/319,96, 7x 700,00/699,93, 12x 1.200,00/1.199,88, com motivo · combinado 1.999,99/2.000,00 · PIX em carrinho misto (121 com promoção + 81 sem) · GD20 (95) com promoção inativa · produto 90 com 18% · promoção duplicada ativa falha · disponibilidade 96, 113, 136, 130 · devolução sem `received_at`, sem canal, presencial, defeito por `order_date`, pedido 20 cancelado, pedido 13 não entregue · horário sáb 12h59/13h00, domingo · dinheiro.

**Ingestão e tools:** `QUALITY.md` completo · pedido 3 retorna 3.450,00 · escrita em `store.db` falha · nome ambíguo.

**Segurança:** anônimo sem acesso · respostas idênticas · bloqueio após 3 falhas entre sessões · expiração em 15 min · `--customer 3` vê 1 e 19, não o 2 · acesso só por nome negado · injeção em descrição não muda permissões · nenhum contato do CSV em prompts, traces, histórico ou tickets.

**Agente (ScriptedLLM):** 5 iterações · erro de tool estruturado · validador regenera e cai em resposta segura · orçamento preserva manual · fora de escopo sem tool · histórico persiste.

**Demo:** 5 conversas sem chave e sem embeddings · hash divergente falha.

**Golden set (LLM real):** categorias catálogo, preço/pagamento, pedidos, devoluções, loja, fora de escopo, adversariais; acerto de tool, exatidão, recusa; 3 repetições, temperatura 0.

## 12. Critérios de aceite do núcleo

- [ ] `make setup && make test && make demo` verdes na CI, sem chave, Docker, GPU ou rede.
- [ ] Demo funciona sem modelo de embedding em cache.
- [ ] Todos os testes de limite passam, incluindo frete em R$ 500,00.
- [ ] Toda interpretação do manual tem ADR com o trecho de origem.
- [ ] `QUALITY.md` lista todas as inconsistências conhecidas.
- [ ] 100% dos testes de segurança passam.
- [ ] Nenhum contato do `customers.csv` em prompts, traces, histórico ou tickets.
- [ ] Verificação descrita como demonstrativa no README, na CLI e na ADR-005.
- [ ] Golden set: acerto de tool ≥ 90%; exatidão de preço, estoque e status = 100%; recusas corretas = 100%.
- [ ] Benchmark P2 encerrado com resultado medido.
- [ ] 5 conversas reais em `examples/`: catálogo, promoção, pedido protegido, devolução, acesso indevido.
- [ ] README com instruções, arquitetura, decisões, limitações, benchmark e uso de assistentes de IA.
- [ ] Commits incrementais, sem force-push, congelados no prazo.

## 13. Inconsistências conhecidas dos dados

- Telefone (67) 3341-4444 (capa, §1.2) vs (67) 3321-4500 (§7); e-mail com e sem acento.
- Parcelamento: tabela da §3 (mínimo R$ 100) vs faixas da §3.1; trecho ambíguo "exceto abaixo de R$ 50".
- Totais: pedido 3 registra 3.450,00 e os itens somam 3.498,00; pedido 20 registra 1.400,00 e os itens somam 1.488,00.
- Produto 130 `coming_soon` presente nos pedidos 3 e 14.
- Produto 136 `discontinued` com 13 unidades em estoque.
- Categorias 6, 7 e 8 sem produtos.
- Promoções sem datas e duplicadas por produto; apenas 4 ativas (produtos 90, 94, 121, 127).
- Nenhuma data de recebimento nem canal de compra nos pedidos.
- Pedidos `pending` desde mar/2026; pedido 8 `shipped` com previsão vencida.

Inconsistências adicionais, verificadas contra os CSVs em 2026-10-31 (fatos dos dados, não decisões; tratamento em `docs/DECISIONS.md`):

- Parcelamentos registrados fora da §3.1: pedido 9 (6x de R$ 58,32), pedido 16 (6x de R$ 71,65), pedido 18 (12x de R$ 38,32).
- Pedidos pagos via PIX (1, 5, 10, 13, 17) registram o preço de tabela, sem o desconto de 5%.
- Descrição divergente do nome ou das specs: 135 (nome Music Man, descrição Fender Jazz Bass, corpo Alder vs specs Ash), 136 (nome Ibanez, descrição "Precision"), 137 (nome Yamaha, descrição Ibanez 5 cordas vs specs 4), 139 (nome Yamaha, descrição Pearl Export, cascos Poplar vs specs Maple), 140 (nome Pearl, descrição Tama, cascos Birch vs specs Maple), 142 (nome Korg, descrição Roland 88 teclas vs specs 61), 144 (nome Roland, descrição Yamaha). Os produtos 138, 141 e 143 citam outro modelo da mesma marca.
- E-mail `bruno.martins@jmail.com` repetido nos clientes 11 e 43.
- §5.2 cita "contrabaixos" e "pianos digitais": a categoria 2 (Baixos) descreve todos os produtos como "contrabaixo"; a categoria 8 (contrabaixo acústico) está vazia; nenhum produto da categoria 4 tem tipo piano digital (todos `Synthesizer`).
- Promoções inativas com desconto fora das faixas da §6.1: id 1 (Black Friday 10%; manual 15–30%) e id 17 (Aniversário 30%; manual 10–25%). Campanhas sem correspondência no manual: Liquidação de Inverno, Promoção de Páscoa, Oferta Especial, Desconto Exclusivo. Promoção 16 em produto descontinuado (113).
- Chaves de `specs` variam por categoria (violões/ukuleles; guitarras/baixos; baterias; teclados).
- `products.csv` fora de ordem (145 entre 130 e 131); 65 produtos, contra "mais de 300" no manual (§1).
- Nomes dos arquivos com espaços: `desafio_tecnico_ai_eng - <tabela>.csv`.

## 14. ADRs

> Substituída pela seção 16: as ADRs 001–011 foram consolidadas em `docs/DECISIONS.md`. A tabela abaixo fica como histórico.

| ADR | Título | Status |
| --- | --- | --- |
| 000 | Especificação consolidada | Aceita |
| 001 | Loop próprio em vez de PydanticAI ou LangGraph | Aceita |
| 002 | `store.db` somente leitura e `app.db` separado | Aceita |
| 003 | Manual completo no contexto em vez de RAG | Aceita |
| 004 | Busca: baseline lexical e critério para o Qdrant | Pendente do benchmark |
| 005 | Identidade simulada e verificação demonstrativa; login/OTP em produção | Aceita |
| 006 | Tokenização de PII e traces redigidos | Aceita |
| 007 | Interpretações do manual | Aceita (suposições a confirmar) |
| 008 | Provedor e modelo de LLM | Pendente |
| 009 | Reprodutibilidade: uv, ReplayLLM, relógio fixo, fallback lexical | Aceita |
| 010 | Opções rejeitadas | Aceita |
| 011 | Adapter Firestore | Proposta (pós-núcleo) |

Opções rejeitadas (ADR-010): Firebase obrigatório, LangGraph, PydanticAI, RAG das políticas como caminho principal, roteador de intenções paralelo, embeddings via API paga, consulta de pedido por nome, filtro de injeção por palavras-chave, sleep fixo contra timing.

## 15. Pendências

- ~~Prazo exato de entrega.~~ Resolvido na seção 16.
- Provedor e modelo de LLM: provedor configurável via `.env`; modelo padrão registrado em `docs/DECISIONS.md` na fase do agente.
- ~~Confirmação das suposições.~~ Todas confirmadas pelo Daniel em 2026-10-31 (`docs/DECISIONS.md`).

## 16. Decisão de escopo (2026-10-31)

**Motivo:** prazo de "2 dias úteis" a partir de 2026-10-30, com feriado em 2026-11-02. Cenário conservador: entrega em **2026-11-03 23:59 America/Sao_Paulo**; repositório congelado em **2026-11-03 20:00**. Dias de trabalho: 31/10, 01/11, 02/11 e 03/11.

Esta seção prevalece sobre as anteriores onde houver conflito.

| Tratamento | Itens |
| --- | --- |
| **Mantém** | Ingestão com validação e `QUALITY.md`; regras de negócio com testes de limite; acesso a pedidos com verificação, expiração e bloqueio; tokenização de PII com teste de varredura; loop próprio + manual no prompt + as 8 tools; CLI; 5 conversas reais em `examples/`; README; `make test` sem chave na CI |
| **Simplifica** | ADRs 001–011 viram um único `docs/DECISIONS.md` (decisões, suposições, rejeitados); busca só FTS5 + rapidfuzz, com mini-eval de ~10 consultas (`make bench`, sem download); golden set de ~15 casos com 1 repetição (`make eval`); validador de evidências só para valores em R$; traces em JSONL básico |
| **Adia** (README, "o que eu faria com mais tempo") | Qdrant/busca densa e híbrida; ReplayLLM e `make demo`; Firestore; LLM-as-judge; comando `emporio trace` |

Efeito nas seções anteriores:

- §2 D9 e §7: sem backend denso nem `auto`/`hybrid`; o mini-eval mede recall@5 e MRR do backend lexical e o resultado vai para `evals/reports/` e para o README. Nenhum resultado é presumido.
- §3 A4, §9 (`make demo`, ReplayLLM, `recordings/`) e §11 "Demo": fora do escopo.
- §4: sem `search/dense.py`, `search/hybrid.py`, `llm/replay.py`, `recordings/`; decisões em `docs/DECISIONS.md`.
- §8: o validador de evidências checa apenas valores em R$ citados contra os resultados de tools do turno.
- §10: trace JSONL com os mesmos campos essenciais, sem o comando `emporio trace`.
- §12: o primeiro critério passa a ser `make setup && make test` verdes na CI; o critério "demo sem embedding" sai; "toda interpretação tem ADR" passa a "toda interpretação está em `docs/DECISIONS.md` com o trecho do manual"; "benchmark P2" passa a "mini-eval de busca medido".
- LLM (D11): provedor configurável por `LLM_BASE_URL`, `LLM_MODEL` e `LLM_API_KEY` no `.env`. O modelo padrão é escolhido na fase do agente, consultando a documentação oficial.

Esclarecimento (2026-11-01): onde esta ADR diz "sem rede" (§1, §4, §9), leia **sem rede externa**: os testes usam loopback (127.0.0.1). `make demo` e ReplayLLM citados nas seções 1, 4 e 9 foram adiados por esta seção.

Planejamento: no máximo 5 fases, tracer bullet na fase 1, e a última fase (5 conversas reais + README) não pode ser comprimida. Se uma fase atrasar, corta-se refinamento, nunca a entrega.
