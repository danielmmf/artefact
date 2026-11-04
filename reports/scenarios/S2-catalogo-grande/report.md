# Relatório do cenário S2-catalogo-grande

> **Dados sintéticos (SINTÉTICO)**, gerados por atributos com seed 20261103. Nenhum LLM, nenhuma API externa de embeddings: modelos baixados uma vez e inferência local.

## Execução

- Commit: `8b83aa855ce6` · código sem alterações: **sim** · critérios pré-registrados antes da execução: **sim** (commit dos critérios `6564570e3c8d`)
- Início 2026-11-04T00:29:17.888045+00:00 · duração 958 s · Python 3.13.15 · Linux-7.0.0-38-generic-x86_64-with-glibc2.43 · 20 CPUs · 14897 MB de RAM
- Configuração escolhida no desenvolvimento (5.000, D): `{'rrf_k': 60, 'profundidade': 100}`; usada em C e D.

## Escala smoke65 (65 produtos)

Qdrant Server 1.20.0 · FastEmbed 0.8.1 · modelo sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (384 dim, apache-2.0).

### Indexação e armazenamento

| Item | Valor |
| --- | --- |
| Embeddings densos | 0.23 s (carregar o modelo: 0.53 s) |
| Embeddings esparsos (BM25) | 0.51 s |
| SQLite + FTS5 (A e D) | — s linhas + — s índice FTS5 |
| Qdrant denso (B), índice pronto | 0.31 s · vetores indexados (contagem do Qdrant): 0 |
| Qdrant híbrido (C), índice pronto | 0.29 s · vetores indexados (contagem do Qdrant; inclui o esparso): 65 |
| Disco: SQLite (com FTS5) | 0.1 MB |
| Disco: embeddings numpy (D) | 0.1 MB |
| Disco: Qdrant denso / híbrido | 1.0 MB / 1.2 MB |
| RAM do servidor Qdrant ocioso (denso / híbrido) | 292.2 MB / 291.0 MB |

### Qualidade (smoke de 10 consultas rotuladas da v1.0.2)

| Estratégia | recall@5 | MRR |
| --- | --- | --- |
| A · SQLite FTS5 + RapidFuzz (original) | 0.8 | 0.75 |
| B · Qdrant denso | 0.7 | 0.5833 |
| C · Qdrant híbrido (BM25 + denso, RRF) | 0.9 | 0.7 |
| D · FTS5 + numpy exato + RRF | 0.85 | 0.69 |

### Latência (ms, índice pronto e cache aquecido, todas as repetições)

| Estratégia | embedding p50 / p95 | índice p50 / p95 | SQLite p50 / p95 | ponta a ponta p50 / p95 | 1ª consulta fria | consultas/s | RSS pico do processo | RSS Qdrant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A · SQLite FTS5 + RapidFuzz (original) | 0.0 / 0.0 | 0.02 / 0.04 | 0.05 / 0.06 | **0.08 / 0.09** | 3 ms | 13095.9 | 48 MB | — |
| B · Qdrant denso | 3.17 / 9.45 | 3.5 / 8.35 | 0.12 / 2.41 | **7.56 / 17.88** | 689 ms | 113.7 | 716 MB | 306.1 |
| C · Qdrant híbrido (BM25 + denso, RRF) | 2.29 / 7.9 | 2.84 / 6.71 | 0.12 / 0.29 | **6.32 / 14.49** | 1227 ms | 138.7 | 717 MB | 306.8 |
| D · FTS5 + numpy exato + RRF | 1.9 / 2.06 | 0.18 / 0.21 | 0.09 / 0.11 | **2.18 / 2.36** | 805 ms | 457.9 | 677 MB | — |

Instabilidade do top-5 entre repetições: A = 0.0000, B = 0.0000, C = 0.0000, D = 0.0000. Concordância de B com a busca densa exata (top-5): 1.0.
Candidatos descartados na confirmação do SQLite (fração das consultas): A = 0.000, B = 0.000, C = 0.000, D = 0.000.

## Escala catalogo5k (5000 produtos)

Qdrant Server 1.20.0 · FastEmbed 0.8.1 · modelo sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (384 dim, apache-2.0).

### Indexação e armazenamento

