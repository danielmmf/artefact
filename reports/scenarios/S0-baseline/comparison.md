# Comparação do cenário S0-baseline-comparacao: v1.0.2 × pydantic-ai

> **Dados sintéticos (SINTÉTICO)**: seed 20261102 (`edb50eda18d071e2…`), oficial, 61 produtos disponíveis. LLM **simulado** (300 ms por chamada); nenhuma API paga ou real foi usada. O relatório original do S0 (`report.md`) segue intacto.

## Execução e pré-registro

- Commit medido: `af9d9b6dff3f` · árvore `src/emporio_lab`: `045bd80b7435` · código sem alterações: **sim**
- Critérios: commit `d29111e9064a`, SHA-256 do cenário `12ce92d68cfde936…`; pré-registro comprovado: **sim**
- Início 2026-11-03T22:01:08.518649+00:00 · Python 3.13.15 · Linux-7.0.0-38-generic-x86_64-with-glibc2.43 · 20 CPUs · pydantic 2.14.2, pydantic-ai-slim 1.107.9, pydantic-graph 1.107.9

## Repetições (ordem alternada)

| Repetição | Ordem | Carga da máquina (1 min) antes → depois | sobrecarga local p95 (ms) v1.0.2 | pydantic-ai |
| --- | --- | --- | --- | --- |
| 1 | v1.0.2 → pydantic-ai | 0.99 → 0.72 | 7.55 | 28.2 |
| 2 | pydantic-ai → v1.0.2 | 0.72 → 0.59 | 8.08 | 17.67 |
| 3 | v1.0.2 → pydantic-ai | 0.59 → 0.46 | 7.42 | 21.55 |
| 4 | pydantic-ai → v1.0.2 | 0.46 → 0.3 | 7.63 | 17.65 |
| 5 | v1.0.2 → pydantic-ai | 0.3 → 0.2 | 7.29 | 19.67 |
| 6 | pydantic-ai → v1.0.2 | 0.2 → 0.27 | 7.54 | 19.32 |

## Métricas lado a lado

Valores: mediana das repetições [mínimo–máximo]. Critérios valem em TODAS as repetições.

| Métrica | Unidade | v1.0.2 | pydantic-ai | Critério | v1.0.2 | pydantic-ai |
| --- | --- | --- | --- | --- | --- | --- |
| `erros_de_execucao` | erros | 0 | 0 | == 0 | atendido | atendido |
| `contingencias_seguras` | respostas | 0 | 0 | == 0 | atendido | atendido |
| `sobrecarga_local_p95_ms` | ms | 7.545 [7.29–8.08] | 19.495 [17.65–28.2] | <= 100 | atendido | atendido |
| `busca_recall_at_5` | fração | 0.8 | 0.8 | == 0.8 | atendido | atendido |
| `busca_mrr` | fração | 0.75 | 0.75 | == 0.75 | atendido | atendido |
| `casos_reprovados` | casos | 0 | 0 | == 0 | atendido | atendido |
| `concessoes_indevidas_de_acesso` | acessos | 0 | 0 | == 0 | atendido | atendido |
| `precos_inventados_aceitos` | respostas | 0 | 0 | == 0 | atendido | atendido |
| `regressoes_de_privacidade` | casos | 0 | 0 | == 0 | atendido | atendido |
| `ferramentas_cobertas` | ferramentas | 8 | 8 | >= 8 | atendido | atendido |
| `divergencias_em_casos_criticos` (par) | casos | 0.0 | | == 0 | atendido | |
| `divergencias_em_casos_com_paridade` (par) | casos | 0.0 | | == 0 | atendido | |
| `latencia_turno_p50_ms` | ms | 605.445 [604.81–606.29] | 611.155 [610.79–613.16] | — | referência | referência |
| `latencia_turno_p95_ms` | ms | 608.795 [608.46–610.16] | 621.925 [619.1–628.26] | — | referência | referência |
| `sobrecarga_local_p50_ms` | ms | 4.62 [4.16–5.31] | 10.495 [10.15–12.5] | — | referência | referência |
| `vazao_turnos_por_s` | turnos/s | 8.447 [8.438–8.473] | 8.342 [8.309–8.37] | — | referência | referência |
| `seq_primeiro_turno_ms` | ms | 4.72 [4.29–5.73] | 8.735 [7.47–9.72] | — | referência | referência |
| `seq_sobrecarga_p50_ms` | ms | 3.48 [2.83–3.72] | 6.475 [6.13–6.68] | — | referência | referência |
| `seq_sobrecarga_p95_ms` | ms | 4.245 [3.42–4.48] | 9.565 [7.73–12.36] | — | referência | referência |
| `chamadas_llm_por_turno` | chamadas | 1.77 | 1.77 | — | referência | referência |
| `tokens_prompt_estimados_p50` | tokens | 9611 | 9122 | — | referência | referência |
| `tokens_prompt_estimados_max` | tokens | 11249 | 10760 | — | referência | referência |
| `tokens_esquemas_ferramentas` | tokens | 1877 | 1388 | — | referência | referência |
| `loc_orquestracao` | linhas | 201 | 257 | — | referência | referência |
| `loc_ponte_de_teste` | linhas | 0 | 46 | — | referência | referência |
| `pontos_de_cola` | pontos | 0 | 10 | — | referência | referência |
| `pacotes_adicionais` | pacotes | 0 | 16 | — | referência | referência |
| `tamanho_dependencias_adicionais_kb` | KB | 0 | 8676 | — | referência | referência |
| `tempo_importacao_ms` | ms | 79.6 | 241.5 | — | referência | referência |
| `razao_sobrecarga_local_p95_ms` (par) | razão | 2.584 | | — | referência | |
| `razao_latencia_turno_p95_ms` (par) | razão | 1.022 | | — | referência | |
| `razao_vazao_turnos_por_s` (par) | razão | 0.988 | | — | referência | |
| `razao_seq_sobrecarga_p50_ms` (par) | razão | 1.861 | | — | referência | |

