---
gsd_state_version: '1.0'
status: planning
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-31)

**Core value:** O avaliador clona o repositório público e `make setup && make ingest && make test` rodam verdes sem chave, Docker, GPU ou rede (com chave, `make chat` e `make eval`), e o agente nunca erra preço, estoque, status nem acesso a pedido.
**Current focus:** Phase 1 — Fundação e tracer bullet

## Current Position

Phase: 1 of 5 (Fundação e tracer bullet)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-10-31 — Roadmap criado (5 fases, 63/63 requisitos mapeados)

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: -
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisões de arquitetura travadas estão no bloco `<decisions>` de PROJECT.md; a tabela Key Decisions tem as de roadmap.

- [Roadmap]: 5 fases em ordem travada; Fase 5 não comprimível, com início no mais tardar na manhã de 03/11; congelamento 03/11 20:00.
- [Roadmap]: IDs de requisito `CAT-NN` com referência aos slugs `REQ-*` do intel (as ferramentas GSD só rastreiam o padrão `CAT-NN`).
- [Roadmap]: defaults do dono — mini-eval com 3 grupos (~10 consultas, recall@5 e MRR); golden set com temperature 0 quando suportado.
- [ADR-000 §16]: demo/ReplayLLM, Qdrant/denso, Firestore, LLM-as-judge e `emporio trace` adiados para o README.

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 4] O dono precisa fornecer a chave do LLM antes de 02/11; o modelo padrão ainda não foi escolhido (registrar em `docs/DECISIONS.md`). Fase de maior risco de calendário (15 requisitos).
- [Phase 4] Teste "dinheiro" (ADR-000 §11): o manual §3 só lista PIX, débito, crédito e boleto. Tratado como caso de agente (ScriptedLLM + golden set), sem regra nova; confirmar a interpretação com o dono.
- [Phase 5] Relógio dos exemplos: com a data real (nov/2026) quase todo pedido estaria fora de prazo; gravar com `EMPORIO_NOW` fixo (S-h) e declarar o relógio no cabeçalho de cada exemplo.
- [Phase 5] Exemplos com pedido protegido têm e-mail digitado pelo usuário: exportar do histórico tokenizado e varrer `examples/` contra o `customers.csv`.
- [Phase 1] Dependências fora da stack inicial (extração de PDF, rapidfuzz, rich, cliente HTTP/openai, pytest) devem ser registradas em `docs/DECISIONS.md` ("nenhuma tecnologia fora da stack sem registro").
- [Phase 1] A extração do PDF precisa gerar `policies.md` determinístico (idempotência) com marcadores §/página; o PDF é texto selecionável de 8 páginas.

## Deferred Items

Itens reconhecidos e adiados pela ADR-000 §16 (vão ao README em "o que eu faria com mais tempo"):

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| Busca | Qdrant e busca densa/híbrida | Deferred | 2026-10-31 | v1 |
| Demo | ReplayLLM, `make demo`, `recordings/` | Deferred | 2026-10-31 | v1 |
| Persistência | Adapter Firestore | Deferred | 2026-10-31 | v1 |
| Avaliação | LLM-as-judge; golden set com várias repetições | Deferred | 2026-10-31 | v1 |
| Observabilidade | Comando `emporio trace` | Deferred | 2026-10-31 | v1 |
| Identidade | Login/OTP real | Deferred | 2026-10-31 | v1 |
| Validação | Validador de evidências para estoque, pedido e nome de produto | Deferred | 2026-10-31 | v1 |

## Session Continuity

Last session: 2026-10-31
Stopped at: Roadmap e requisitos escritos; aguardando aprovação do dono antes de planejar a Fase 1
Resume file: None