| Item | Valor |
| --- | --- |
| Embeddings densos | 33.75 s (carregar o modelo: 0.55 s) |
| Embeddings esparsos (BM25) | 0.73 s |
| SQLite + FTS5 (A e D) | 0.027 s linhas + 0.033 s índice FTS5 |
| Qdrant denso (B), índice pronto | 0.73 s · vetores indexados (contagem do Qdrant): 0 |
| Qdrant híbrido (C), índice pronto | 0.79 s · vetores indexados (contagem do Qdrant; inclui o esparso): 5000 |
| Disco: SQLite (com FTS5) | 4.5 MB |
| Disco: embeddings numpy (D) | 7.7 MB |
| Disco: Qdrant denso / híbrido | 19.5 MB / 22.4 MB |
| RAM do servidor Qdrant ocioso (denso / híbrido) | 362.1 MB / 461.2 MB |

### Qualidade por grupo (subconjunto de validação)

| Grupo | n | Métrica | A | B | C | D |
| --- | --- | --- | --- | --- | --- | --- |
| nome_codigo | 40 | precisão@5 | 1.000 | 0.421 | 0.767 | 0.762 |
|  |  | nDCG@5 | 1.000 | 0.394 | 0.708 | 0.722 |
|  |  | hit@5 | 1.000 | 0.600 | 0.925 | 0.925 |
| digitacao | 30 | precisão@5 | 0.818 | 0.212 | 0.558 | 0.558 |
|  |  | nDCG@5 | 0.906 | 0.280 | 0.589 | 0.590 |
|  |  | hit@5 | 0.867 | 0.367 | 0.667 | 0.667 |
| intencao | 60 | precisão@5 | 0.190 | 0.257 | 0.250 | 0.257 |
|  |  | nDCG@5 | 0.419 | 0.414 | 0.512 | 0.486 |
|  |  | hit@5 | 0.517 | 0.550 | 0.567 | 0.567 |
| sinonimos | 30 | precisão@5 | 0.147 | 0.107 | 0.180 | 0.133 |
|  |  | nDCG@5 | 0.248 | 0.210 | 0.306 | 0.248 |
|  |  | hit@5 | 0.333 | 0.200 | 0.433 | 0.267 |
| ambiguas | 20 | precisão@5 | 1.000 | 0.760 | 0.990 | 0.990 |
|  |  | nDCG@5 | 1.000 | 0.780 | 0.993 | 0.993 |
|  |  | hit@5 | 1.000 | 0.850 | 1.000 | 1.000 |
| filtros | 30 | precisão@5 | 0.280 | 0.253 | 0.307 | 0.387 |
|  |  | nDCG@5 | 0.591 | 0.536 | 0.628 | 0.658 |
|  |  | hit@5 | 0.667 | 0.533 | 0.500 | 0.833 |
| sem_correspondencia | 15 | falso positivo | 0.667 | 1.000 | 1.000 | 1.000 |

**Consultas com resposta possível que devolveram lista vazia (validação):** A = 0.011, B = 0.000, C = 0.000, D = 0.000

**Qualidade com filtros (precisão@5 / nDCG@5, validação):**

| Subgrupo | A | B | C | D |
| --- | --- | --- | --- | --- |
| categoria | 0.400 / 0.703 | 0.273 / 0.625 | 0.327 / 0.669 | 0.473 / 0.736 |
| preco | 0.133 / 0.574 | 0.200 / 0.376 | 0.289 / 0.583 | 0.289 / 0.573 |
| disponibilidade_nao | 0.400 / 0.675 | 0.050 / 0.516 | 0.050 / 0.516 | 0.150 / 0.606 |
| disponibilidade_sim | 0.200 / 0.354 | 0.433 / 0.625 | 0.467 / 0.692 | 0.533 / 0.679 |

Violações de filtro no estado atual da base: A = 0, B = 0, C = 0, D = 0.

### Latência (ms, índice pronto e cache aquecido, todas as repetições)

| Estratégia | embedding p50 / p95 | índice p50 / p95 | SQLite p50 / p95 | ponta a ponta p50 / p95 | 1ª consulta fria | consultas/s | RSS pico do processo | RSS Qdrant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A · SQLite FTS5 + RapidFuzz (original) | 0.0 / 0.0 | 1.93 / 3.45 | 0.06 / 0.07 | **2.0 / 3.53** | 5 ms | 521.4 | 53 MB | — |
| B · Qdrant denso | 2.44 / 7.53 | 2.59 / 6.85 | 0.12 / 0.17 | **5.44 / 12.53** | 685 ms | 153.5 | 718 MB | 375.0 |
| C · Qdrant híbrido (BM25 + denso, RRF) | 2.55 / 7.89 | 3.4 / 8.52 | 0.12 / 0.17 | **6.46 / 14.4** | 1209 ms | 130.9 | 720 MB | 446.7 |
| D · FTS5 + numpy exato + RRF | 2.23 / 3.89 | 1.98 / 3.11 | 0.1 / 0.13 | **4.23 / 6.81** | 810 ms | 229.9 | 687 MB | — |

