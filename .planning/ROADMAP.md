# Roadmap: Empório AI

## Overview

Agente de atendimento da Empório da Música (desafio técnico AI Engineer, Artefact), entregue em 5 fases numa janela de 4 dias úteis (31/10 a 03/11/2026; congelamento em 03/11 às 20:00). A ordem é travada pela ADR-000 §16: a Fase 1 monta a fundação reproduzível e já atravessa todas as camadas com um tracer bullet; a Fase 2 entrega as regras comerciais e a busca (tudo em Python testado, sem LLM); a Fase 3 entrega pedidos, devoluções e segurança; a Fase 4 junta tudo no agente com LLM real e mede o golden set; a Fase 5 (que não pode ser comprimida) produz as 5 conversas reais, o README e o aceite final. Se uma fase atrasar, corta-se refinamento da própria fase (linha de corte), nunca a entrega da Fase 5.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Fundação e tracer bullet** - uv, Makefile, CI sem chave, ingestão validada, `store.db` somente leitura, `policies.md`, `QUALITY.md` e uma conversa mínima de ponta a ponta
- [ ] **Phase 2: Regras de negócio e ferramentas de catálogo** - disponibilidade, promoção, PIX, parcelamento, frete, horário e cotação especial; `search_products`, `get_product`, `quote_payment`, `store_status`; mini-eval `make bench`
- [ ] **Phase 3: Pedidos e segurança** - `app.db`, identidade, posse demonstrativa, acesso de 15 min, bloqueio após 3 falhas, `get_order`, devoluções, escalonamento e tokenização de PII com varredura
- [ ] **Phase 4: Agente** - adaptador OpenAI-compatible, registry das 8 tools, loop próprio, prompt com o manual, validador de R$, orçamento de 16k, histórico, `emporio chat` e golden set (`make eval`)
- [ ] **Phase 5: Entrega** - 5 conversas reais em `examples/`, README, checagem final de aceite e congelamento às 20:00

## Calendário e linhas de corte

2026-10-31 é sábado; 02/11 é feriado. As janelas são alvos de calendário, não estimativas de esforço. Fases 2 e 3 não têm dependência técnica entre si (a ordem 2 → 3 é a travada pelo dono; podem inverter se isso desbloquear o calendário). A Fase 4 precisa das 8 tools das Fases 2 e 3. A Fase 5 começa na manhã de 03/11 mesmo que a Fase 4 tenha sido cortada pela linha de corte.

| Fase | Janela alvo | Linha de corte (cortado primeiro se a fase atrasar) |
|------|-------------|------------------------------------------------------|
| 1 | 31/10 (sáb) | lint/type-check na CI; formatação do `policies.md` além dos marcadores; campos do trace além do mínimo |
| 2 | 01/11 (dom), manhã até início da tarde | ajuste fino do rapidfuzz; heurística de `alternatives`; polimento do relatório do bench |
| 3 | 01/11 (dom), tarde e noite (transborda no máximo até a manhã de 02/11) | texto de `message_for_agent`/`conditions`; riqueza do ticket; framework de migração do `app.db` |
| 4 | 02/11 (seg, feriado), dia inteiro e noite; chave do dono necessária já no início | polimento Rich da CLI; tamanho do golden set (mín. 10–12, todas as 7 categorias); contagem exata de tokens; campos opcionais do trace; iterações extras de ajuste de prompt |
| 5 | 03/11 (ter): início no mais tardar pela manhã; congelamento 20:00 | nenhuma (não comprimível) |

Portões de calendário:
- Fim de 01/11: Fases 1 a 3 fechadas (alvo).
- Fim de 02/11: Fase 4 fechada, com `make eval` rodado pelo menos uma vez contra o LLM real (alvo).
- 03/11, manhã: a Fase 5 começa de qualquer jeito. O que sobrar da Fase 4 é cortado pela linha de corte; nunca se rouba tempo da Fase 5.
- 03/11 20:00: congelamento. Depois disso só logística de envio (sem commits) até 23:59.
- Regra de honestidade: se o golden set não atingir as metas na janela, o resultado medido vai para o README como está; metas e casos não são alterados para "passar".

