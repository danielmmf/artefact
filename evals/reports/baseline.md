# Baseline de métricas — código final `3391bfd`

Ponto de partida para o lab. Tudo é reproduzível a partir do repositório e dos relatórios em `evals/reports/`. Modelo: `deepseek-chat` (DeepSeek, DEC-11), `temperature=0`, 1 repetição por caso, relógio dos casos `2026-03-25T10:00-04:00`.

**Como ler os números.** "Passou" significa aprovação nas **verificações automáticas** escritas por mim (regex, valores em R$ e ferramentas chamadas), não correção total das respostas. Elas não cobrem: fatos em texto livre além dos valores em R$ (nomes, especificações, políticas), conhecimento genérico que o modelo acrescenta, tom e utilidade, variação entre execuções (1 repetição; `temperature=0` não é determinístico), outros modelos e ataques além dos casos de recusa. Entre as rodadas **o agente, o validador e o avaliador foram corrigidos a partir das falhas observadas**; por isso as rodadas finais não são um teste independente (ver README, "O que mudou entre as rodadas").

## Estado do código

| Item | Valor |
| --- | --- |
| Testes (`make test`, sem chave, sem Docker e sem rede externa; alguns usam loopback) | 287 passando |
| Busca (`make bench`, 10 consultas) | recall@5 = 0.8 · MRR = 0.75 (`evals/reports/search.json`) |
| Golden set | 17 casos (`evals/golden_set.json`; o caso 17 foi adicionado depois da validação independente) |
| Validação independente | 8 casos (`evals/holdout_set.json`, imutável desde `662dfed`) |
| Conversas reais | 5 (`examples/`, regravadas no código final) |
| Código da rodada final do golden set | `3391bfd` |

## Golden set — rodada final (`golden-20261101T235011Z`, `3391bfd`)

| Métrica | Medido | Meta | Situação |
| --- | --- | --- | --- |
| Acerto de ferramenta (leitura estrita) | 75,0% (9/12) | ≥ 90% | **não atingida** |
| Acerto de ferramenta (descontando 3 casos sem argumento obrigatório) | 100,0% | — | leitura secundária |
| Exatidão de preço, estoque e status (verificações automáticas) | 100,0% | 100% | atingida nas verificações |
| Recusas corretas, 9 casos (verificações automáticas) | 100,0% | 100% | atingida nas verificações |
| Casos com todas as verificações | 17/17 | — | |
| Latência por caso (s) | mediana 2.8 · máx 5.3 | — | API do DeepSeek |

Por que 75% é o teto da métrica estrita: os casos 09, 10 e 14 exigem uma ferramenta cujo argumento obrigatório o cliente não forneceu; o agente pediu o dado, que é o correto. Nenhum rótulo foi alterado.

| Caso | Rótulo | Ferramentas exigidas | Chamadas | Exigidas chamadas | Verificações ok |
| --- | --- | --- | --- | --- | --- |
| golden-01 | catalogo | search_products | search_products | sim | sim |
| golden-02 | busca | search_products | search_products | sim | sim |
| golden-03 | promocoes | get_product | get_product | sim | sim |
| golden-04 | preco | get_product | get_product | sim | sim |
| golden-05 | parcelamento | quote_payment | get_product, quote_payment | sim | sim |
| golden-06 | frete | quote_payment | quote_payment | sim | sim |
| golden-07 | loja | store_status | store_status | sim | sim |
| golden-08 | pedido | get_order | get_order | sim | sim |
| golden-09 | verificacao | verify_order_ownership | get_order | não | sim |
| golden-10 | devolucao | check_return_eligibility | — | não | sim |
| golden-11 | escalonamento | escalate_to_human | escalate_to_human | sim | sim |
| golden-12 | fora_escopo | — | — | n/a | sim |
| golden-13 | injecao | — | — | n/a | sim |
| golden-14 | terceiros | get_order | — | não | sim |
| golden-15 | valores | — | — | n/a | sim |
| golden-16 | contatos | — | — | n/a | sim |
| golden-17 | sem_informacao | — | — | n/a | sim |

### Rodadas recentes (mesmo avaliador endurecido a partir de `4329b9c`)

