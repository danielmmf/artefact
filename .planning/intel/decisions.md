# Decisions (synthesized intel)

Sources: `docs/DECISIONS.md` (ADR, precedence 0, locked) and `docs/adr/ADR-000-especificacao-consolidada.md` (ADR, precedence 1, locked).
Both documents are locked. Where they overlap, entries are merged and both sources are listed (same substance, not a conflict). Where ADR-000 §16 / DECISIONS supersede earlier ADR-000 sections, the entry states the EFFECTIVE decision and names the superseded text. Effective-state resolutions are logged in `/var/www/html/teste/.planning/INGEST-CONFLICTS.md` (INFO).
Quoted Portuguese text is verbatim from the sources.

---

## DEC-01 / ADR-000 D2: Own function-calling loop with Pydantic contracts
- source: docs/DECISIONS.md (DEC-01, ex-ADR-001); docs/adr/ADR-000-especificacao-consolidada.md §2 D2
- status: locked
- decision: Own function-calling loop with Pydantic contracts. No PydanticAI and no LangGraph. Rationale: 8 tools and a linear flow do not justify a framework; the own loop keeps authorization, budget and validator explicit and testable with ScriptedLLM.
- scope: agent loop, tool contracts

## DEC-02 / ADR-000 D3, D4: store.db read-only plus separate app.db
- source: docs/DECISIONS.md (DEC-02, ex-ADR-002); docs/adr/ADR-000-especificacao-consolidada.md §2 D3, D4
- status: locked
- decision: `store.db` (SQLite, opened `mode=ro` during service) holds store data. A separate `app.db` (SQLite) holds history, sessions, order access, attempts and escalation tickets. Rationale: the service cannot alter price, stock or order, neither by bug nor by injection.
- scope: persistence, store data, app data

## DEC-03 / ADR-000 D8: Full policy manual in context instead of RAG
- source: docs/DECISIONS.md (DEC-03, ex-ADR-003); docs/adr/ADR-000-especificacao-consolidada.md §2 D8
- status: locked
- decision: Complete manual in context as `data/processed/policies.md` with markers `[§seção · p.página]`, instead of RAG. Rationale: the 8-page manual fits in context; RAG would add risk of retrieving the wrong passage without gain.
- scope: policy manual handling, prompt construction

## DEC-04 / ADR-000 D9: Search is FTS5/BM25 + rapidfuzz only (as revised by §16)
- source: docs/DECISIONS.md (DEC-04, ex-ADR-004); docs/adr/ADR-000-especificacao-consolidada.md §2 D9, §7, §16
- status: locked
- decision: Search uses SQLite FTS5/BM25 + rapidfuzz; exact filters in SQL; the index only orders IDs. 65 products; reproducible without network. Qdrant, dense and hybrid search are DEFERRED (§16); no `auto`/`hybrid` backend. A mini-eval of ~10 queries measures recall@5 and MRR of the lexical backend; the result goes to `evals/reports/` and the README. No result is presumed. Superseded text: ADR-000 §2 D9 (Qdrant "só se vencer o benchmark") and §7 (dense/hybrid pipeline, 15 to 20 queries, RRF, Qdrant adoption threshold). Status in DECISIONS: "Fechada; resultado pendente da medição".
- scope: product search

## DEC-05 / ADR-000 A1: Simulated authenticated identity and demonstrative ownership confirmation
- source: docs/DECISIONS.md (DEC-05, ex-ADR-005); docs/adr/ADR-000-especificacao-consolidada.md §3 A1, §8
- status: locked
- decision: Authenticated identity is SIMULATED by the channel (`--customer <id>`); ownership confirmation is DEMONSTRATIVE (order + e-mail or phone). Production requires login or OTP. Contact-based verification is weak and must be declared as demonstrative in the README and in the CLI. Verification is not authentication.
- scope: identity, order access