## Phase Details

### Phase 1: Fundação e tracer bullet
**Goal**: O avaliador clona, instala e ingere os dados oficiais com `make setup && make ingest && make test` sem chave, e uma conversa mínima atravessa todas as camadas (ScriptedLLM → `get_product` real → resposta → trace JSONL), expondo cedo problemas de integração.
**Depends on**: Nothing (first phase)
**Requirements**: FND-01, FND-02, FND-03, FND-04, ING-01, ING-02, ING-03, ING-04, ING-05, REP-01, REP-02, TRC-01, TLS-01, CLI-01
**Success Criteria** (what must be TRUE):
  1. Em um clone limpo, `make setup && make ingest && make test` terminam verdes sem chave, Docker, GPU ou rede, e a CI do GitHub Actions (`ubuntu-latest`, Python 3.11, sem secrets) roda `make setup && make test` verde.
  2. `make ingest` é idempotente (duas execuções geram `store.db`, `policies.md` e `QUALITY.md` equivalentes), não altera `data/raw/` nem toca `app.db`; o loader acha cada CSV pelo sufixo mesmo com espaços no nome (T-6) e falha com CSV ausente ou ambíguo; duas promoções ativas no mesmo produto (dado sintético) falham a ingestão (T-7).
  3. `data/processed/policies.md` reproduz o manual v2.1 completo (§1 a §10, páginas 1 a 8) com marcadores `[§seção · p.página]`, e `data/processed/QUALITY.md` lista todas as inconsistências conhecidas (ADR-000 §13 mais a lista adicional de 2026-10-31) sem atribuir causa.
  4. Todo acesso a dados da loja passa por `StoreRepository`/`SQLiteRepository` sobre `store.db` aberto em `mode=ro`: uma escrita falha; valores monetários são centavos inteiros expostos como `Decimal`.
  5. Um teste de tracer bullet faz um ScriptedLLM pedir `get_product`, executa a tool real (envelope `ToolResult`) sobre o `store.db` ingerido, devolve a resposta final e grava um trace JSONL básico em `var/traces/`, sem chave.
**Plans**: TBD
**Janela alvo**: 31/10 (sábado).
**Linha de corte**: (1) lint/type-check como gate de CI (a CI roda só `make setup && make test`); (2) formatação do `policies.md` além dos marcadores e do texto completo (tabelas como texto simples); (3) campos do trace além do mínimo (hash da sessão, turno, `tool_calls`, status, latência), completados na Fase 4. Nunca cortar: loader por sufixo (T-6), conteúdo completo do `QUALITY.md`, `store.db` somente leitura, tracer bullet, CI verde.
**Testes a adicionar** (ADR-000 §11 revisado, mais itens do dono):
- Ingestão: idempotência; hash de `data/raw/` inalterado; Pydantic rejeita linha inválida; `policies.md` com marcadores para §1–§10 e páginas 1–8.
- `QUALITY.md` completo: checagem programática de cada item do §13 e da lista adicional (§11 "Ingestão e tools").
- T-6: loader por sufixo (com espaços, sem espaços, arquivo ausente falha, dois candidatos falha).
- T-7 / §11 "promoção duplicada ativa falha": dado sintético.
- §11 "escrita em `store.db` falha".
- Unitários de `money` (centavos ↔ `Decimal`), `clock` (`EMPORIO_NOW`) e `config`.
- Arquitetura: `tools`, `rules`, `domain`, `security` não importam `agent`/`llm`.
- Tracer bullet ponta a ponta (ScriptedLLM → `get_product` → resposta → trace).

