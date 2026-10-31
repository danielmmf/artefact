# Requirements (synthesized intel)

IMPORTANT: the ingest set contains NO PRD documents. These requirements are extracted mechanically from the two ADRs: ADR-000 §5, §6, §8, §11, §12 (acceptance criteria as revised by §16) and §16 "Mantém"/"Simplifica", plus `docs/DECISIONS.md` (DEC, S-x, T-x). Nothing here is new content. Items marked deferred in §16 are NOT requirements (see decisions.md and context.md). IDs are `REQ-{slug}` and stay stable. Each entry cites the source section.
Where DECISIONS / §16 override earlier ADR-000 text, the effective (post-§16) requirement is stated.
No competing acceptance variants were found (single source lineage).

---

## REQ-ingest-pipeline
- source: docs/adr/ADR-000-especificacao-consolidada.md §2 D5, §9, §16; docs/DECISIONS.md T-6, T-7
- description: Explicit, idempotent ingestion (`make ingest`) with Pydantic validation producing `store.db`, `data/processed/policies.md` and `data/processed/QUALITY.md`. Does not touch `app.db`. Loader finds each CSV by suffix (categories, customers, order_items, orders, products, promotions) tolerating spaces in filenames; absence or ambiguity fails ingestion. Two active promotions on the same product fail ingestion.
- acceptance: Ingestion re-runnable with identical result; missing/ambiguous CSV fails; duplicate active promotion (synthetic data) fails; `data/raw/` untouched.
- scope: data ingestion

## REQ-ingest-quality-report
- source: docs/adr/ADR-000-especificacao-consolidada.md §12, §13; docs/DECISIONS.md T-1, T-3, T-4, T-9, S-l
- description: `QUALITY.md` lists all known data inconsistencies (ADR-000 §13 list, including additional verified items) without attributing cause, including phone/e-mail divergence of the manual.
- acceptance: "`QUALITY.md` lista todas as inconsistências conhecidas"; test "`QUALITY.md` completo".
- scope: data quality

## REQ-data-treatment-rules
- source: docs/DECISIONS.md T-1, T-2, T-3, T-4, T-5, T-8
- description: Apply data-treatment rules: order totals always `orders.total_brl` ("total registrado no pedido"); descriptions of products 135, 136, 137, 139, 140, 142, 144 are not sent to the LLM; historical installments (orders 9, 16, 18) and PIX orders without discount (1, 5, 10, 13, 17) only logged in QUALITY.md; ownership check compares contact with the customer of the order (customers 11 and 43 share an e-mail); `estimated_delivery` never becomes receipt date.
- acceptance: order 3 returns 3.450,00; test that agent does not cite a brand from the divergent descriptions; dedicated test for repeated-e-mail ownership.
- scope: data handling

## REQ-rule-availability
- source: docs/adr/ADR-000-especificacao-consolidada.md §6 (manual §7.3)
- description: `active` + stock > 0: available. `active` + 0: unavailable, with alternatives. `discontinued`: out of catalog even with stock. `coming_soon`: not sellable.
- acceptance: tests for products 96, 113, 136, 130.
- scope: catalog

## REQ-rule-promotion
- source: docs/adr/ADR-000-especificacao-consolidada.md §6, §5 (manual §6.2); docs/DECISIONS.md T-7
- description: Only `is_active = 1` promotions count. `PriceInfo` shows original price and percentage together. Inactive promotions listed separately in product detail.
- acceptance: GD20 (95) with inactive promotion; product 90 with 18%; duplicate active promotion fails ingestion.
- scope: pricing

## REQ-rule-pix
- source: docs/adr/ADR-000-especificacao-consolidada.md §6 (manual §3, §6.2); docs/DECISIONS.md S-j
- description: 5% PIX discount applied item by item, only to items without an active promotion.
- acceptance: mixed cart test (121 with promotion + 81 without); subtotal 510,00 with PIX.
- scope: payment

## REQ-rule-installments
- source: docs/adr/ADR-000-especificacao-consolidada.md §6 (manual §3, §3.1); docs/DECISIONS.md S-a, S-b
- description: Credit 1x no minimum; 2x to 3x installment >= R$ 50,00; 4x to 6x >= R$ 80,00 inclusive; 7x to 12x >= R$ 100,00 inclusive (§3.1 prevails over §3 table). Each installment option returns `{n, valor, valid, reason}`.
- acceptance: 2x 100,00/99,98; 3x 150,00/149,97; 4x 320,00/319,96; 7x 700,00/699,93; 12x 1.200,00/1.199,88, with reason.
- scope: payment