Instabilidade do top-5 entre repetições: A = 0.0000, B = 0.0000, C = 0.0000, D = 0.0000. Concordância de B com a busca densa exata (top-5): 1.0.
Candidatos descartados na confirmação do SQLite (fração das consultas): A = 0.000, B = 0.000, C = 0.000, D = 0.000.

### Integração: o SQLite continua sendo a fonte de verdade

Consulta "violão para quem nunca tocou"; depois da indexação, um produto foi esgotado e outro teve o preço alterado numa cópia do SQLite.

| Estratégia | produto esgotado saiu | candidatos descartados | produto reprecificado segue no resultado |
| --- | --- | --- | --- |
| B | True | 0 | True |
| C | True | 1 | True |
| D | True | 0 | True |

Preço no SQLite agora: 61700 centavos; no payload do Qdrant (do momento da indexação): 60990 centavos. o Qdrant só propôs IDs; estoque e preço vieram de get_product_pricing (SQLite) na hora da resposta.

## Escala catalogo50k (50000 produtos)

Qdrant Server 1.20.0 · FastEmbed 0.8.1 · modelo sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (384 dim, apache-2.0).

### Indexação e armazenamento

| Item | Valor |
| --- | --- |
| Embeddings densos | 367.74 s (carregar o modelo: 0.62 s) |
| Embeddings esparsos (BM25) | 2.61 s |
| SQLite + FTS5 (A e D) | 0.147 s linhas + 0.325 s índice FTS5 |
| Qdrant denso (B), índice pronto | 3.92 s · vetores indexados (contagem do Qdrant): 0 |
| Qdrant híbrido (C), índice pronto | 4.87 s · vetores indexados (contagem do Qdrant; inclui o esparso): 50000 |
| Disco: SQLite (com FTS5) | 44.4 MB |
| Disco: embeddings numpy (D) | 76.8 MB |
| Disco: Qdrant denso / híbrido | 191.4 MB / 213.4 MB |
| RAM do servidor Qdrant ocioso (denso / híbrido) | 380.3 MB / 164.1 MB |

### Qualidade por grupo (subconjunto de validação)

| Grupo | n | Métrica | A | B | C | D |
| --- | --- | --- | --- | --- | --- | --- |
| nome_codigo | 40 | precisão@5 | 1.000 | 0.236 | 0.602 | 0.627 |
|  |  | nDCG@5 | 1.000 | 0.188 | 0.547 | 0.571 |
|  |  | hit@5 | 1.000 | 0.425 | 0.800 | 0.825 |
| digitacao | 30 | precisão@5 | 0.763 | 0.120 | 0.543 | 0.482 |
|  |  | nDCG@5 | 0.861 | 0.185 | 0.571 | 0.546 |
|  |  | hit@5 | 0.800 | 0.267 | 0.767 | 0.667 |
| intencao | 60 | precisão@5 | 0.217 | 0.277 | 0.237 | 0.257 |
|  |  | nDCG@5 | 0.454 | 0.459 | 0.493 | 0.455 |
|  |  | hit@5 | 0.533 | 0.600 | 0.550 | 0.600 |
| sinonimos | 30 | precisão@5 | 0.160 | 0.093 | 0.113 | 0.100 |
|  |  | nDCG@5 | 0.249 | 0.187 | 0.279 | 0.211 |
|  |  | hit@5 | 0.333 | 0.133 | 0.233 | 0.167 |
| ambiguas | 20 | precisão@5 | 1.000 | 0.810 | 0.930 | 0.920 |
|  |  | nDCG@5 | 1.000 | 0.822 | 0.933 | 0.928 |
|  |  | hit@5 | 1.000 | 0.900 | 1.000 | 1.000 |
| filtros | 30 | precisão@5 | 0.247 | 0.300 | 0.333 | 0.307 |
|  |  | nDCG@5 | 0.599 | 0.578 | 0.629 | 0.612 |
|  |  | hit@5 | 0.533 | 0.600 | 0.533 | 0.667 |
| sem_correspondencia | 15 | falso positivo | 0.667 | 1.000 | 1.000 | 1.000 |

**Consultas com resposta possível que devolveram lista vazia (validação):** A = 0.011, B = 0.000, C = 0.000, D = 0.000

**Qualidade com filtros (precisão@5 / nDCG@5, validação):**

