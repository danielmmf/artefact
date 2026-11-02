# Laboratório de cenários

O lab evolui a v1.0.2 **por cenários**. Cada mudança de arquitetura só entra se um cenário revelar o gargalo concreto que ela resolve; nenhuma tecnologia é adotada por si só.

Este diretório vive no branch `lab/cenarios`. A `main` e as tags `v1.0` a `v1.0.2` não são alteradas.

## Como usar

```sh
make scenario-list            # lista os cenários, uma linha cada
make scenario S=S0-baseline   # explica, prepara os dados, roda e grava reports/scenarios/<nome>/
```

`make scenario S=<nome>` (ou `emporio-lab scenario run <nome>`):
1. imprime a explicação do cenário em linguagem clara, com as condições e os critérios;
2. prepara os dados: a carga é **sintética**, gerada com seed fixa e marcada como sintética (o relatório traz a impressão digital da carga);
3. roda a v1.0.2 (e, nos cenários futuros, a alternativa) nas mesmas condições;
4. grava `report.md` e `report.json` em `reports/scenarios/<nome>/`, com cada critério marcado como atendido ou reprovado e a conclusão.

Critério reprovado é resultado, não erro: o comando sai com 0 e registra. Com `--strict` sai com 1.

## Regras que o código impõe

- Todo cenário mensurável declara, **antes** de rodar, as métricas e os critérios (`scenarios/<nome>.yaml`). A execução é recusada se esse arquivo não estiver commitado, para o histórico provar que os critérios vieram antes da medição.
- Cenário `planejado` tem hipótese e candidata, mas **não pode ser executado**: sem critério não há medição, e sem medição não há conclusão.
- O LLM é **simulado**, com latência artificial configurável. LLM real só numa amostra pequena e dentro do protocolo de custo (ainda não usado).

## Estado

| Cenário | Status | Resumo |
| --- | --- | --- |
| S0-baseline | medido | condições da v1.0.2: 65 produtos, manual de 8 páginas, poucos usuários |
| S1-mil-usuarios | planejado | 1.000 usuários simultâneos |
| S2-catalogo-grande | planejado | 50 mil produtos sintéticos |
| S3-conhecimento-grande | planejado | manual expandido e múltiplos documentos |
| S4-fluxo-com-aprovacao | planejado | pausa para aprovação humana e retomada após reinício |

## S0-baseline

Referência de todos os outros cenários: a v1.0.2 como entregue, sem alternativa. **Hipótese:** com poucos usuários não aparece gargalo no código local; o custo por turno é dominado pelo LLM e pelo manual inteiro no prompt.

**Resultado (relatório [`reports/scenarios/S0-baseline/report.md`](../reports/scenarios/S0-baseline/report.md)):** os cinco critérios pré-registrados foram atendidos (0 erros, 0 contingências, sobrecarga local p95 de 20.1 ms contra o limite de 100 ms, e a busca igual ao publicado: recall@5 0.8 e MRR 0.75). Referências para os próximos cenários: latência do turno p50 609.33 ms e p95 620.41 ms, 8.329 turnos/s, tokens estimados do pedido ao LLM p50 9611 e máximo 11249.

**Ressalvas desta medição:**
- O LLM é simulado (300 ms por chamada, 1.77 chamadas por turno): a conclusão sobre "o LLM é o gargalo" usa essa latência assumida, não a de um provedor real.
- Os tokens são a estimativa conservadora do projeto (bytes÷3). Numa medição anterior com o Groq, o valor real foi cerca de metade do estimado. O p50 inclui o histórico acumulado (até 20 turnos por usuário), por isso é maior que o pedido do primeiro turno.
- Uma execução, sem repetição: não há medida de variância. Foram 5 usuários em threads numa máquina de 20 CPUs.
- A carga sorteia entre os 61 produtos disponíveis (ativos e com estoque) dos 65 do catálogo.

**Conclusão:** Se o cenário mudar para 5 usuários simultâneos, catálogo de 65 produtos e manual de 8 páginas (cerca de 14 mil caracteres) inteiro no prompt de sistema, o gargalo medido foi o LLM e o tamanho do prompt: a sobrecarga local foi 20.1 ms no p95 contra 531 ms de latência simulada do LLM por turno, e o pedido ao LLM tem cerca de 9611 tokens estimados; o código local não é gargalo, e a arquitetura recomendada é v1.0.2 (cenário de referência, sem alternativa medida), pelos números: erros 0, contingências 0, sobrecarga local p95 20.1 ms, latência do turno p95 620.41 ms, 8.329 turnos/s, tokens estimados p50 9611, recall@5 0.8, MRR 0.75.

## S1-mil-usuarios

Hipótese: gargalos de concorrência no SQLite, execução síncrona e custo por turno do manual no prompt. Candidatas: API assíncrona, Postgres para o estado e cache de prompt. Teste de carga com LLM simulado e latência artificial; LLM real só numa amostra pequena.

Status: planejado, critérios pendentes. **Conclusão: nenhuma (sem medição).**

## S2-catalogo-grande

Hipótese: a busca FTS5 perde recall em consultas por intenção. Candidata: Qdrant local com busca híbrida (RRF). Métricas: recall@5, MRR e latência, com dataset de consultas rotulado antes.

Status: planejado, critérios pendentes. **Conclusão: nenhuma (sem medição).**

## S3-conhecimento-grande

Hipótese: o contexto completo deixa de caber ou de ser viável em custo. Candidata: RAG com Qdrant, comparado ao contexto completo.

Status: planejado, critérios pendentes. **Conclusão: nenhuma (sem medição).**

## S4-fluxo-com-aprovacao

Hipótese: o loop próprio não persiste o estado do fluxo entre a pausa e a retomada. Candidata: LangGraph com persistência (substitui a Etapa 4 condicional).

Status: planejado, critérios pendentes. **Conclusão: nenhuma (sem medição).**

A comparação loop próprio × PydanticAI é transversal: roda primeiro no S0 e, havendo tempo, nos demais. Ainda não foi feita.