## REQ-rule-combined-payment
- source: docs/adr/ADR-000-especificacao-consolidada.md §6; docs/DECISIONS.md S-d
- description: Combined payment methods allowed from R$ 2.000,00 inclusive.
- acceptance: tests at 1.999,99 and 2.000,00.
- scope: payment

## REQ-rule-shipping
- source: docs/adr/ADR-000-especificacao-consolidada.md §3 A5, §6 (manual §5.1, §5.2); docs/DECISIONS.md S-c, S-e, S-f
- description: Campo Grande city only (MVP): free from R$ 500,00 inclusive; below, R$ 35,00; basis is subtotal with promotion before PIX; 1 to 3 business days. Other cities: no fee; PAC, SEDEX, Jadlog with lead times; calculation by CEP, weight and dimensions at checkout.
- acceptance: tests 499,99 / 500,00 / 500,01; subtotal 510,00 with PIX; other city.
- scope: shipping

## REQ-rule-special-quote
- source: docs/DECISIONS.md S-i; docs/adr/ADR-000-especificacao-consolidada.md §6 (manual §5.2)
- description: `special_quote_required` for the explicit list 135, 136, 137, 138, 139, 140, 141 only (no inference from description). Agent says "pode exigir cotação especial", never that it requires it. Product 136 is discontinued and not sellable.
- acceptance: acoustic drum test; agent wording never asserts requirement.
- scope: shipping

## REQ-rule-order-total
- source: docs/adr/ADR-000-especificacao-consolidada.md §3 A3, §6; docs/DECISIONS.md T-1
- description: Order total is always `orders.total_brl`, presented as "total registrado no pedido".
- acceptance: order 3 returns 3.450,00 (items sum 3.498,00).
- scope: orders

## REQ-rule-returns
- source: docs/adr/ADR-000-especificacao-consolidada.md §3 A2, §5, §6 (manual §4.1 to §4.4, §8); docs/DECISIONS.md S-g, T-8
- description: `ReturnStatus` in {eligible, expired, not_applicable, not_yet_delivered, cancelled, insufficient_information}. Cancelled order: `cancelled` with order note. `pending`/`confirmed`/`shipped`: `not_yet_delivered`. Regret: online purchase only, 7 calendar days after receipt; without `received_at` or channel: `insufficient_information`; in-store: `not_applicable`. Defect: 30 calendar days after purchase (`order_date`); afterwards `expired` with manufacturer warranty guidance and 90-day legal warranty from receipt. Preference: 7 days from receipt, subject to availability; without `received_at`: `insufficient_information`. Exclusions (customization, final sale, mouthpieces) are not in the data: returned as `exclusions_to_confirm`. The tool never approves a return and lists `missing_information`.
- acceptance: tests for return without `received_at`, without channel, in-store, defect by `order_date`, order 20 cancelled, order 13 not delivered.
- scope: returns

## REQ-rule-store-hours
- source: docs/adr/ADR-000-especificacao-consolidada.md §5, §6 (manual §2)
- description: Mon-Fri 9h-18h, Sat 9h-13h, Sunday closed; holidays out of scope; injectable clock.
- acceptance: Saturday 12:59 / 13:00 and Sunday tests.
- scope: store hours

## REQ-rule-scope-contact
- source: docs/adr/ADR-000-especificacao-consolidada.md §6 (manual §1, §1.2, §7.1, §7.3); docs/DECISIONS.md S-k, S-l
- description: Instruments only; accessories refused without citing partner stores. Contact (67) 3341-4444 and `contato@emporiodamusica.com.br`. Complaints go to `escalate_to_human` with return in 24 business hours.
- acceptance: out-of-scope request answered without tool call; "dinheiro" test.
- scope: service scope

