# Constraints (synthesized intel)

Sources: ADR-000 (`docs/adr/ADR-000-especificacao-consolidada.md`), `docs/DECISIONS.md`, and hard constraints supplied by the project owner in the ingest request (marked "owner directive", consistent with ADR-000 §16). No SPEC documents exist in the ingest set; these entries come from the ADRs. Quoted Portuguese is verbatim.

---

## CON-schedule: Deadline and work days
- source: docs/adr/ADR-000-especificacao-consolidada.md §16; owner directive
- type: nfr
- content: Delivery deadline 2026-11-03 23:59 America/Sao_Paulo. Repository freeze 2026-11-03 20:00. Work days: 31/10, 01/11, 02/11, 03/11 (reason: "2 dias úteis" from 2026-10-30, with holiday on 2026-11-02; conservative scenario).

## CON-planning: Roadmap shape
- source: docs/adr/ADR-000-especificacao-consolidada.md §16; owner directive
- type: nfr
- content: At most 5 phases. Tracer bullet in phase 1. The last phase (5 real conversations in `examples/` + README) cannot be compressed. If a phase is late, cut refinement, never delivery. No production code before roadmap approval (owner directive).

## CON-repo-hygiene: Versioning rules
- source: owner directive; docs/adr/ADR-000-especificacao-consolidada.md §4
- type: nfr
- content: Never version `.env`, `var/`, `.claude/`, `docs/private/`. `.planning/` is versioned. `data/raw/` (official CSVs and PDF) is never edited ("intocados"). `var/` holds gitignored `store.db`, `app.db`, `traces/`.

## CON-llm-config: LLM provider contract
- source: docs/DECISIONS.md DEC-07; docs/adr/ADR-000-especificacao-consolidada.md §2 D11, §16; owner directive
- type: api-contract
- content: OpenAI-compatible adapter. Environment variables in `.env`: `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`. Default model not yet chosen: it is chosen in the agent phase from official documentation and recorded in `docs/DECISIONS.md`. Tests never need the key.

## CON-tool-envelope: ToolResult envelope and error codes
- source: docs/adr/ADR-000-especificacao-consolidada.md §5
- type: api-contract
- content: `ToolResult = { ok: bool, data: <modelo> | null, error: { code, message_for_agent } | null }`. Codes: `invalid_input`, `not_found`, `ambiguous`, `access_denied`, `not_verified`, `locked`, `internal_error`. No tool output contains e-mail, phone or full customer name.

## CON-tool-contracts: The 8 tools
- source: docs/adr/ADR-000-especificacao-consolidada.md §5, §16
- type: api-contract
- content: 
  - `search_products`: in `query?`, `category?`, `min_price?`, `max_price?`, `only_available=true`, `limit=5`; out `ProductSummary[]` (id, name, category, `availability`, stock, `PriceInfo`), `total_matches`, `search_backend`; exact filters in SQL, index orders IDs only.
  - `get_product`: in `product_id` or `name`; out `ProductDetail` (description, specs, `PriceInfo`, `inactive_promotions`, `alternatives`); `ambiguous` with candidates. (Per DECISIONS T-2, descriptions of products 135, 136, 137, 139, 140, 142, 144 are not sent.)
  - `quote_payment`: in `items[{product_id, quantity}]`, `destination_city?`; out per item: list price, final, promotion, PIX eligible, PIX price; totals; `installments[{n, valor, valid, reason}]`; `combined_payment_allowed`; `shipping`; non-sellable items as `not_purchasable`, outside totals.
  - `store_status`: no input; out `now_local`, `is_open`, today's hours, next opening; injectable clock.
  - `verify_order_ownership`: in `order_id`, `contact_ref` (token); out `granted` with validity; `not_verified` identical for nonexistent or wrong contact; `locked` after 3 failures.
  - `get_order`: in `order_id`; out status, date, items, `total_brl`, payment, tracking, estimate, note, first name; `access_denied` without access, whether or not it exists.
  - `check_return_eligibility`: in `order_id`, `reason` (arrependimento, defeito, preferência), `received_at?`, `purchase_channel?`; out `status`, rule (§), deadline, days left, `missing_information`, conditions, `exclusions_to_confirm`; requires access; never approves a return.
  - `escalate_to_human`: in `category`, `summary` (tokenized); out `ticket_id`, return in 24 business hours; writes to `app.db` without PII.

## CON-tool-models: Supporting models
- source: docs/adr/ADR-000-especificacao-consolidada.md §5
- type: schema
- content: `PriceInfo`: `list_price`, `final_price`, `active_promotion {name, discount_percent}` or null (original price and percentage always together, manual §6.2). `availability`: available, out_of_stock, discontinued, coming_soon. `ReturnStatus`: eligible, expired, not_applicable, not_yet_delivered, cancelled, insufficient_information. `shipping`: `region` (metro, other, unknown), `fee` (null outside region), `free`, `rule_ref`, `modalities`, `special_quote_required`.

## CON-money: Monetary representation
- source: docs/DECISIONS.md DEC-09; docs/adr/ADR-000-especificacao-consolidada.md §2 D6
- type: schema
- content: Integer cents internally, exposed as `Decimal`.

## CON-db-separation: Database separation and access
- source: docs/DECISIONS.md DEC-02; docs/adr/ADR-000-especificacao-consolidada.md §2 D3, D4, §8
- type: schema
- content: `store.db` opened with `mode=ro` during service (write must fail). `app.db` separate: history, sessions, `order_access(session_id UUID, order_id, granted_at, expires_at)` with 15-minute validity, attempts (per `order_id` and per session, persisted), tickets without PII.