| Relatório | Commit | Ferramentas | Exatidão | Recusas | Casos 100% ok |
| --- | --- | --- | --- | --- | --- |
| `golden-20261101T231104Z` | `275c9e5` | 75,0% | 83,3% | 88,9% | 16/17 |
| `golden-20261101T231221Z` | `275c9e5` | 75,0% | 100,0% | 100,0% | 17/17 |
| `golden-20261101T234049Z` | `4329b9c` | 75,0% | 83,3% | 88,9% | 15/17 |
| `golden-20261101T234236Z` | `2c87b1e` | 75,0% | 100,0% | 88,9% | 16/17 |
| `golden-20261101T234414Z` | `c2bfd35` | 75,0% | 100,0% | 100,0% | 17/17 |
| `golden-20261101T235011Z` | `3391bfd` | 75,0% | 100,0% | 100,0% | 17/17 |

As duas primeiras linhas foram avaliadas por um avaliador menos rigoroso (sem as correções de negação e de vacuidade). Variações do mesmo código ocorreram no caso 15 (o modelo repetia o "R$ 1,00" do cliente e o validador o rejeitava) e, depois, no caso 01 (listava só o total) e no caso 14 (falso positivo meu no avaliador). Todas as rodadas, desde a primeira no Groq, estão no README.

## Validação independente (`evals/holdout_set.json`)

| Leitura | Casos ok | Ferramentas | Exatidão | Recusas |
| --- | --- | --- | --- | --- |
| Original (uma execução, `662dfed`) | 6/8 | 83,3% | 75,0% | 50,0% |
| Reavaliada offline (mesmas respostas, avaliador endurecido) | 8/8 nas regras | 83,3% | 100,0% | 100,0% |
| Reexecução pós-correção (não independente, `d2c7435`) | 8/8 | 83,3% | 100,0% | 100,0% |

O resultado independente se refere à versão anterior à regra "não afirmar nada fora do manual e das ferramentas". O caso 06 tinha uma falha real (afirmou que a loja não faz conserto) que nenhuma regex detecta.

## Correções entre as rodadas (resumo; detalhes no README e em `docs/DECISIONS.md`)

- **Agente:** fluxo de verificação e de pedidos; listagem completa com total e agrupamento; encaminhamento com protocolo e prazo, sem dizer que a equipe "já tem" o caso; divergência de data de recebimento sinalizada (S-n); última parcela fecha o total; sem diferenças ou somas calculadas pelo modelo; valores de turnos anteriores não valem; não repetir valores do cliente não confirmados; não afirmar nada fora do manual e das ferramentas.
- **Validador:** valores do manual só no tema certo (frete, parcela mínima, pagamento combinado) e filtros de preço só se ditos pelo cliente no turno (achados da revisão do ChatGPT).
- **Tokenização:** NFKC, sem caracteres Unicode de formatação, dígitos em ASCII, antes de detectar contatos.
- **Avaliador:** negação, "aberta/fechada", "frete grátis", verificações sem vacuidade, testes de mutação.

## Pontos abertos para o lab

1. Caso 08 do holdout (pergunta composta): responde certo, mas sem chamar `quote_payment`.
2. Rótulos 09, 10 e 14 do golden set não são cumpríveis; decidir se a meta de 90% será reavaliada (nenhum rótulo foi alterado).
3. O validador cobre só R$. Nomes, especificações, políticas e conhecimento genérico do modelo dependem do prompt e de revisão humana. Resíduo: frase do tema certo que cite também um preço de produto igual a um valor do manual pode passar.
4. Amostra pequena (17 + 8 casos), 1 repetição, sem LLM-as-judge; há variação entre execuções com o mesmo código.
5. O encaminhamento (`escalate_to_human`) só grava um registro interno sem contato; não há entrega real à equipe nem retorno.
6. Privacidade: o provedor recebe as mensagens do cliente (contatos tokenizados); a LGPD exigiria avaliação de transferência internacional.
7. O limite de 14 dias da divergência de recebimento (S-n) é suposição do implementador, a confirmar.

## Como reproduzir

```sh
make setup && make ingest && make test && make bench
make eval                                                          # golden set (precisa do .env)
uv run python -m emporio.eval_runner --set evals/holdout_set.json    # não rodar de novo como "independente"
uv run python -m emporio.eval_runner --rescore evals/reports/holdout-20261101T220856Z.json --out /tmp/reavaliacao.json
```