## REQ-tools-eight
- source: docs/adr/ADR-000-especificacao-consolidada.md §5, §16
- description: Implement the 8 tools (`search_products`, `get_product`, `quote_payment`, `store_status`, `verify_order_ownership`, `get_order`, `check_return_eligibility`, `escalate_to_human`) with the common `ToolResult` envelope and contracts in constraints.md. No tool output contains e-mail, phone or customer full name. Search backend after §16 is lexical only.
- acceptance: ambiguous name returns `ambiguous` with candidates; write attempt to `store.db` fails; structured tool error handled by agent.
- scope: tool layer

## REQ-agent-loop
- source: docs/adr/ADR-000-especificacao-consolidada.md §2 D2, §8, §11, §16; docs/DECISIONS.md DEC-01
- description: Own function-calling loop (max 5 iterations per turn) with the full policy manual in the prompt; token budget of 16k per call (history truncated first; manual and tool definitions never); out-of-scope requests handled without tools; history persisted in `app.db`.
- acceptance: ScriptedLLM tests: 5 iterations; structured tool error; validator regenerates and falls to safe response; budget preserves manual; out-of-scope without tool; history persists.
- scope: agent

## REQ-agent-validator-rs
- source: docs/adr/ADR-000-especificacao-consolidada.md §8, §16
- description: Evidence validator only for R$ values: R$ values cited must appear in the turn's tool results; otherwise regenerate once; if it persists, safe response.
- acceptance: ScriptedLLM test of regenerate then safe response.
- scope: answer validation

## REQ-agent-llm-config
- source: docs/DECISIONS.md DEC-07; docs/adr/ADR-000-especificacao-consolidada.md §16
- description: OpenAI-compatible adapter configured by `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` from `.env` (`.env.example` provided). Default model chosen in the agent phase from official documentation and recorded in `docs/DECISIONS.md`.
- acceptance: provider switchable by `.env` only; default model recorded in DECISIONS.md.
- scope: LLM provider

## REQ-sec-order-access
- source: docs/adr/ADR-000-especificacao-consolidada.md §8, §11; docs/DECISIONS.md DEC-05, DEC-10
- description: `anonymous` mode (default): one order at a time after demonstrative ownership confirmation (order + e-mail or phone). `simulated_authenticated` mode (`emporio chat --customer <id>`): only that customer's orders. Access stored in `app.db` `order_access(session_id UUID, order_id, granted_at, expires_at)` with 15-minute validity. `get_order` and `check_return_eligibility` check access in Python on every call. Nonexistent order and wrong contact return the identical response. No lookup by name alone.
- acceptance: anonymous without access; identical responses; expiry at 15 min; `--customer 3` sees orders 1 and 19 but not 2; access by name denied.
- scope: order access

## REQ-sec-lockout
- source: docs/adr/ADR-000-especificacao-consolidada.md §5, §8, §11
- description: Failures counted per `order_id` and per session, persisted; 3 failures lock (`locked`) and escalate to the team.
- acceptance: lockout after 3 failures across sessions.
- scope: order access

## REQ-sec-pii
- source: docs/adr/ADR-000-especificacao-consolidada.md §8, §11, §12, §16; docs/DECISIONS.md DEC-06
- description: E-mail and phone tokenized (`[EMAIL_1]`, `[PHONE_1]`) before the LLM; map in process memory only, isolated per session, never in prompt or disk. Traces, history and tickets carry no contact. Tool results are delimited as data; injection defense is Python authorization.
- acceptance: scan test: no contact from `customers.csv` in prompts, traces, history or tickets; injection in a description does not change permissions.
- scope: PII, LGPD

## REQ-sec-verification-disclosure
- source: docs/adr/ADR-000-especificacao-consolidada.md §12; docs/DECISIONS.md DEC-05
- description: Verification must be described as demonstrative in the README and in the CLI (and in DECISIONS.md, replacing ADR-005).
- acceptance: wording present in README, CLI and DECISIONS.md.
- scope: identity

## REQ-search-lexical
- source: docs/adr/ADR-000-especificacao-consolidada.md §5, §7, §16; docs/DECISIONS.md DEC-04
- description: Product search with SQLite FTS5/BM25 + rapidfuzz; exact filters in SQL; index returns only IDs, data comes from the repository; `search_backend` reported in tool response and trace. No dense/hybrid backend.
- acceptance: filters exact in SQL; backend reported.
- scope: search

