# Decisão do cenário S2-catalogo-grande

> Dados sintéticos. Critérios pré-registrados em `6564570e3c8d` (pré-registro: **sim**). Sem recalibração depois da medição.

## Veredito

Os embeddings não demonstraram o ganho mínimo pré-registrado sobre a busca original; nenhuma alternativa é recomendada por esta medição.

## As duas perguntas (escala principal, validação)

**1. Os embeddings ajudam? (D contra A)** Não demonstrado pelos critérios.
- nDCG@5, consultas de intenção: +0.0011 (IC95% -0.0465 a +0.0523, 60 consultas de validação)
- precisão@5, consultas por nome e código: -0.3729 (IC95% -0.4913 a -0.2550, 40 consultas de validação)

**2. O Qdrant se justifica? (C contra D)** Não nas condições medidas.
- nDCG@5, consultas de intenção: +0.0379 (IC95% -0.0198 a +0.0976, 60 consultas de validação)
- precisão@5, consultas por nome e código: -0.0250 (IC95% -0.0900 a +0.0150, 40 consultas de validação)
- Via qualidade: não atendida · via latência (D acima de 200 ms de p95 e C dentro): não atendida

## Limites operacionais (p95 ponta a ponta, violações de filtro, instabilidade)

| Estratégia | p95 ms | violações | instabilidade | dentro dos limites |
| --- | --- | --- | --- | --- |
| A · SQLite FTS5 + RapidFuzz (original) | 35.96 | 0 | 0.0000 | True |
| B · Qdrant denso | 13.95 | 0 | 0.0000 | True |
| C · Qdrant híbrido (BM25 + denso, RRF) | 15.71 | 0 | 0.0000 | True |
| D · FTS5 + numpy exato + RRF | 30.08 | 0 | 0.0000 | True |

## O que esta medição não conclui

(1) O ramo lexical de C (BM25 do FastEmbed, com stemming em português) e o de D (FTS5 unicode61, sem stemming) são diferentes: parte da diferença C-D pode vir do léxico, não do Qdrant. (2) Rótulos sintéticos por atributos: medem generalização nesse gerador, não comportamento de clientes reais. (3) O modelo denso é o quantizado do FastEmbed. (4) Abstenção (limiar de similaridade) não é calibrada; consultas sem correspondência medem só a taxa de resultados devolvidos. (5) Vazão medida com um cliente sequencial. (6) Uma máquina, 20 CPUs, Docker local.

- Rótulos e catálogo sintéticos: o resultado vale para este gerador e este modelo de embeddings; outro domínio, outro idioma de consulta ou outro modelo podem mudar a conclusão.
- Nenhum vencedor global é declarado: a decisão é só sobre as duas perguntas acima, na escala de 50.000 produtos, com uma máquina.
