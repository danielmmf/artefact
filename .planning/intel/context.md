# Context (synthesized intel)

No DOC-type documents exist in the ingest set. This file holds explanatory context from the ADRs that is not a decision, requirement or constraint. Source attribution on every topic.

---

## Topic: Project purpose
- source: docs/adr/ADR-000-especificacao-consolidada.md (title, header)
- ADR-000 is "a referência de arquitetura do projeto"; "Mudanças exigem nova ADR com motivo técnico comprovado." Inputs were proposals and reviews by Claude, ChatGPT, Gemini, DeepSeek and GLM, validated against the official CSVs and the manual `políticas_da_loja.pdf` (v2.1, jun/2025). Project: Agente Empório da Música (customer service agent for a music store). Owner: Daniel Medeiros.

## Topic: Scope-decision rationale (2026-10-31)
- source: docs/adr/ADR-000-especificacao-consolidada.md §16
- Reason: deadline of "2 dias úteis" from 2026-10-30, with a holiday on 2026-11-02. Conservative scenario: delivery 2026-11-03 23:59 America/Sao_Paulo; repository frozen 2026-11-03 20:00.

## Topic: Supersession order between the two ADRs
- source: docs/DECISIONS.md (intro); docs/adr/ADR-000-especificacao-consolidada.md §14, §16
- DECISIONS.md is the "Registro único que substitui as ADRs 001–011 (decisão de escopo, ADR-000 §16)". The full specification stays in ADR-000, DECISIONS.md records the why of each choice and every interpretation of the manual. ADR-000 §14 table (ADRs 000-011 and statuses) is kept as history only: 004 "Pendente do benchmark", 007 "Aceita (suposições a confirmar)", 008 "Pendente", 011 "Proposta (pós-núcleo)".

## Topic: Known data inconsistencies (ADR-000 §13)
- source: docs/adr/ADR-000-especificacao-consolidada.md §13; docs/DECISIONS.md T-1 to T-9
- Phone (67) 3341-4444 (cover, §1.2) vs (67) 3321-4500 (§7); e-mail with and without accent.
- Installments: §3 table (minimum R$ 100) vs §3.1 ranges; ambiguous "exceto abaixo de R$ 50".
- Totals: order 3 records 3.450,00, items sum 3.498,00; order 20 records 1.400,00, items sum 1.488,00.
- Product 130 `coming_soon` appears in orders 3 and 14. Product 136 `discontinued` with 13 units in stock.
- Categories 6, 7, 8 have no products.
- Promotions without dates and duplicated per product; only 4 active (products 90, 94, 121, 127).
- No receipt date nor purchase channel in orders. Orders `pending` since Mar/2026; order 8 `shipped` with overdue estimate.
- Installments outside §3.1: order 9 (6x R$ 58,32), order 16 (6x R$ 71,65), order 18 (12x R$ 38,32).
- PIX orders (1, 5, 10, 13, 17) record list price without the 5% discount.
- Description diverges from name/specs: 135 (name Music Man, description Fender Jazz Bass, body Alder vs specs Ash), 136 (name Ibanez, description "Precision"), 137 (name Yamaha, description Ibanez 5 strings vs specs 4), 139 (name Yamaha, description Pearl Export, shells Poplar vs Maple), 140 (name Pearl, description Tama, shells Birch vs Maple), 142 (name Korg, description Roland 88 keys vs specs 61), 144 (name Roland, description Yamaha). Products 138, 141, 143 cite another model of the same brand.
- E-mail `bruno.martins@jmail.com` repeated on customers 11 and 43.
- §5.2 cites "contrabaixos" and "pianos digitais": category 2 (Baixos) describes all products as "contrabaixo"; category 8 (acoustic bass) is empty; no category 4 product is a digital piano (all `Synthesizer`).
- Inactive promotions outside §6.1 ranges: id 1 (Black Friday 10%; manual 15-30%) and id 17 (Aniversário 30%; manual 10-25%). Campaigns with no manual counterpart: Liquidação de Inverno, Promoção de Páscoa, Oferta Especial, Desconto Exclusivo. Promotion 16 on discontinued product 113.
- `specs` keys vary by category (acoustic guitars/ukuleles; electric guitars/basses; drums; keyboards).
- `products.csv` out of order (145 between 130 and 131); 65 products against "mais de 300" in manual §1.
- File names with spaces: `desafio_tecnico_ai_eng - <tabela>.csv`.
- Note from the source: these are facts of the data, not decisions; treatment is in docs/DECISIONS.md.

## Topic: Pending items
- source: docs/adr/ADR-000-especificacao-consolidada.md §15; docs/DECISIONS.md DEC-04, DEC-07
- Open: default LLM provider/model (provider configurable via `.env`; default model recorded in DECISIONS.md in the agent phase). Search mini-eval result pending measurement.
- Resolved: exact deadline (§16); confirmation of assumptions (all confirmed by Daniel on 2026-10-31).

## Topic: Manual policy references
- source: docs/DECISIONS.md §2; docs/adr/ADR-000-especificacao-consolidada.md §6
- Manual sections cited: §1, §1.2 (contact), §2 (hours), §3 / §3.1 (payment, installments), §4.1-§4.4 (returns), §5.1 / §5.2 (shipping), §6.1 / §6.2 (promotions, PIX), §7 / §7.1 / §7.3 (service, partners, availability/complaints), §8 (warranty), §9 (LGPD). `data/processed/policies.md` uses markers `[§seção · p.página]`.

## Topic: Test catalog (original ADR-000 §11, minus demo)
- source: docs/adr/ADR-000-especificacao-consolidada.md §11, §16
- Rules, ingestion and tools, security, agent (ScriptedLLM), golden set. The "Demo" test group (5 conversations without key and embeddings; divergent hash fails) is out of scope per §16. Detailed cases appear as acceptance criteria in requirements.md.

## Topic: Deferred work for the README
- source: docs/DECISIONS.md §5; docs/adr/ADR-000-especificacao-consolidada.md §16
- Section "o que eu faria com mais tempo": Qdrant and dense/hybrid search; ReplayLLM and `make demo`; Firestore adapter; LLM-as-judge; `emporio trace`; real login/OTP; golden set with multiple repetitions; evidence validator for stock, order and product name.