### Phase 2: Regras de negócio e ferramentas de catálogo
**Goal**: Todas as regras comerciais de disponibilidade, promoção, PIX, parcelamento, pagamento combinado, frete e horário estão em Python testado nos limites, expostas por `search_products`, `get_product`, `quote_payment` e `store_status`, com a busca lexical medida por um mini-eval reproduzível.
**Depends on**: Phase 1
**Requirements**: TLS-02, TLS-03, TLS-04, TLS-05, DAT-01, PRC-01, PRC-02, PRC-03, PRC-04, PRC-05, PRC-06, PRC-07, PRC-08, SRC-01, SRC-02, TST-01
**Success Criteria** (what must be TRUE):
  1. `quote_payment` obedece todos os limites: frete R$ 35,00 / grátis / grátis em 499,99 / 500,00 / 500,01; subtotal 510,00 com PIX tem frete grátis; outra cidade vem sem valor e com PAC, SEDEX e Jadlog; parcelas 2x 100,00/99,98, 3x 150,00/149,97, 4x 320,00/319,96, 7x 700,00/699,93 e 12x 1.200,00/1.199,88 retornam `valid` e `reason` corretos; combinado negado em 1.999,99 e permitido em 2.000,00; carrinho misto (121 com promoção + 81 sem) aplica PIX só no 81.
  2. Disponibilidade e promoção respondem certo: 96, 113, 136 e 130 trazem o status correto (indisponível com alternativas, descontinuado, `coming_soon`) e itens não vendáveis ficam `not_purchasable` fora dos totais; o GD20 (95) mostra preço de tabela e lista a promoção inativa à parte; o produto 90 mostra 18% junto do preço original.
  3. `get_product` nunca devolve descrição para 135, 136, 137, 139, 140, 142 e 144 (T-2), e `search_products` também não; nome ambíguo retorna `ambiguous` com candidatos; os produtos 135 a 141 (e só eles) vêm com `special_quote_required` e o texto permite dizer "pode exigir cotação especial" (S-i).
  4. `search_products` (FTS5/BM25 + rapidfuzz) aplica filtros exatos em SQL, o índice só ordena IDs, e a resposta informa `search_backend`; `store_status` com relógio injetado responde sábado 12:59 aberto, 13:00 fechado e domingo fechado.
  5. `make bench` roda sem nenhum download e grava recall@5 e MRR de ~10 consultas (por nome / por intenção / ambíguas) em `evals/reports/`, sem resultado presumido.
**Plans**: TBD
**Janela alvo**: 01/11 (domingo), manhã até o início da tarde.
**Linha de corte**: (1) ajuste fino do rapidfuzz: FTS5 como base e um fallback fuzzy simples nos tokens do nome, sem afinar por consulta; (2) `alternatives` do `get_product` com heurística mínima (mesma categoria, disponível, preço mais próximo); (3) bench com ~10 consultas medidas como estão, sem iterar para melhorar o recall e sem latência, relatório em Markdown/JSON simples. Nunca cortar: nenhum teste de limite (TST-01), a lista S-i exata, a retenção da descrição (T-2), o `make bench` existir e medir.
**Testes a adicionar** (ADR-000 §11 revisado, mais itens do dono):
- §11 Regras: frete 499,99/500,00/500,01; subtotal 510,00 com PIX; outra cidade; bateria acústica; parcelamento 2x/3x/4x/7x/12x com motivo; combinado 1.999,99/2.000,00; PIX em carrinho misto; GD20 (95) com promoção inativa; produto 90 com 18%; disponibilidade 96, 113, 136, 130; horário sáb 12h59/13h00 e domingo.
- S-i: lista exata 135–141 com `special_quote_required`, produto 143 e demais sem a flag; 136 não vendável.
- §11 Ingestão e tools: nome ambíguo devolve `ambiguous` com candidatos.
- T-2 (nível de tool): descrição ausente para 135, 136, 137, 139, 140, 142, 144 em `get_product` e `search_products`; a descrição segue indexada na busca.
- Busca: filtros exatos em SQL; `search_backend` presente; `make bench` produz `evals/reports/` com recall@5 e MRR (§12 "mini-eval medido").