## REQ-search-minieval
- source: docs/adr/ADR-000-especificacao-consolidada.md §7, §9, §12, §16; docs/DECISIONS.md DEC-04
- description: `make bench` runs a mini-eval of ~10 queries (`evals/search_queries.yaml`) measuring recall@5 and MRR of the lexical backend, without any download; result stored in `evals/reports/` and in the README. No result presumed. Source is silent on whether the original three groups (by name / by intent / ambiguous) are kept for the ~10 queries.
- acceptance: "mini-eval de busca medido" (replaces "Benchmark P2 encerrado com resultado medido").
- scope: search evaluation

## REQ-eval-golden
- source: docs/adr/ADR-000-especificacao-consolidada.md §11, §12, §16
- description: Golden set of ~15 cases with 1 repetition run by `make eval` against a real LLM; categories catalog, price/payment, orders, returns, store, out of scope, adversarial; metrics tool-selection accuracy, exactness, refusal. LLM-as-judge deferred. Original temperature 0 (the "3 repetições" is replaced by 1).
- acceptance: tool accuracy >= 90%; price, stock and status exactness = 100%; correct refusals = 100% (thresholds from §12; §16 does not change them).
- scope: evaluation

## REQ-trace-jsonl
- source: docs/adr/ADR-000-especificacao-consolidada.md §10, §16
- description: Basic JSONL trace per turn in `var/traces/` with essential fields (session hash, turn, iteration max 5, tool_calls with redacted args, status, error, latency; llm model, latency, tokens; search_backend; validator; budget; auth events without contact; errors). No `emporio trace` command.
- acceptance: trace written per turn with no contact data.
- scope: observability

## REQ-cli
- source: docs/adr/ADR-000-especificacao-consolidada.md §2 D12, §4, §8, §16
- description: CLI with Rich: `emporio chat` (optional `--customer <id>`) and `emporio ingest`. No `trace` command.
- acceptance: commands available and verification declared demonstrative.
- scope: user interface

## REQ-ci-make-test
- source: docs/adr/ADR-000-especificacao-consolidada.md §9, §12, §16; docs/DECISIONS.md DEC-08
- description: `make setup` (`uv sync`), `make ingest`, `make test` (unit, tools, security, agent with ScriptedLLM; no key, no network, no Docker), `make chat` (key), `make eval` (key), `make bench` (no download). CI on `ubuntu-latest`, Python 3.11, no secrets. CI criterion: `make setup && make test` green without key, Docker, GPU or network. `make demo` is out of scope.
- acceptance: `make setup && make test` green in CI.
- scope: reproducibility, CI

## REQ-docs-decisions
- source: docs/adr/ADR-000-especificacao-consolidada.md §12, §16; docs/DECISIONS.md
- description: Every manual interpretation is recorded in `docs/DECISIONS.md` with the manual passage (replaces "toda interpretação tem ADR"). Default LLM model recorded there in the agent phase.
- acceptance: interpretations S-a..S-l kept with manual excerpt; model recorded.
- scope: documentation

## REQ-docs-examples
- source: docs/adr/ADR-000-especificacao-consolidada.md §12, §16
- description: 5 REAL conversations in `examples/` as `.md`: catalog, promotion, protected order, return, improper access. Last phase of the roadmap; cannot be compressed.
- acceptance: 5 real (not simulated) conversations with those topics.
- scope: deliverable

## REQ-docs-readme
- source: docs/adr/ADR-000-especificacao-consolidada.md §12, §16; docs/DECISIONS.md §5
- description: README with instructions, architecture, decisions, limitations, search mini-eval result, use of AI assistants, demonstrative-verification disclosure, and the "o que eu faria com mais tempo" list of deferred items.
- acceptance: all listed sections present.
- scope: deliverable

## REQ-tests-boundary
- source: docs/adr/ADR-000-especificacao-consolidada.md §11, §12
- description: Business-rule boundary tests as enumerated in REQ-rule-* acceptance criteria, including shipping at R$ 500,00 exactly; 100% of security tests pass.
- acceptance: all boundary tests pass; 100% of security tests pass; no contact from `customers.csv` leaks.
- scope: testing

## REQ-git-delivery
- source: docs/adr/ADR-000-especificacao-consolidada.md §12, §16
- description: Incremental commits, no force-push, repository frozen at deadline (see constraints.md CON-schedule).
- acceptance: "Commits incrementais, sem force-push, congelados no prazo."
- scope: delivery process
