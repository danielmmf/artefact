# Empório AI

## What This Is

Agente de atendimento ao cliente da loja fictícia Empório da Música (Campo Grande/MS), em Python 3.11+ com CLI Rich, construído como desafio técnico de AI Engineer da Artefact. O LLM escolhe a ferramenta; o código em Python garante preço, estoque, promoção, parcelamento, frete e acesso a pedidos. Quem consome o resultado é o avaliador técnico, que clona o repositório público e precisa reproduzir os testes sem chave, Docker, GPU ou rede.

Responsável e product owner: Daniel Medeiros. Implementação: Claude Code com GSD. A referência de arquitetura é `docs/adr/ADR-000-especificacao-consolidada.md` (a §16 prevalece sobre as seções anteriores); o registro de decisões e interpretações do manual é `docs/DECISIONS.md` (precedência máxima).

## Core Value

O avaliador clona o repositório público e `make setup && make ingest && make test` rodam verdes sem chave, Docker, GPU ou rede (com chave, `make chat` e `make eval` funcionam), e o agente nunca erra preço, estoque, status nem acesso a pedido: o código decide, o LLM só escolhe a ferramenta.

Métricas de sucesso (ADR-000 §12 revisado pela §16):

- Golden set (`make eval`, LLM real): acerto de tool >= 90%; exatidão de preço, estoque e status = 100%; recusas corretas = 100%.
- 100% dos testes de segurança passam.
- Nenhum contato do `customers.csv` em prompts, traces, histórico ou tickets.
- `make setup && make test` verde na CI (`ubuntu-latest`), sem segredos.

## Requirements

### Validated

(None yet — ship to validate)

### Active

Escopo v1 completo e rastreável em `.planning/REQUIREMENTS.md` (63 requisitos, 15 categorias). Capacidades:

- [ ] Fundação reproduzível: uv, Makefile, CI sem chave, config, relógio injetável, dinheiro em centavos (FND)
- [ ] Ingestão idempotente com validação Pydantic, `store.db` somente leitura, `policies.md` com marcadores e `QUALITY.md` completo (ING, REP)
- [ ] Tracer bullet ponta a ponta: ScriptedLLM → `get_product` real → resposta → trace JSONL (TRC)
- [ ] Regras comerciais com testes de limite: disponibilidade, promoção, PIX por item, parcelamento, pagamento combinado, frete, cotação especial, horário (PRC, DAT, TST)
- [ ] Busca FTS5 + rapidfuzz com mini-eval `make bench` (SRC)
- [ ] Pedidos, devoluções e escalonamento com identidade simulada, verificação demonstrativa, expiração de 15 min, bloqueio após 3 falhas e tokenização de PII com teste de varredura (ORD, SEC)
- [ ] Agente: adaptador OpenAI-compatible, 8 tools registradas, loop próprio (máx. 5 iterações), prompt com manual completo, validador de R$, orçamento de 16k tokens, histórico persistido, `emporio chat` (AGT, TLS, CLI, TRC)
- [ ] Golden set de ~15 casos (`make eval`) (EVL)
- [ ] Entrega: 5 conversas reais em `examples/`, README completo, checagem final de aceite e congelamento do repositório (DOC)

### Out of Scope

Adiado pela ADR-000 §16 (vai para o README em "o que eu faria com mais tempo"):

- Qdrant e busca densa/híbrida — a busca é só FTS5 + rapidfuzz sobre 65 produtos; sem backend `auto`/`hybrid`.
- ReplayLLM, `make demo`, `recordings/` — sem tempo; as 5 conversas reais em `examples/` cobrem a demonstração.
- Adapter Firestore — fora do núcleo; "Firebase/Firestore obrigatório" foi rejeitado (dependência externa sem ganho).
- LLM-as-judge — o golden set mede acerto de tool, exatidão e recusa por regras.
- Comando `emporio trace` — o trace JSONL básico fica em `var/traces/`.
- Login/OTP real — identidade autenticada é simulada pelo canal (`--customer`); verificação por contato é demonstrativa.
- Golden set com múltiplas repetições — uma repetição.
- Validador de evidências para estoque, número de pedido e nome de produto — só valores em R$.

Fora do escopo por decisão de produto:

- Acessórios e lojas parceiras (manual §1, §7.1) — o manual não lista parceiros; acessórios são recusados sem citar lojas.
- Feriados no horário de funcionamento; municípios da região metropolitana além de Campo Grande (S-f).
- Consulta de pedido só por nome de cliente — nomes não identificam ninguém com segurança.