### Phase 3: Pedidos e segurança
**Goal**: Pedidos e devoluções só são acessíveis a quem comprovou posse (ou está autenticado pelo canal simulado), por 15 minutos, com bloqueio após 3 falhas, e nenhum contato de cliente chega ao LLM, a traces, ao histórico ou a tickets.
**Depends on**: Phase 1
**Requirements**: ORD-01, ORD-02, ORD-03, ORD-04, SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06, SEC-07, SEC-08, TST-02
**Success Criteria** (what must be TRUE):
  1. No modo anônimo, `get_order` e `check_return_eligibility` respondem `access_denied` sem posse confirmada; `verify_order_ownership` (pedido + e-mail ou telefone, comparado com o cliente DO PEDIDO) concede acesso; pedido inexistente e contato errado dão a mesma resposta `not_verified`; consulta só por nome é negada; o e-mail repetido dos clientes 11 e 43 não abre o pedido do outro (T-5).
  2. No modo `simulated_authenticated` com cliente 3, os pedidos 1 e 19 são visíveis e o 2 não; o acesso concedido expira em 15 minutos (relógio injetado); 3 falhas de verificação num `order_id` bloqueiam (`locked`) e escalam, e o bloqueio persiste numa sessão nova.
  3. `get_order` devolve o total registrado (pedido 3 = R$ 3.450,00, não 3.498,00) e só o primeiro nome do cliente; `check_return_eligibility` cobre os seis `ReturnStatus` (sem `received_at`, sem canal, presencial, defeito por `order_date`, pedido 20 cancelado, pedido 13 não entregue), lista `missing_information` e `exclusions_to_confirm` e nunca aprova devolução.
  4. `escalate_to_human` grava ticket no `app.db` sem PII e informa retorno em 24 horas úteis.
  5. E-mails e telefones viram `[EMAIL_n]`/`[PHONE_n]` antes do LLM, com o mapa só em memória por sessão; o teste de varredura não encontra nenhum contato do `customers.csv` em `app.db`, tickets, traces e saídas de tools; um pedido de acesso vindo de texto injetado continua negado por autorização em Python.
**Plans**: TBD
**Janela alvo**: 01/11 (domingo), tarde e noite; pode transbordar até a manhã de 02/11, nunca além, porque a Fase 4 ocupa o dia.
**Linha de corte**: (1) texto de `message_for_agent` e `conditions` das devoluções (mantém os campos estruturados); (2) ticket mínimo (categoria, resumo tokenizado, horário; sem fluxo de status); (3) `app.db` com `CREATE TABLE IF NOT EXISTS` e versão de esquema, sem framework de migração. Nunca cortar: expiração de 15 min, bloqueio após 3 falhas entre sessões, respostas idênticas, teste T-5, tokenização, varredura de PII.
**Testes a adicionar** (ADR-000 §11 revisado, mais itens do dono):
- §11 Regras (devoluções): sem `received_at`, sem canal, presencial, defeito por `order_date`, pedido 20 cancelado, pedido 13 não entregue; preferência sem `received_at` → `insufficient_information` (T-8).
- §11 Ingestão e tools: pedido 3 retorna R$ 3.450,00.
- §11 Segurança: anônimo sem acesso; respostas idênticas; bloqueio após 3 falhas entre sessões; expiração em 15 min; `--customer 3` vê 1 e 19, não o 2 (via contexto de sessão; flag da CLI na Fase 4); acesso só por nome negado; injeção em descrição não muda permissões; nenhum contato do CSV em tickets, `app.db`, traces e saídas de tools.
- T-5: contato do cliente 11 não abre pedido do cliente 43 e vice-versa (e-mail `bruno.martins@jmail.com` repetido).
- Nenhuma saída de tool com e-mail, telefone ou nome completo.
- Tokenizador: round-trip em processo, isolamento entre sessões, mapa fora de disco.