## DEC-06 / ADR-000 D10: PII tokenization before the LLM
- source: docs/DECISIONS.md (DEC-06, ex-ADR-006); docs/adr/ADR-000-especificacao-consolidada.md §2 D10, §8
- status: locked
- decision: E-mail and phone are tokenized (`[EMAIL_1]`, `[PHONE_1]`) before reaching the LLM; the map lives only in process memory, per session; traces, history and tickets carry no contact. Rationale: LGPD (manual §9) and reduced leakage surface.
- scope: PII, LGPD, traces

## DEC-07 / ADR-000 D11: OpenAI-compatible adapter, provider configured via .env
- source: docs/DECISIONS.md (DEC-07, ex-ADR-008); docs/adr/ADR-000-especificacao-consolidada.md §2 D11, §16
- status: locked
- decision: OpenAI-compatible adapter; provider configurable by `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` in `.env`. Rationale: the evaluator may use whatever key they have. Default model is PENDING, chosen in the agent phase by consulting official documentation, and recorded in `docs/DECISIONS.md`. ADR-000 D11 also lists Ollama as optional (compatible with an OpenAI-compatible adapter; DECISIONS is silent on it).
- scope: LLM provider, configuration

## DEC-08 / ADR-000 D1: Reproducibility (uv, injectable clock, keyless tests)
- source: docs/DECISIONS.md (DEC-08, ex-ADR-009); docs/adr/ADR-000-especificacao-consolidada.md §2 D1, §9
- status: locked
- decision: Python 3.11+, dependencies locked with uv; injectable clock (`EMPORIO_NOW`); `make test` runs without key, without network and without Docker. Requirement of the evaluator. The ADR-009 elements ReplayLLM and demo fallback are deferred (§16).
- scope: reproducibility, tooling

## DEC-09 / ADR-000 D6: Monetary values in cents
- source: docs/DECISIONS.md (DEC-09); docs/adr/ADR-000-especificacao-consolidada.md §2 D6
- status: locked
- decision: Monetary values are integer cents, exposed as `Decimal`. Rationale: avoid rounding errors in boundary tests.
- scope: money handling

## DEC-10: Ownership and access checked in Python on every order tool call
- source: docs/DECISIONS.md (DEC-10); docs/adr/ADR-000-especificacao-consolidada.md §8
- status: locked
- decision: Ownership verification and access are checked in Python on every call of `get_order` and `check_return_eligibility`, independent of the LLM. The defense against injection is authorization in code, not the prompt.
- scope: order access, prompt injection defense

## ADR-000 D5: Explicit idempotent ingestion with QUALITY.md
- source: docs/adr/ADR-000-especificacao-consolidada.md §2 D5, §6, §9, §16
- status: locked
- decision: Explicit, idempotent ingestion with Pydantic validation and report `data/processed/QUALITY.md`. `make ingest` produces `store.db`, `policies.md`, `QUALITY.md`; idempotent; does not touch `app.db`. Kept by §16.
- scope: data ingestion

## ADR-000 D7: StoreRepository interface
- source: docs/adr/ADR-000-especificacao-consolidada.md §2 D7
- status: locked
- decision: `StoreRepository` interface; `SQLiteRepository` is the official implementation.
- scope: repository layer

## ADR-000 D12: CLI with Rich as main interface
- source: docs/adr/ADR-000-especificacao-consolidada.md §2 D12, §16
- status: locked
- decision: Main interface is a CLI with Rich. After §16 the CLI commands are `chat` and `ingest` (no `trace`).
- scope: user interface

## ADR-000 D13: Firestore only as a future adapter (deferred)
- source: docs/adr/ADR-000-especificacao-consolidada.md §2 D13, §16; docs/DECISIONS.md §4, §5
- status: locked
- decision: Firestore is only a future adapter of `StoreRepository`, outside the mandatory core. DEFERRED by §16 (README "o que eu faria com mais tempo"). "Firebase/Firestore obrigatório" is a rejected option: "Dependência externa sem ganho para o protótipo".
- scope: persistence adapters