## Context

- **Origem**: ADR-000 consolidou propostas e revisões de Claude, ChatGPT, Gemini, DeepSeek e GLM, validadas contra os CSVs oficiais e o manual `políticas_da_loja.pdf` (v2.1, jun/2025, 8 páginas, texto selecionável).
- **Dados** (`data/raw/`, nunca editados): 6 CSVs `desafio_tecnico_ai_eng - <tabela>.csv` (nomes com espaços) e o PDF do manual. 65 produtos (o manual diz "mais de 300"), 20 pedidos, categorias 6, 7 e 8 sem produtos, apenas 4 promoções ativas (produtos 90, 94, 121, 127).
- **Inconsistências conhecidas dos dados** (fatos, não decisões; todas vão para `data/processed/QUALITY.md`): telefone/e-mail divergentes no manual; totais dos pedidos 3 e 20 divergentes dos itens; produto 130 `coming_soon` em pedidos; produto 136 `discontinued` com 13 unidades; parcelamentos históricos fora da §3.1 (pedidos 9, 16, 18); pedidos PIX sem desconto (1, 5, 10, 13, 17); descrições divergentes de nome/specs (135, 136, 137, 139, 140, 142, 144; e 138, 141, 143 citam outro modelo da mesma marca); e-mail repetido nos clientes 11 e 43; sem data de recebimento nem canal de compra; promoções fora das faixas da §6.1; `products.csv` fora de ordem; nomes de arquivo com espaços.
- **Dados de pedidos x relógio**: os pedidos são de out/2025 a mar/2026. Os testes usam `EMPORIO_NOW=2026-03-25T10:00-04:00`; conversas reais com a data de hoje deixariam quase todo pedido fora de prazo de devolução.
- **Cronograma**: hoje é 2026-10-31 (sábado). Dias de trabalho: 31/10, 01/11, 02/11 (feriado) e 03/11. Entrega até 2026-11-03 23:59 America/Sao_Paulo; repositório congelado em 2026-11-03 20:00.
- **Estado do repositório**: git com 2 commits de documentação (`docs/`, `GSD_KICKOFF.md`, `data/raw/`); `.planning/` ainda não versionado. Não há código de produção. Não reutilizar código do protótipo experimental anterior.
- **Fluxo**: GSD (discutir, planejar, executar, verificar) com commits atômicos. Nesta etapa só há planejamento; código de produção só depois da aprovação do roadmap.

## Constraints

- **Tech stack**: Python 3.11+, uv com lock, CLI com Rich, SQLite (`store.db` somente leitura + `app.db`), Pydantic, FTS5 + rapidfuzz — nenhuma tecnologia fora da stack da ADR-000 entra sem registro em `docs/DECISIONS.md`.
- **Timeline**: prazo 2026-11-03 23:59 America/Sao_Paulo, congelamento 2026-11-03 20:00, no máximo 5 fases, tracer bullet na Fase 1; a última fase (5 conversas reais + README) não pode ser comprimida e, se uma fase atrasar, corta-se refinamento, nunca entrega.
- **Reprodutibilidade**: `make test` sem chave, sem rede, sem Docker e sem GPU; `make bench` sem download; CI `ubuntu-latest`, Python 3.11, sem secrets.
- **Higiene do repositório**: nunca versionar `.env`, `var/`, `.claude/`, `docs/private/`; `.planning/` é versionado; `data/raw/` intocado; commits incrementais, sem force-push.
- **Arquitetura**: `domain`, `rules`, `security` e `tools` não importam `agent` nem `llm`; layout `src/emporio/` da ADR-000 §4 sem os itens removidos pela §16 (`search/dense.py`, `search/hybrid.py`, `llm/replay.py`, `recordings/`, comando `trace`).
- **LLM**: adaptador OpenAI-compatible configurado por `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` em `.env`; os testes nunca precisam da chave; o dono fornece a chave; modelo padrão escolhido na Fase 4 consultando a documentação oficial.
- **Privacidade**: e-mail e telefone tokenizados antes do LLM; mapa só em memória, por sessão; traces, histórico e tickets sem contato (LGPD, manual §9).
- **Idioma**: artefatos de planejamento em pt-BR; identificadores e código em inglês.

<decisions>
## Decisões travadas (LOCKED)