### Phase 4: Agente
**Goal**: Um cliente conversa em `emporio chat` com um agente que usa as 8 tools via LLM real, nunca cita valor em R$ sem evidência, respeita escopo e privacidade, e tem seu desempenho medido pelo golden set.
**Depends on**: Phase 2, Phase 3
**Requirements**: TRC-02, TLS-06, AGT-01, AGT-02, AGT-03, AGT-04, AGT-05, AGT-06, AGT-07, AGT-08, AGT-09, AGT-10, EVL-01, CLI-02, CLI-03
**Success Criteria** (what must be TRUE):
  1. `make chat` / `emporio chat` (com `--customer <id>` opcional) conduz uma conversa com LLM real configurado só por `LLM_BASE_URL`, `LLM_MODEL` e `LLM_API_KEY` no `.env`; a CLI declara que a verificação é demonstrativa; o modelo padrão, escolhido na documentação oficial, está registrado em `docs/DECISIONS.md`.
  2. As 8 tools são oferecidas ao LLM pelo registry com contratos Pydantic; o loop próprio para em 5 iterações, devolve erros estruturados de tool ao LLM, entrega resultados como dados delimitados, trata pedido fora de escopo (acessório, "dinheiro") sem chamar tool e sem citar lojas parceiras, e persiste o histórico (tokenizado) no `app.db`.
  3. Um valor em R$ ausente dos resultados de tool do turno faz o agente regenerar uma vez e, persistindo, cair em resposta segura; o orçamento de 16k tokens trunca o histórico primeiro e nunca o manual nem as definições de tools (testes com ScriptedLLM).
  4. `make test` (sem chave) inclui a suíte do agente: o prompt enviado ao LLM nunca contém marca vinda de descrição divergente (T-2), a redação de S-i é "pode exigir cotação especial", a varredura de PII cobre prompts, histórico e traces reais do agente, e injeção em descrição não muda permissões.
  5. `make eval` roda o golden set de ~15 casos (7 categorias, 1 repetição, temperature 0 quando suportado) contra o LLM real e grava o relatório em `evals/reports/` com acerto de tool >= 90%, exatidão de preço/estoque/status = 100% e recusas corretas = 100%; cada turno gera um trace JSONL completo sem contato.
**Plans**: TBD
**Janela alvo**: 02/11 (segunda, feriado), dia inteiro e noite. O dono fornece a chave antes de começar (necessária para escolher o modelo e fazer um smoke test real cedo).
**Linha de corte**: (1) polimento Rich da CLI (fica funcional, com `--customer` e o aviso de verificação demonstrativa); (2) golden set de ~15 pode cair para 10–12 casos, mantendo as 7 categorias com pelo menos um adversarial e um fora de escopo, sem mudar as metas; (3) contagem de tokens aproximada e truncamento do histórico por descarte dos turnos mais antigos; (4) campos opcionais do trace (detalhe de `budget` e `validator`); (5) iterações extras de ajuste de prompt além do necessário para a primeira medição honesta; (6) escolha do modelo padrão sem comparar vários candidatos. Nunca cortar: 8 tools no registry, loop com limite de 5, validador de R$, tokenização antes do LLM, histórico persistido, `emporio chat`, `make eval` existir e rodar.
**Testes a adicionar** (ADR-000 §11 revisado, mais itens do dono):
- §11 Agente (ScriptedLLM): 5 iterações; erro de tool estruturado; validador regenera e cai em resposta segura; orçamento preserva o manual; fora de escopo sem tool; histórico persiste.
- T-2 no agente: com ScriptedLLM, o conteúdo enviado ao LLM após `get_product`/`search_products` de 135 etc. não contém a marca da descrição divergente (ex.: "Fender Jazz Bass" para o 135); caso no golden set com LLM real.
- S-i no agente: a resposta para produto da lista usa "pode exigir cotação especial", nunca "exige".
- §11 Regras "dinheiro": pergunta sobre pagamento em dinheiro não inventa regra (manual §3 lista PIX, débito, crédito e boleto); ScriptedLLM + caso no golden set. Interpretação a confirmar com o dono.
- §11 Segurança (extensão): varredura de PII sobre prompts, histórico e traces do agente; injeção em descrição não muda permissões no nível do agente; `--customer` ligado à CLI.
- Registry: o schema de cada uma das 8 tools é gerado dos contratos Pydantic e o despacho devolve `ToolResult`.
- Golden set (§11): ~15 casos nas categorias catálogo, preço/pagamento, pedidos, devoluções, loja, fora de escopo e adversariais; metas do §12.