| Subgrupo | A | B | C | D |
| --- | --- | --- | --- | --- |
| categoria | 0.364 / 0.699 | 0.327 / 0.657 | 0.382 / 0.688 | 0.400 / 0.695 |
| preco | 0.200 / 0.584 | 0.200 / 0.436 | 0.267 / 0.553 | 0.222 / 0.517 |
| disponibilidade_nao | 0.100 / 0.569 | 0.200 / 0.581 | 0.100 / 0.539 | 0.200 / 0.633 |
| disponibilidade_sim | 0.200 / 0.457 | 0.467 / 0.648 | 0.500 / 0.697 | 0.333 / 0.587 |

Violações de filtro no estado atual da base: A = 0, B = 0, C = 0, D = 0.

### Latência (ms, índice pronto e cache aquecido, todas as repetições)

| Estratégia | embedding p50 / p95 | índice p50 / p95 | SQLite p50 / p95 | ponta a ponta p50 / p95 | 1ª consulta fria | consultas/s | RSS pico do processo | RSS Qdrant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A · SQLite FTS5 + RapidFuzz (original) | 0.0 / 0.0 | 20.82 / 35.74 | 0.1 / 0.13 | **21.0 / 35.96** | 12 ms | 51.1 | 68 MB | — |
| B · Qdrant denso | 2.86 / 7.2 | 5.04 / 8.49 | 0.14 / 0.22 | **8.71 / 13.95** | 703 ms | 109.0 | 719 MB | 398.1 |
| C · Qdrant híbrido (BM25 + denso, RRF) | 3.03 / 7.79 | 5.71 / 10.27 | 0.14 / 0.21 | **9.55 / 15.71** | 1201 ms | 97.5 | 720 MB | 220.5 |
| D · FTS5 + numpy exato + RRF | 2.58 / 5.25 | 15.83 / 26.37 | 0.13 / 0.16 | **18.33 / 30.08** | 848 ms | 58.7 | 755 MB | — |

Instabilidade do top-5 entre repetições: A = 0.0000, B = 0.0000, C = 0.0000, D = 0.0000. Concordância de B com a busca densa exata (top-5): 1.0.
Candidatos descartados na confirmação do SQLite (fração das consultas): A = 0.000, B = 0.000, C = 0.000, D = 0.000.

## Critérios pré-registrados

| Métrica | Medido | Critério | Resultado |
| --- | --- | --- | --- |
| `d_vs_a_delta_ndcg_intencao` | 0.0011 pontos de nDCG | >= 0.05 | reprovado |
| `d_vs_a_ic95_inferior_ndcg_intencao` | -0.0465 pontos de nDCG | > 0 | reprovado |
| `d_vs_a_delta_precisao_nome` | -0.3729 pontos de precisão | >= -0.02 | reprovado |
| `c_vs_d_delta_ndcg_intencao` | 0.0379 pontos de nDCG | >= 0.03 | atendido |
| `c_vs_d_ic95_inferior_ndcg_intencao` | -0.0198 pontos de nDCG | > 0 | reprovado |
| `c_vs_d_delta_precisao_nome` | -0.025 pontos de precisão | >= -0.02 | reprovado |
| `p95_e2e_ms[A]` | 35.96 ms | <= 200 | atendido |
| `violacoes_de_filtro[A]` | 0 resultados | == 0 | atendido |
| `instabilidade_top5[A]` | 0.0 fração | <= 0.01 | atendido |
| `p95_e2e_ms[B]` | 13.95 ms | <= 200 | atendido |
| `violacoes_de_filtro[B]` | 0 resultados | == 0 | atendido |
| `instabilidade_top5[B]` | 0.0 fração | <= 0.01 | atendido |
| `p95_e2e_ms[C]` | 15.71 ms | <= 200 | atendido |
| `violacoes_de_filtro[C]` | 0 resultados | == 0 | atendido |
| `instabilidade_top5[C]` | 0.0 fração | <= 0.01 | atendido |
| `p95_e2e_ms[D]` | 30.08 ms | <= 200 | atendido |
| `violacoes_de_filtro[D]` | 0 resultados | == 0 | atendido |
| `instabilidade_top5[D]` | 0.0 fração | <= 0.01 | atendido |
| `smoke_a_recall_at_5` | 0.8 fração | == 0.8 | atendido |
| `smoke_a_mrr` | 0.75 fração | == 0.75 | atendido |

## Resultado

Os embeddings não demonstraram o ganho mínimo pré-registrado sobre a busca original; nenhuma alternativa é recomendada por esta medição.