Fonte: `docs/DECISIONS.md` (precedência 0) e `docs/adr/ADR-000-especificacao-consolidada.md` (precedência 1; a §16, "Decisão de escopo (2026-10-31)", prevalece sobre as seções anteriores). Roadmap, planos e código não podem contradizer estas decisões; mudança exige nova decisão registrada em `docs/DECISIONS.md` com motivo técnico comprovado.

### Arquitetura
- **DEC-01 [LOCKED]:** Loop próprio de function calling com contratos Pydantic. Sem PydanticAI e sem LangGraph (8 tools e fluxo linear não justificam framework; autorização, orçamento e validador ficam explícitos e testáveis com ScriptedLLM). (ADR-000 D2)
- **DEC-02 [LOCKED]:** `store.db` (SQLite, `mode=ro` no atendimento) para dados da loja; `app.db` separado para histórico, sessões, acesso a pedidos, tentativas e tickets. O atendimento não altera preço, estoque ou pedido nem por bug nem por injeção. (ADR-000 D3, D4)
- **DEC-03 [LOCKED]:** Manual completo no contexto como `data/processed/policies.md` com marcadores `[§seção · p.página]`, em vez de RAG. (ADR-000 D8)
- **DEC-04 [LOCKED]:** Busca só com SQLite FTS5/BM25 + rapidfuzz; filtros exatos em SQL; o índice só ordena IDs; reprodutível sem rede. Qdrant, denso e híbrido adiados (§16). Mini-eval de ~10 consultas mede recall@5 e MRR; resultado em `evals/reports/` e no README; nenhum resultado presumido. (ADR-000 D9, §7, §16)
- **DEC-05 [LOCKED]:** Identidade autenticada SIMULADA pelo canal (`--customer <id>`); confirmação de posse DEMONSTRATIVA (pedido + e-mail ou telefone); produção exigiria login ou OTP. Declarar como demonstrativa no README e na CLI. Verificação não é autenticação. (ADR-000 A1, §8)
- **DEC-06 [LOCKED]:** E-mail e telefone tokenizados (`[EMAIL_1]`, `[PHONE_1]`) antes do LLM; mapa só em memória, por sessão; traces, histórico e tickets sem contato. (ADR-000 D10, §8)
- **DEC-07 [LOCKED]:** Adaptador OpenAI-compatible; provedor configurável por `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` no `.env`. Modelo padrão PENDENTE, escolhido na fase do agente e registrado em `docs/DECISIONS.md`. (ADR-000 D11, §16)
- **DEC-08 [LOCKED]:** Python 3.11+, uv com lock, relógio injetável (`EMPORIO_NOW`), `make test` sem chave, sem rede e sem Docker. (ADR-000 D1, §9)
- **DEC-09 [LOCKED]:** Valores monetários em centavos inteiros, expostos como `Decimal`. (ADR-000 D6)
- **DEC-10 [LOCKED]:** Posse e acesso checados em Python a cada chamada de `get_order` e `check_return_eligibility`, independentemente do LLM; a defesa contra injeção é a autorização no código, não o prompt.
- **ADR-D5 [LOCKED]:** Ingestão explícita, idempotente, com validação Pydantic e relatório `data/processed/QUALITY.md`; `make ingest` gera `store.db`, `policies.md`, `QUALITY.md` e não toca `app.db`.
- **ADR-D7 [LOCKED]:** Interface `StoreRepository`; `SQLiteRepository` é a implementação oficial.
- **ADR-D12 [LOCKED]:** Interface principal é CLI com Rich; comandos `chat` e `ingest` (sem `trace`).
- **ADR-D13 [LOCKED]:** Firestore só como adapter futuro, fora do núcleo (adiado).

### Princípios (ADR-000 §1, revisados pela §16)
- **PRI-01 [LOCKED]:** O LLM escolhe a ferramenta; o código garante preço, estoque, promoção, parcelamento, frete e acesso a pedidos.
- **PRI-02 [LOCKED]:** Reprodutibilidade antes de sofisticação: `make test` roda sem chave, Docker, GPU ou rede após a instalação.
- **PRI-03 [LOCKED]:** Na dúvida, o agente pergunta ou encaminha para a equipe; nunca inventa. Cada camada é testável isoladamente.
- **PRI-04 [LOCKED]:** Interpretações de IAs não viram regra da loja sem trecho do manual; toda interpretação fica registrada em `docs/DECISIONS.md`.