### Phase 5: Entrega
**Goal**: O repositório público entrega o que o avaliador precisa para julgar o trabalho: 5 conversas reais, README honesto sobre decisões e limitações, aceite final verificado contra a ADR-000 §12 revisada pela §16, e congelamento no prazo.
**Depends on**: Phase 4
**Requirements**: DOC-01, DOC-02, DOC-03, DOC-04, DOC-05
**Success Criteria** (what must be TRUE):
  1. `examples/` tem 5 conversas REAIS em `.md` (catálogo, promoção, consulta protegida de pedido, devolução, tentativa de acesso indevido), geradas com `emporio chat` e LLM real (não simuladas), cada uma declarando modelo e relógio usados, sem contato real de cliente.
  2. O README traz instruções (`make setup/ingest/test/chat/eval/bench`), arquitetura, decisões, limitações, resultados medidos do mini-eval de busca e do golden set, a declaração de que a verificação é demonstrativa, o uso de assistentes de IA (revisão multi-IA da arquitetura + Claude Code com GSD) e "o que eu faria com mais tempo" com todos os itens adiados.
  3. A checagem final contra ADR-000 §12 revisada pela §16 está feita critério a critério com evidência registrada; num clone limpo, `make setup && make ingest && make test` ficam verdes sem chave nem rede e a CI do último commit está verde.
  4. `docs/DECISIONS.md` está completo (S-a..S-l com trecho do manual, T-1..T-9, modelo padrão, defaults do mini-eval e do golden set, dependências novas); o repositório tem commits incrementais, sem force-push, sem `.env`, `var/`, `.claude/` ou `docs/private/` versionados, e está congelado em 03/11 às 20:00.
**Plans**: TBD
**Janela alvo**: 03/11 (terça): começa pela manhã, congelamento 20:00. Trechos do README que não dependem de medições (arquitetura, decisões, limitações, lista de adiados, uso de IA) podem ser adiantados em tempos mortos das Fases 3 e 4, mas são entregues e verificados aqui.
**Linha de corte**: nenhuma; a fase não é comprimível. Se o tempo apertar, a ordem de prioridade interna é: (1) as 5 conversas reais, (2) README com todas as seções obrigatórias, (3) clone limpo + CI verde, (4) registro da checagem de aceite.
**Testes a adicionar** (ADR-000 §12 revisado):
- Verificação de clone limpo (diretório novo): `make setup && make ingest && make test` verdes offline e sem chave.
- Varredura de contato do `customers.csv` também sobre `examples/` (adição do roadmapper, custo baixo: os exemplos devem ser exportados do histórico já tokenizado).
- Checagem de higiene: `git ls-files` não lista `.env`, `var/`, `.claude/` nem `docs/private/`.
- Checagem de conteúdo do README (seções obrigatórias, declaração de verificação demonstrativa, lista de adiados completa).

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Fundação e tracer bullet | 0/TBD | Not started | - |
| 2. Regras de negócio e ferramentas de catálogo | 0/TBD | Not started | - |
| 3. Pedidos e segurança | 0/TBD | Not started | - |
| 4. Agente | 0/TBD | Not started | - |
| 5. Entrega | 0/TBD | Not started | - |
