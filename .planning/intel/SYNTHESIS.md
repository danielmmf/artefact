# Synthesis Summary

Entry point for `gsd-roadmapper`. MODE: new. Precedence: docs/DECISIONS.md (0) > docs/adr/ADR-000-especificacao-consolidada.md (1); ADR-000 §16 "Decisão de escopo (2026-10-31)" prevails over earlier ADR-000 sections.

## Documents
- Total: 2 (ADR: 2; SPEC: 0; PRD: 0; DOC: 0; UNKNOWN: 0)
- docs/DECISIONS.md (locked, precedence 0)
- docs/adr/ADR-000-especificacao-consolidada.md (locked, precedence 1)
- Note: no PRD exists, so requirements.md is derived from the ADRs (acceptance criteria §12, business rules §6, §16 "Mantém"/"Simplifica", DECISIONS S-x/T-x).

## Decisions locked: 42 entries
Source: docs/DECISIONS.md and docs/adr/ADR-000-especificacao-consolidada.md. Includes DEC-01..10 (merged with ADR-000 D1..D13, A1..A5), S-a..S-l, T-1..T-9, the §16 scope decision, rejected options and deferred items. Deferred/superseded (not to plan): Qdrant/dense/hybrid search, ReplayLLM and `make demo`, Firestore, LLM-as-judge, `emporio trace`. See `/var/www/html/teste/.planning/intel/decisions.md`.

## Requirements: 33 entries
IDs (REQ-): ingest-pipeline, ingest-quality-report, data-treatment-rules, rule-availability, rule-promotion, rule-pix, rule-installments, rule-combined-payment, rule-shipping, rule-special-quote, rule-order-total, rule-returns, rule-store-hours, rule-scope-contact, tools-eight, agent-loop, agent-validator-rs, agent-llm-config, sec-order-access, sec-lockout, sec-pii, sec-verification-disclosure, search-lexical, search-minieval, eval-golden, trace-jsonl, cli, ci-make-test, docs-decisions, docs-examples, docs-readme, tests-boundary, git-delivery. See `/var/www/html/teste/.planning/intel/requirements.md`.

## Constraints: 19 entries
Type breakdown: api-contract 3, schema 5, nfr 10, protocol 1. Includes CON-schedule (deadline 2026-11-03 23:59 America/Sao_Paulo, freeze 20:00), CON-planning (max 5 phases, tracer bullet phase 1, last phase uncompressible, cut refinement not delivery, no production code before roadmap approval), CON-repo-hygiene, CON-llm-config. See `/var/www/html/teste/.planning/intel/constraints.md`.

## Context topics: 8
See `/var/www/html/teste/.planning/intel/context.md` (data inconsistencies, scope rationale, pending items, deferred work).

## Conflicts
- 0 blockers, 0 competing variants (warnings), 15 auto-resolved (INFO).
- Detail: `/var/www/html/teste/.planning/INGEST-CONFLICTS.md`

## Open items for the roadmapper
- Default LLM model not chosen (decide in the agent phase, record in docs/DECISIONS.md).
- Search mini-eval result pending measurement.
- Source silent on whether mini-eval keeps the three query groups; and whether golden-set temperature 0 persists.

## Files
- /var/www/html/teste/.planning/intel/decisions.md
- /var/www/html/teste/.planning/intel/requirements.md
- /var/www/html/teste/.planning/intel/constraints.md
- /var/www/html/teste/.planning/intel/context.md
