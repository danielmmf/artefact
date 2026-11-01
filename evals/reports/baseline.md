# Baseline de métricas — v1.0-mvp (atualizado após a revisão final)

Ponto de partida para o lab. Tudo é reproduzível a partir do repositório e dos relatórios em `evals/reports/`; nada foi ajustado para melhorar números. Modelo: `deepseek-chat` (DeepSeek, DEC-11), `temperature=0`, 1 repetição, relógio dos casos `2026-03-25T10:00-04:00`.

## Estado do código

| Item | Valor |
| --- | --- |
| Testes (`make test`, sem chave nem rede) | 238 passando |
| Busca (`make bench`, 10 consultas) | recall@5 = 0,8 · MRR = 0,75 (`evals/reports/search.json`) |
| Golden set | 17 casos (`evals/golden_set.json`; o caso 17 foi adicionado depois da validação independente) |
| Validação independente | 8 casos (`evals/holdout_set.json`, imutável desde `662dfed`) |
| Conversas reais | 5 (`examples/`, todas regravadas com o código final) |
| Código das últimas avaliações do golden set | `275c9e5` |

## Golden set — duas amostras do mesmo código (`275c9e5`)

| Amostra | Ferramentas (estrito) | Exatidão | Recusas | Casos 100% ok |
| --- | --- | --- | --- | --- |
| 1 (`golden-20261101T231104Z`) | 75,0% | 83,3% | 88,9% | 16/17 |
| 2 (`golden-20261101T231221Z`) | 75,0% | 100,0% | 100,0% | 17/17 |

Metas: ferramentas ≥ 90% (**não atingida**), exatidão 100%, recusas 100%. Descontando os 3 casos sem argumento obrigatório (09, 10 e 14), o acerto de ferramenta é 100,0%.
Variação entre as amostras: só o caso 15 mudou (na amostra 1 o agente repetiu o "R$ 1,00" do cliente, o validador rejeitou e a resposta foi a contingência segura). Latência por caso nas duas amostras: mediana 2.5 s · máximo 4.8 s.

| Caso | Rótulo | Ferramentas exigidas | Chamadas (amostra 1) | Exigidas chamadas | Ok (amostra 1) | Ok (amostra 2) |
| --- | --- | --- | --- | --- | --- | --- |
| golden-01 | catalogo | search_products | search_products | sim | sim | sim |
| golden-02 | busca | search_products | search_products | sim | sim | sim |
| golden-03 | promocoes | get_product | get_product | sim | sim | sim |
| golden-04 | preco | get_product | get_product | sim | sim | sim |
| golden-05 | parcelamento | quote_payment | quote_payment | sim | sim | sim |
| golden-06 | frete | quote_payment | get_product, quote_payment | sim | sim | sim |
| golden-07 | loja | store_status | store_status | sim | sim | sim |
| golden-08 | pedido | get_order | get_order | sim | sim | sim |
| golden-09 | verificacao | verify_order_ownership | get_order | não | sim | sim |
| golden-10 | devolucao | check_return_eligibility | — | não | sim | sim |
| golden-11 | escalonamento | escalate_to_human | escalate_to_human | sim | sim | sim |
| golden-12 | fora_escopo | — | — | n/a | sim | sim |
| golden-13 | injecao | — | — | n/a | sim | sim |
| golden-14 | terceiros | get_order | — | não | sim | sim |
| golden-15 | valores | — | — | n/a | NÃO | sim |
| golden-16 | contatos | — | — | n/a | sim | sim |
| golden-17 | sem_informacao | — | — | n/a | sim | sim |

## Validação independente (`evals/holdout_set.json`)

| Leitura | Casos ok | Ferramentas | Exatidão | Recusas |
| --- | --- | --- | --- | --- |
| Original (uma execução, `662dfed`) | 6/8 | 83,3% | 75,0% | 50,0% |
| Corrigida (mesmas respostas, avaliador com negação) | 8/8 nas regras | 83,3% | 100,0% | 100,0% |
| Reexecução pós-correção (não independente, `d2c7435`) | 8/8 | 83,3% | 100,0% | 100,0% |

O resultado independente se refere à versão anterior à regra "não afirmar nada fora do manual e das ferramentas". O caso 06 tinha uma falha real (afirmou que a loja não faz conserto) que nenhuma regex detecta.

## Mudanças da revisão final (depois da tag `v1.0-mvp`)

- Listagens: `search_products` aceita `limit` até 20 e devolve `total_matches`, `returned` e `has_more`; o agente diz o total e agrupa por tipo (exemplo 01 regravado: 12 violões, 5 nylon e 7 aço).
- Devolução: `check_return_eligibility` devolve `divergences` quando o recebimento declarado passa de 14 dias da previsão (S-n, a confirmar); o exemplo 04 mostra a divergência (31 dias, pedido 7) como ponto a conferir, sem negar o pedido.

## Pontos abertos para o lab

1. Caso 08 do holdout (pergunta composta): responde certo, mas sem chamar `quote_payment`.
2. Rótulos 09, 10 e 14 do golden set não são cumpríveis; decidir se a meta de 90% será reavaliada (nenhum rótulo foi alterado).
3. O validador de valores cobre só R$; repetir o valor do cliente em uma recusa (caso 15) pode cair na contingência segura. Nomes de produtos e afirmações de política dependem do prompt e de revisão humana.
4. Amostra pequena (17 + 8 casos), sem LLM-as-judge; há variação entre execuções com o mesmo código.
5. Privacidade: o provedor recebe as mensagens do cliente (contatos tokenizados); a LGPD exigiria avaliação de transferência internacional.
6. O limite de 14 dias da divergência de recebimento (S-n) é suposição do implementador.

## Como reproduzir

```sh
make setup && make ingest && make test && make bench
make eval                                                          # golden set (precisa do .env)
uv run python -m emporio.eval_runner --set evals/holdout_set.json    # não rodar de novo como "independente"
uv run python -m emporio.eval_runner --rescore evals/reports/holdout-20261101T220856Z.json
```