## ADR-000 A4: Offline demo without embeddings (superseded)
- source: docs/adr/ADR-000-especificacao-consolidada.md §3 A4, §16
- status: locked
- decision: SUPERSEDED/out of scope per §16 ("§3 A4, §9 (`make demo`, ReplayLLM, `recordings/`) e §11 'Demo': fora do escopo"). Not to be planned. Original text: "Busca `auto` cai para lexical sem modelo em cache; gravações do demo feitas com backend lexical".
- scope: demo, search fallback

## S-a: Installments up to 3x
- source: docs/DECISIONS.md S-a; manual §3.1
- status: locked
- decision: Manual: "Parcelamento em até 3x: sem juros, sem valor mínimo de parcela (exceto abaixo de R$ 50,00)." Adopted: 2x and 3x require installment >= R$ 50,00. 1x has no minimum. Confirmed by the owner 2026-10-31.
- scope: installments

## S-b: Installment table vs ranges
- source: docs/DECISIONS.md S-b; docs/adr/ADR-000-especificacao-consolidada.md §6; manual §3, §3.1
- status: locked
- decision: Manual §3 table says "Até 12x sem juros — Parcela mínima de R$ 100,00"; §3.1 (ranges) prevails as the specific rule: 4 to 6x >= R$ 80,00; 7 to 12x >= R$ 100,00 (inclusive).
- scope: installments

## S-c / ADR-000 A5: Shipping at exactly R$ 500,00
- source: docs/DECISIONS.md S-c; docs/adr/ADR-000-especificacao-consolidada.md §3 A5, §6; manual §5.1
- status: locked
- decision: Manual: "Frete grátis para pedidos acima de R$ 500,00. Para pedidos abaixo de R$ 500,00, taxa fixa de R$ 35,00." Exactly R$ 500,00 has free shipping (interpretation most favorable to the consumer, CDC art. 47). Tested at 499,99 / 500,00 / 500,01.
- scope: shipping

## S-d: Combined payment threshold
- source: docs/DECISIONS.md S-d; docs/adr/ADR-000-especificacao-consolidada.md §6; manual §3.1
- status: locked
- decision: Manual: "Combinação de formas de pagamento: permitida (ex.: PIX + cartão) para compras acima de R$ 2.000,00." Adopted: allowed from R$ 2.000,00 inclusive (same logic as S-c). Tested at 1.999,99 / 2.000,00.
- scope: payment combination

## S-e: Shipping basis
- source: docs/DECISIONS.md S-e; docs/adr/ADR-000-especificacao-consolidada.md §6
- status: locked
- decision: Manual §5.1 does not define the basis of "pedido". Shipping basis is the subtotal with promotion, before the PIX discount.
- scope: shipping

## S-f: Metropolitan region scope
- source: docs/DECISIONS.md S-f; docs/adr/ADR-000-especificacao-consolidada.md §6; manual §5.1
- status: locked
- decision: Manual: "Região Metropolitana de Campo Grande" (municipalities not listed). In the MVP only the city of Campo Grande counts; other cities follow §5.2.
- scope: shipping region

## S-g / ADR-000 A2: Preference exchange and return start date
- source: docs/DECISIONS.md S-g, T-8; docs/adr/ADR-000-especificacao-consolidada.md §3 A2, §6; manual §4.3
- status: locked
- decision: Manual §4.3 "Trocas por preferência ... em até 7 dias, mediante disponibilidade" (start undefined). Counted from receipt. Without `received_at`: `insufficient_information`. `estimated_delivery` is never used as receipt date.
- scope: returns

## S-h: Clock for tests (and former demo)
- source: docs/DECISIONS.md S-h; docs/adr/ADR-000-especificacao-consolidada.md §9
- status: locked
- decision: Clock for demo and tests: `EMPORIO_NOW=2026-03-25T10:00-04:00`. The demo is deferred (§16); the fixed clock remains for tests.
- scope: clock