### Interpretações do manual (todas confirmadas pelo dono em 2026-10-31)
- **S-a [LOCKED]:** Parcelas 2x e 3x exigem parcela >= R$ 50,00; 1x não tem mínimo (§3.1).
- **S-b [LOCKED]:** §3.1 prevalece sobre a tabela da §3: 4–6x >= R$ 80,00; 7–12x >= R$ 100,00, inclusivos.
- **S-c [LOCKED]:** Frete grátis a partir de R$ 500,00, inclusive; abaixo, R$ 35,00 (CDC art. 47, interpretação mais favorável ao consumidor); testado em 499,99 / 500,00 / 500,01.
- **S-d [LOCKED]:** Pagamento combinado permitido a partir de R$ 2.000,00, inclusive; testado em 1.999,99 / 2.000,00.
- **S-e [LOCKED]:** Base do frete = subtotal com promoção, antes do desconto PIX.
- **S-f [LOCKED]:** No MVP, região metropolitana = só a cidade de Campo Grande; demais cidades seguem a §5.2.
- **S-g [LOCKED]:** Troca por preferência contada do recebimento; sem `received_at`, `insufficient_information`.
- **S-h [LOCKED]:** Relógio dos testes `EMPORIO_NOW=2026-03-25T10:00-04:00` (a demonstração foi adiada).
- **S-i [LOCKED]:** Cotação especial só para a lista explícita 135, 136, 137, 138, 139, 140, 141 (sem inferir pela descrição; nenhum produto é piano digital; 136 descontinuado e não vendável); o agente diz "pode exigir cotação especial", nunca que exige.
- **S-j [LOCKED]:** PIX 5% item a item, só em itens sem promoção ativa.
- **S-k [LOCKED]:** O manual não lista lojas parceiras: acessórios são recusados sem citar lojas.
- **S-l [LOCKED]:** Contato oficial informado: (67) 3341-4444 e `contato@emporiodamusica.com.br`; divergências no `QUALITY.md`.

### Tratamento dos dados
- **T-1 [LOCKED]:** Total do pedido sempre `orders.total_brl`, descrito como "total registrado no pedido"; divergência dos itens (pedidos 3 e 20) vai ao `QUALITY.md` sem atribuir causa.
- **T-2 [LOCKED]:** Produtos 135, 136, 137, 139, 140, 142, 144: nome e specs são a fonte de verdade; a descrição NÃO é enviada ao LLM por nenhuma tool (fica só no índice de busca); teste garante que o agente não cita marca vinda dessas descrições.
- **T-3 [LOCKED]:** Parcelamentos históricos fora da §3.1 (pedidos 9, 16, 18): só registro no `QUALITY.md`.
- **T-4 [LOCKED]:** Pedidos PIX sem desconto no total (1, 5, 10, 13, 17): só registro no `QUALITY.md`.
- **T-5 [LOCKED]:** Confirmação de posse compara o contato com o cliente DO PEDIDO, nunca com qualquer cliente que tenha o contato (clientes 11 e 43 compartilham e-mail); teste dedicado.
- **T-6 [LOCKED]:** O loader localiza cada CSV pelo sufixo (`categories`, `customers`, `order_items`, `orders`, `products`, `promotions`), tolerando espaços; ausência ou ambiguidade falha a ingestão.
- **T-7 [LOCKED]:** Duas promoções ativas no mesmo produto falham a ingestão (testado com dado sintético).
- **T-8 [LOCKED]:** `estimated_delivery` nunca vira data de recebimento; devolução sem data ou canal retorna `insufficient_information` com a lista do que falta.
- **T-9 [LOCKED]:** Demais inconsistências da ADR-000 §13 são listadas no `QUALITY.md` gerado pela ingestão.

### Escopo (ADR-000 §16, 2026-10-31)
- **ESC-01 [LOCKED]:** Mantém: ingestão com validação e `QUALITY.md`; regras com testes de limite; acesso a pedidos com verificação, expiração e bloqueio; tokenização de PII com teste de varredura; loop próprio + manual no prompt + 8 tools; CLI; 5 conversas reais em `examples/`; README; `make test` sem chave na CI.
- **ESC-02 [LOCKED]:** Simplifica: `docs/DECISIONS.md` único no lugar das ADRs 001–011; busca só FTS5 + rapidfuzz com mini-eval de ~10 consultas (`make bench`, sem download); golden set de ~15 casos com 1 repetição (`make eval`); validador de evidências só para valores em R$ (regenera uma vez, depois resposta segura); traces JSONL básicos com os campos essenciais.
- **ESC-03 [LOCKED]:** Adia (README, "o que eu faria com mais tempo"): Qdrant/denso/híbrido; ReplayLLM e `make demo`; Firestore; LLM-as-judge; `emporio trace`; login/OTP real; golden set com múltiplas repetições; validador de evidências para estoque, pedido e nome de produto.
- **ESC-04 [LOCKED]:** No máximo 5 fases; tracer bullet na Fase 1; a última fase não pode ser comprimida; se uma fase atrasar, corta-se refinamento, nunca a entrega.