## Casos funcionais offline

| Caso | Crítico | Ferramentas | v1.0.2 | pydantic-ai | Paridade | Divergências |
| --- | --- | --- | --- | --- | --- | --- |
| produto-e-preco | sim | get_product | ok | ok | exigida | nenhuma |
| busca-de-produtos |  | search_products | ok | ok | exigida | nenhuma |
| cotacao | sim | quote_payment | ok | ok | exigida | nenhuma |
| horario |  | store_status | ok | ok | exigida | nenhuma |
| argumento-faltante |  | get_product | ok | ok | exigida | nenhuma |
| pedido-sem-posse | sim | get_order | ok | ok | exigida | nenhuma |
| pedido-de-outro-cliente | sim | get_order, check_return_eligibility | ok | ok | exigida | nenhuma |
| posse-com-contato-errado | sim | verify_order_ownership, get_order | ok | ok | exigida | nenhuma |
| posse-confirmada | sim | verify_order_ownership, get_order | ok | ok | exigida | nenhuma |
| devolucao-do-proprio-pedido |  | check_return_eligibility | ok | ok | exigida | nenhuma |
| encaminhamento |  | escalate_to_human | ok | ok | exigida | nenhuma |
| erro-de-ferramenta |  | get_product | ok | ok | exigida | nenhuma |
| preco-sem-evidencia-corrigido | sim | — | ok | ok | exigida | nenhuma |
| preco-sem-evidencia-persistente | sim | — | ok | ok | exigida | nenhuma |
| contato-tokenizado | sim | — | ok | ok | exigida | nenhuma |
| contato-na-resposta-do-modelo | sim | — | ok | ok | exigida | nenhuma |
| contato-ilegivel-na-resposta | sim | — | ok | ok | exigida | nenhuma |
| limite-de-iteracoes |  | store_status | ok | ok | exigida | nenhuma |
| falha-do-modelo |  | — | ok | ok | exigida | nenhuma |
| historico-entre-turnos |  | — | ok | ok | exigida | nenhuma |
| ferramenta-inexistente |  | — | ok | ok | diferença conhecida | dominio |
| argumentos-nao-json |  | get_product | ok | ok | diferença conhecida | dominio |
| tipo-de-argumento-invalido |  | get_order | ok | ok | diferença conhecida | dominio |

### Diferenças de orquestração observadas (casos sem paridade exigida)

- **ferramenta-inexistente**: v1.0.2 → chamadas ao domínio: [['unknown', '{}', False, 'invalid_input']], chamadas ao LLM: 2; pydantic-ai → chamadas ao domínio: nenhuma, chamadas ao LLM: 2
- **argumentos-nao-json**: v1.0.2 → chamadas ao domínio: [['get_product', 'null', False, 'invalid_input']], chamadas ao LLM: 2; pydantic-ai → chamadas ao domínio: nenhuma, chamadas ao LLM: 2
- **tipo-de-argumento-invalido**: v1.0.2 → chamadas ao domínio: [['get_order', '{"order_id": "abc"}', False, 'invalid_input']], chamadas ao LLM: 2; pydantic-ai → chamadas ao domínio: nenhuma, chamadas ao LLM: 2

## Complexidade e dependências

| Medida | v1.0.2 | pydantic-ai |
| --- | --- | --- |
| loc_orquestracao | 201 | 257 |
| loc_ponte_de_teste | 0 | 46 |
| pontos_de_cola | 0 | 10 |
| pacotes_adicionais | 0 | 16 |
| tamanho_dependencias_adicionais_kb | 0 | 8676 |
| tempo_importacao_ms | 79.6 | 241.5 |
| bytes_esquemas_ferramentas | 5567 | 4102 |
| tokens_esquemas_ferramentas | 1877 | 1388 |

Pacotes adicionais trazidos pelo PydanticAI: anyio, certifi, genai-prices, griffelib, h11, httpcore, httpcore2, httpx, httpx2, httpx2-jsfetch, idna, logfire-api, opentelemetry-api, pydantic-ai-slim, pydantic-graph, truststore.

Cargas: {'conversa': 23, 'horario': 16, 'listagem': 22, 'preco': 39}

A interpretação e a decisão estão em `decision.md` e em `docs/LAB_JOURNAL.md`.
