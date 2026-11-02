# Relatório do cenário S0-baseline

> **Dados sintéticos (SINTÉTICO)**: carga gerada com seed 20261102 (impressão digital `edb50eda18d071e2…`). Catálogo: oficial, 61 produtos disponíveis. LLM: **simulado**, latência artificial de 300 ms por chamada.

## Execução

- Commit: `1cafca7` · cenário (SHA-256): `1d2bf76d1c407a93…` · critérios commitados antes da execução: **sim**
- Início: 2026-11-02T17:57:36.246092+00:00 · Python 3.13.15 · Linux-7.0.0-38-generic-x86_64-with-glibc2.43 · 20 CPUs

## Métricas e critérios

| Métrica | Medido | Critério | Resultado |
| --- | --- | --- | --- |
| `erros_de_execucao` | 0 erros | == 0 | atendido |
| `contingencias_seguras` | 0 respostas | == 0 | atendido |
| `sobrecarga_local_p95_ms` | 20.1 ms | <= 100 | atendido |
| `busca_recall_at_5` | 0.8 fração | == 0.8 | atendido |
| `busca_mrr` | 0.75 fração | == 0.75 | atendido |
| `latencia_turno_p50_ms` | 609.33 ms | — | referência |
| `latencia_turno_p95_ms` | 620.41 ms | — | referência |
| `vazao_turnos_por_s` | 8.329 turnos/s | — | referência |
| `tokens_prompt_estimados_p50` | 9611 tokens | — | referência |
| `tokens_prompt_estimados_max` | 11249 tokens | — | referência |

Cargas: {'conversa': 23, 'horario': 16, 'listagem': 22, 'preco': 39}

## Conclusão

Se o cenário mudar para 5 usuários simultâneos, catálogo de 65 produtos e manual de 8 páginas (cerca de 14 mil caracteres) inteiro no prompt de sistema, o gargalo medido foi o LLM e o tamanho do prompt: a sobrecarga local foi 20.1 ms no p95 contra 531 ms de latência simulada do LLM por turno, e o pedido ao LLM tem cerca de 9611 tokens estimados; o código local não é gargalo, e a arquitetura recomendada é v1.0.2 (cenário de referência, sem alternativa medida), pelos números: erros 0, contingências 0, sobrecarga local p95 20.1 ms, latência do turno p95 620.41 ms, 8.329 turnos/s, tokens estimados p50 9611, recall@5 0.8, MRR 0.75.