### Opções rejeitadas
- **REJ-01 [LOCKED]:** PydanticAI e LangGraph; Firebase/Firestore obrigatório ("dependência externa sem ganho para o protótipo"); RAG das políticas como caminho principal; roteador de intenções paralelo ao LLM ("duplica a decisão que o function calling já toma"); embeddings via API paga ("quebra a reprodutibilidade sem chave"); consulta de pedido por nome ("nomes não identificam ninguém com segurança"); filtro de injeção por palavras-chave ("contornável; a defesa é a autorização em Python"); sleep fixo contra ataque de timing ("respostas idênticas e bloqueio por tentativas resolvem").

### Em aberto (não travadas; definidas no roadmap)
- Modelo padrão do LLM: escolhido na Fase 4 a partir da documentação oficial e registrado em `docs/DECISIONS.md`.
- Resultado do mini-eval de busca: pendente de medição (Fase 2); nenhum valor presumido.
- Defaults do dono para itens em silêncio nas fontes: o mini-eval mantém 3 grupos de consultas (por nome / por intenção / ambíguas, ~3–4 cada, ~10 no total) medindo recall@5 e MRR; o golden set usa temperature 0 quando o modelo suporta, senão a exceção é documentada.
</decisions>

## Key Decisions

<!-- Decisões que restringem o trabalho futuro. Decisões de arquitetura travadas estão no bloco <decisions> acima. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 5 fases em ordem travada: Fundação+tracer, Regras+busca, Pedidos+segurança, Agente, Entrega | ADR-000 §16 (prazo de 4 dias úteis, congelamento 03/11 20:00); o kickoff de 6 fases foi comprimido | — Pending |
| Fase 5 (Entrega) não comprimível, com início no mais tardar na manhã de 03/11 | Sem exemplos reais e README não há entrega; corta-se refinamento das Fases 1–4, nunca a Fase 5 | — Pending |
| IDs de requisito `CAT-NN` (ex.: `PRC-03`) com referência cruzada aos slugs `REQ-*` do intel | As ferramentas GSD extraem IDs com o padrão `[A-Z][A-Z0-9]*-\d+`; slugs `REQ-rule-pix` não seriam rastreáveis | — Pending |
| Tracer bullet na Fase 1 com loop mínimo + ScriptedLLM + `get_product` real (sem descrição) | Descobrir cedo problemas de integração entre ingestão, tool, loop e trace; o esqueleto evolui na Fase 4, não é descartado | — Pending |
| Tools implementadas como Python puro com envelope `ToolResult` desde a Fase 1; registry para o LLM só na Fase 4 | Mantém a regra de dependência (tools não importam agent/llm) e cada camada testável isolada | — Pending |
| `make bench` mantém 3 grupos de consultas (nome / intenção / ambíguas), ~10 no total | Default do dono; permite ver onde o backend lexical falha, sem presumir resultado | — Pending (medição na Fase 2) |
| Golden set com temperature 0 quando o modelo suporta; senão, exceção documentada | Default do dono; reduz variância com 1 repetição | — Pending |
| Modelo padrão do LLM escolhido na Fase 4 | Depende da chave do dono e da documentação oficial do provedor | — Pending |

## Evolution

Este documento evolui nas transições de fase e de milestone.

**Após cada fase:**
1. Requisitos invalidados? Mover para Out of Scope com o motivo.
2. Requisitos validados? Mover para Validated com a referência da fase.
3. Novos requisitos? Adicionar a Active.
4. Decisões a registrar? Adicionar a Key Decisions (e em `docs/DECISIONS.md`).
5. "What This Is" ainda descreve a realidade? Atualizar se houve desvio.

**Após o milestone (entrega de 03/11):** revisão completa das seções, checagem do Core Value e auditoria do Out of Scope.

---
*Last updated: 2026-10-31 after roadmap creation (ingest from ADR-000 and docs/DECISIONS.md)*