## CON-identity-protocol: Identity and verification protocol
- source: docs/adr/ADR-000-especificacao-consolidada.md §3 A1, §8; docs/DECISIONS.md DEC-05, DEC-10, T-5
- type: protocol
- content: Modes `simulated_authenticated` (`emporio chat --customer <id>`) and `anonymous` (default; one order at a time after demonstrative confirmation of order + e-mail or phone). Contact compared with the customer of the order. Failure responses identical for nonexistent order and wrong contact. 3 failures lock and escalate. Access checks in Python on every `get_order` / `check_return_eligibility`. Production would need login or OTP.

## CON-pii: PII boundary
- source: docs/adr/ADR-000-especificacao-consolidada.md §8; docs/DECISIONS.md DEC-06
- type: nfr
- content: E-mail and phone become `[EMAIL_1]`, `[PHONE_1]` before the LLM. Token map only in process memory, isolated per session, never in prompt or disk. Traces, history, tickets without contact. Tool results delimited as data. Defense against injection is authorization in Python, not keyword filtering.

## CON-budget: Token budget and loop limits
- source: docs/adr/ADR-000-especificacao-consolidada.md §8, §10, §11
- type: nfr
- content: 16k tokens per LLM call; history truncated first; the manual and tool definitions are never truncated. Max 5 iterations per turn.

## CON-reproducibility: Reproducible environment
- source: docs/adr/ADR-000-especificacao-consolidada.md §1, §2 D1, §9, §12, §16; docs/DECISIONS.md DEC-08, S-h
- type: nfr
- content: Python 3.11+, uv with lock. Injectable clock `EMPORIO_NOW` (fixed test value `2026-03-25T10:00-04:00`). `make test` without key, network or Docker. CI `ubuntu-latest`, Python 3.11, no secrets; CI criterion `make setup && make test` green. `make bench` without download. `make demo` is out of scope (§16).

## CON-architecture-deps: Layer dependency rule and layout
- source: docs/adr/ADR-000-especificacao-consolidada.md §4, §16
- type: nfr
- content: `domain`, `rules`, `security` and `tools` must not import `agent` or `llm`. Layout under `src/emporio/`: config, clock, money, domain, ingest, repository (base.py Protocol, sqlite.py), rules (availability, pricing, installments, shipping, returns, hours), search (lexical.py, factory.py), security (auth_context, access, pii), tools (contracts, registry, impl), agent (loop, prompt, validator, budget, session), llm (base, openai_compat, scripted), appdb, tracing, cli.py (chat, ingest). Removed by §16: `search/dense.py`, `search/hybrid.py`, `llm/replay.py`, `recordings/`, `trace` command. ADR documentation consolidated into `docs/DECISIONS.md` (no ADR-001..011 files).

## CON-trace-schema: JSONL trace record
- source: docs/adr/ADR-000-especificacao-consolidada.md §10, §16
- type: schema
- content: One JSONL record per turn in `var/traces/`: `session` (hash), `turn`, `iteration` (max 5), `tool_calls[]` (name, redacted args, status, error, latency), `llm` (model, latency, tokens), `search_backend`, `validator`, `budget`, `auth` (events without contact), `errors[]`.

## CON-return-windows: Return and warranty windows
- source: docs/adr/ADR-000-especificacao-consolidada.md §6 (manual §4.1 to §4.3, §8); docs/DECISIONS.md S-g
- type: nfr
- content: Regret 7 calendar days from receipt (online only); defect 30 calendar days from `order_date`; preference 7 days from receipt subject to availability; legal warranty 90 days from receipt. `estimated_delivery` is never a receipt date. Without receipt date or channel: `insufficient_information`.

## CON-payment-thresholds: Payment and shipping numeric thresholds
- source: docs/adr/ADR-000-especificacao-consolidada.md §6; docs/DECISIONS.md S-a, S-b, S-c, S-d, S-e
- type: nfr
- content: PIX 5% on non-promotional items. Installments: 1x none; 2x-3x >= R$ 50,00; 4x-6x >= R$ 80,00; 7x-12x >= R$ 100,00 (inclusive). Combined payment >= R$ 2.000,00 inclusive. Free shipping >= R$ 500,00 inclusive (Campo Grande only), otherwise R$ 35,00; base subtotal with promotion before PIX.

## CON-evals: Evaluation scope after §16
- source: docs/adr/ADR-000-especificacao-consolidada.md §7, §11, §12, §16
- type: nfr
- content: Search mini-eval about ~10 queries (`make bench`, lexical only). Golden set about ~15 cases, 1 repetition (`make eval`, real LLM). Acceptance thresholds from §12: tool accuracy >= 90%; exactness of price, stock, status = 100%; correct refusals = 100%. LLM-as-judge deferred. No result is presumed.

## CON-data-raw: Official data files
- source: docs/adr/ADR-000-especificacao-consolidada.md §4, §13; docs/DECISIONS.md T-6
- type: schema
- content: `data/raw/` contains official CSVs named `desafio_tecnico_ai_eng - <tabela>.csv` (categories, customers, order_items, orders, products, promotions) and `políticas_da_loja.pdf` (v2.1, jun/2025), untouched. 65 products. `store.db` and `policies.md` are derived artifacts.
