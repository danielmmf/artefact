## Conflict Detection Report

Operation: ingest (MODE new). Inputs: docs/DECISIONS.md (ADR, precedence 0, locked) and docs/adr/ADR-000-especificacao-consolidada.md (ADR, precedence 1, locked). No UNKNOWN classifications, no PRD variants, no SPEC/ADR contradictions across independent documents.

### BLOCKERS (0)

(none)

### WARNINGS (0)

(none)

### INFO (15)

[INFO] Auto-resolved: mutual cross-reference between the two ADRs is not a blocking cycle
  Note: docs/adr/ADR-000-especificacao-consolidada.md cites docs/DECISIONS.md (§14, §16) and docs/DECISIONS.md cites docs/adr/ADR-000-especificacao-consolidada.md (intro, S-/DEC- entries), forming a 2-node cycle in the cross_refs graph. These are citation links, not dependency inclusion, and the owner fixed an explicit order (DECISIONS precedence 0 over ADR-000 precedence 1, per §16), so synthesis does not loop. Synthesis proceeded. Other cross_refs (docs/adr/ directory, políticas_da_loja.pdf, data/processed/policies.md, QUALITY.md) are not part of the ingest set.

[INFO] Auto-resolved: §16 supersedes ADR-000 §2 D9 and §7 (dense/hybrid search, Qdrant)
  Note: ADR-000 §2 D9 allowed "Qdrant local + fastembed só se vencer o benchmark" and §7 defined hybrid/auto backends, RRF and a 10-point Qdrant threshold with 15 to 20 queries. ADR-000 §16 and docs/DECISIONS.md DEC-04 and §5 defer Qdrant and dense/hybrid search; only FTS5 + rapidfuzz remains. DECISIONS/§16 win. Recorded in decisions.md (DEC-04) and requirements.md (REQ-search-lexical).

[INFO] Auto-resolved: §16 removes the demo track (ADR-000 §1 principle 2, §3 A4, §4, §9, §11 "Demo", §12)
  Note: `make demo`, ReplayLLM, `recordings/`, `llm/replay.py`, the "Demo" test group, the `make demo` step in `.github/workflows/ci.yml` and the "demo sem embedding" acceptance criterion are out of scope per §16 ("fora do escopo") and docs/DECISIONS.md §5. §16 wins. The 5 real conversations in `examples/` are kept (REQ-docs-examples).

[INFO] Auto-resolved: §16 simplifies the file layout (ADR-000 §4) and ADR set (§14)
  Note: ADR-000 §4 listed `docs/adr/` ADR-000 to ADR-011, `search/dense.py`, `search/hybrid.py`, `llm/replay.py`, `recordings/` and CLI commands "chat, trace, ingest". §16 and docs/DECISIONS.md replace ADR-001..011 with the single docs/DECISIONS.md and drop those files and the `trace` command. ADR-000 §14 table is kept as history only. Effective layout in constraints.md (CON-architecture-deps).

[INFO] Auto-resolved: evidence validator narrowed to R$ values (ADR-000 §8)
  Note: ADR-000 §8 required R$, stock, order number and product name to appear in the turn's tool results. §16 and docs/DECISIONS.md §5 restrict the validator to R$ values and defer the rest. §16 wins (REQ-agent-validator-rs).

[INFO] Auto-resolved: `emporio trace` command deferred (ADR-000 §10)
  Note: ADR-000 §10 defined the command `emporio trace <session>`. §16 keeps the basic JSONL trace with the same essential fields and defers the command (REQ-trace-jsonl, CON-trace-schema).

[INFO] Auto-resolved: golden set and evaluation scope reduced (ADR-000 §11, §12)
  Note: ADR-000 §11 specified a golden set with "3 repetições, temperatura 0". §16 sets ~15 cases and 1 repetition; LLM-as-judge is deferred. The §12 thresholds (tool accuracy >= 90%, exactness 100%, refusals 100%) are not changed by §16 and are kept. Source is silent on whether temperature 0 persists; it is carried as originally specified.

[INFO] Auto-resolved: search benchmark reduced to a ~10-query mini-eval (ADR-000 §7, §9, §12)
  Note: ADR-000 §7 required 15 to 20 queries in three groups with a fixed recall@5 >= 0,8 decision rule leading to a dense fallback; §9 allowed a one-time embedding download for `make bench`. Per §16 and DEC-04: ~10 queries, recall@5 and MRR of the lexical backend only, no download, result to `evals/reports/` and README. The decision rule is moot because dense is deferred. The source does not say whether the three query groups (name / intent / ambiguous) are kept; flagged for the roadmapper.

[INFO] Auto-resolved: §12 acceptance criteria rewritten by §16
  Note: First criterion becomes `make setup && make test` green in CI; "demo sem embedding" removed; "toda interpretação tem ADR" becomes "toda interpretação está em docs/DECISIONS.md com o trecho do manual"; "Benchmark P2 encerrado" becomes "mini-eval de busca medido"; references to ADR-005 for the demonstrative-verification disclosure now point to docs/DECISIONS.md (DEC-05). Applied in requirements.md.

[INFO] Auto-resolved: Firestore adapter (ADR-000 §2 D13) deferred
  Note: ADR-000 D13 already placed Firestore outside the mandatory core; §16 defers it to the README and DECISIONS §4 rejects mandatory Firebase/Firestore. No conflict, recorded for transparency.

[INFO] Auto-resolved: DECISIONS S-i refines ADR-000 §6 "Cotação especial"
  Note: ADR-000 §6 says "Baterias acústicas, pianos digitais e contrabaixos: `special_quote_required`" in general terms. docs/DECISIONS.md S-i (precedence 0) fixes an explicit list (135, 136, 137, 138, 139, 140, 141; no digital piano exists) and requires the wording "pode exigir cotação especial". DECISIONS wins (REQ-rule-special-quote).

[INFO] Auto-resolved: DECISIONS T-2 refines ADR-000 §5 `get_product` description output
  Note: ADR-000 §5 lists `ProductDetail` with description. docs/DECISIONS.md T-2 withholds the description from the LLM for products 135, 136, 137, 139, 140, 142, 144 (index only). DECISIONS wins (REQ-data-treatment-rules, CON-tool-contracts).

[INFO] Auto-resolved: S-h fixed clock now serves tests only
  Note: ADR-000 §9 and DECISIONS S-h set `EMPORIO_NOW=2026-03-25T10:00-04:00` as the "relógio da demonstração e dos testes". With the demo deferred (§16), the clock applies to tests (CON-reproducibility).

[INFO] Auto-resolved: LLM default model pending; Ollama mention
  Note: ADR-000 D11 says hosted default provider pending and "Ollama opcional"; DECISIONS DEC-07 and §16 make the provider configurable via LLM_BASE_URL, LLM_MODEL, LLM_API_KEY, with default model chosen in the agent phase. Not a contradiction; DEC-07 is the effective text, Ollama stays possible through an OpenAI-compatible endpoint. Open item, not a conflict.

[INFO] Auto-resolved: same-substance overlaps between the two ADRs merged
  Note: DEC-01..DEC-10, S-c/A5, S-g/A2, T-1/A3 and the ADR-000 D-entries describe identical decisions in both documents. They were merged into single entries listing both sources (decisions.md). No contradiction was found between LOCKED ADRs; precedence resolutions above follow ADR-000 §16 (intra-document supersession) and the owner's precedence rule, not a LOCKED-vs-LOCKED contradiction.