## S-i: Special freight quotation list
- source: docs/DECISIONS.md S-i; docs/adr/ADR-000-especificacao-consolidada.md §6, §13; manual §5.2
- status: locked
- decision: Manual: "Instrumentos de grande porte (baterias acústicas, pianos digitais, contrabaixos) podem exigir frete especial com cotação individual." The agent says the product "pode exigir cotação especial", never that it requires it. Explicit list, no inference from descriptions: products 135, 136, 137, 138 (category 2, "contrabaixo") and 139, 140, 141 (acoustic drums). No product is a digital piano. Product 136 is discontinued and not sellable.
- scope: shipping, special quote

## S-j: PIX discount only on non-promotional items
- source: docs/DECISIONS.md S-j; docs/adr/ADR-000-especificacao-consolidada.md §6; manual §6.2
- status: locked
- decision: Manual: "O desconto de PIX (5%) não se aplica sobre preços já promocionais." PIX applies item by item, only to items without an active promotion.
- scope: PIX, promotions

## S-k: Partner stores
- source: docs/DECISIONS.md S-k; docs/adr/ADR-000-especificacao-consolidada.md §6; manual §7.1
- status: locked
- decision: Manual: "Sugerir lojas parceiras quando possível." The manual lists no partners: accessories are refused without citing stores.
- scope: out-of-scope handling

## S-l: Official contact data
- source: docs/DECISIONS.md S-l; docs/adr/ADR-000-especificacao-consolidada.md §6; manual cover, §1.2, §7
- status: locked
- decision: Cover and §1.2 give (67) 3341-4444; §7 gives (67) 3321-4500; e-mail appears with and without accent. Official contact reported: (67) 3341-4444 and `contato@emporiodamusica.com.br`. Divergences recorded in `QUALITY.md`.
- scope: store contact

## T-1 / ADR-000 A3: Order totals
- source: docs/DECISIONS.md T-1; docs/adr/ADR-000-especificacao-consolidada.md §3 A3
- status: locked
- decision: Totals diverging from items (orders 3 and 20): always use `orders.total_brl`, described as "total registrado no pedido"; divergence goes to `QUALITY.md` without attributing cause.
- scope: orders data

## T-2: Product descriptions that diverge from name/specs
- source: docs/DECISIONS.md T-2
- status: locked
- decision: For products 135, 136, 137, 139, 140, 142, 144, name and specs are the source of truth. The description of these products is NOT sent to the LLM by the tools; it stays only in the search index. A test guarantees the agent does not cite a brand taken from those descriptions.
- scope: product data, tools

## T-3: Historical installments outside §3.1
- source: docs/DECISIONS.md T-3
- status: locked
- decision: Orders 9, 16, 18: record only in `QUALITY.md`. Rules apply to new quotes.
- scope: orders data

## T-4: PIX orders without discount in total
- source: docs/DECISIONS.md T-4
- status: locked
- decision: Orders 1, 5, 10, 13, 17: record only in `QUALITY.md` (consistent with T-1).
- scope: orders data

## T-5: Repeated e-mail on customers 11 and 43
- source: docs/DECISIONS.md T-5
- status: locked
- decision: Ownership confirmation compares the contact with the customer OF THE ORDER, never with any customer holding that contact. Dedicated test.
- scope: ownership verification

## T-6: CSV filenames with spaces
- source: docs/DECISIONS.md T-6
- status: locked
- decision: Files are named `desafio_tecnico_ai_eng - <tabela>.csv`. The loader locates each CSV by suffix (`categories`, `customers`, `order_items`, `orders`, `products`, `promotions`), tolerating spaces; absence or ambiguity fails ingestion.
- scope: ingestion loader

## T-7: Two active promotions on the same product
- source: docs/DECISIONS.md T-7; docs/adr/ADR-000-especificacao-consolidada.md §6
- status: locked
- decision: Fails ingestion (does not occur in current data; tested with synthetic data).
- scope: promotions

## T-8: No receipt date or channel in orders
- source: docs/DECISIONS.md T-8; docs/adr/ADR-000-especificacao-consolidada.md §3 A2
- status: locked
- decision: `estimated_delivery` never becomes receipt date; return without date or channel returns `insufficient_information` (with list of what is missing).
- scope: returns

## T-9: Remaining data inconsistencies
- source: docs/DECISIONS.md T-9; docs/adr/ADR-000-especificacao-consolidada.md §13
- status: locked
- decision: Remaining inconsistencies of ADR-000 §13 are listed in `QUALITY.md` generated by ingestion.
- scope: data quality

## ADR-000 §1: Principles (as revised by §16)
- source: docs/adr/ADR-000-especificacao-consolidada.md §1, §16
- status: locked
- decision: (1) The LLM chooses the tool; code guarantees price, stock, promotion, installments, shipping and order access. (2) Reproducibility before sophistication: `make test` runs without key, Docker, GPU or network after install (the `make demo` part is out of scope per §16). (3) When in doubt the agent asks or escalates; never invents. (4) Each layer is testable in isolation. (5) AI interpretations do not become store rules without a manual passage; every interpretation is recorded (now in `docs/DECISIONS.md`).
- scope: project principles

## ADR-000 §8: Evidence validator (R$ only, per §16)
- source: docs/adr/ADR-000-especificacao-consolidada.md §8, §16; docs/DECISIONS.md §5
- status: locked
- decision: The validator checks ONLY R$ values cited against the tool results of the turn; otherwise regenerate once; if it persists, safe response. Validator for stock, order number and product name is deferred. Superseded text: §8 original "R$, estoque, número de pedido e nome de produto".
- scope: answer validation

## ADR-000 §10: Observability (basic JSONL trace, per §16)
- source: docs/adr/ADR-000-especificacao-consolidada.md §10, §16
- status: locked
- decision: JSONL trace per turn in `var/traces/` with the same essential fields; no `emporio trace` command (deferred).
- scope: tracing

## ADR-000 §16: Scope decision of 2026-10-31
- source: docs/adr/ADR-000-especificacao-consolidada.md §16; docs/DECISIONS.md (intro)
- status: locked
- decision: Prevails over earlier sections where they conflict. KEEPS: ingestion with validation and `QUALITY.md`; business rules with boundary tests; order access with verification, expiry and lockout; PII tokenization with scan test; own loop + manual in prompt + the 8 tools; CLI; 5 real conversations in `examples/`; README; `make test` keyless in CI. SIMPLIFIES: ADRs 001-011 become a single `docs/DECISIONS.md`; search only FTS5 + rapidfuzz with ~10-query mini-eval (`make bench`, no download); golden set ~15 cases with 1 repetition (`make eval`); evidence validator only for R$ values; basic JSONL traces. DEFERS (README, "o que eu faria com mais tempo"): Qdrant/dense and hybrid search; ReplayLLM and `make demo`; Firestore; LLM-as-judge; `emporio trace` command.
- scope: whole project scope

## Rejected options (ex-ADR-010)
- source: docs/DECISIONS.md §4; docs/adr/ADR-000-especificacao-consolidada.md §14
- status: locked
- decision: Rejected: PydanticAI and LangGraph (see DEC-01); mandatory Firebase/Firestore ("Dependência externa sem ganho para o protótipo"); RAG of policies as main path (see DEC-03); intent router parallel to the LLM ("Duplica a decisão que o function calling já toma"); embeddings via paid API ("Quebra a reprodutibilidade sem chave"); order lookup by customer name ("Nomes não identificam ninguém com segurança"); keyword injection filter ("Contornável; a defesa é a autorização em Python"); fixed sleep against timing attacks ("Não resolve; respostas idênticas e bloqueio por tentativas resolvem").
- scope: architecture alternatives

## Deferred items (README "o que eu faria com mais tempo")
- source: docs/DECISIONS.md §5; docs/adr/ADR-000-especificacao-consolidada.md §16
- status: locked
- decision: Deferred, to be listed in README only: Qdrant and dense/hybrid search; ReplayLLM and `make demo`; Firestore adapter; LLM-as-judge; `emporio trace` command; real login/OTP; golden set with multiple repetitions; evidence validator for stock, order and product name.
- scope: deferred work
