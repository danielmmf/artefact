# GSD KICKOFF — Empório AI / Desafio Artefact

Você é o **Tech Lead e agente principal de implementação** do desafio técnico de AI Engineer da Artefact: um agente de atendimento em Python para a loja fictícia Empório da Música (Campo Grande/MS).

A arquitetura já foi decidida. A referência é **`docs/adr/ADR-000-especificacao-consolidada.md`**. Leia esse arquivo inteiro antes de qualquer outra ação. Sua missão é transformá-lo em um projeto funcional, testado, documentado e reproduzível, usando o fluxo do GSD (discutir → planejar → executar → verificar).

**Nesta sessão está autorizado apenas o planejamento. Não escreva código de produção antes de o roadmap ser aprovado pelo Daniel.**

---

## 1. Insumos

| Arquivo | Papel |
| --- | --- |
| `docs/adr/ADR-000-especificacao-consolidada.md` | Arquitetura, contratos, regras, testes e critérios de aceite |
| `data/raw/desafio_tecnico_ai_eng_-_*.csv` | Dados oficiais (categories, customers, order_items, orders, products, promotions), com os nomes originais |
| `data/raw/políticas_da_loja.pdf` | Manual de políticas v2.1 |
| Enunciado do desafio | Requisitos de entrega (resumidos na seção 6 abaixo) |

Os arquivos de `data/raw/` nunca são editados. Se algum insumo estiver faltando, pare e peça ao Daniel.

## 2. Governança

- A ADR-000 manda. Divergência só com nova ADR e motivo técnico comprovado.
- Nenhuma tecnologia fora da stack da ADR-000 entra sem ADR.
- Nenhuma interpretação vira regra comercial sem trecho do manual ou suposição documentada na ADR-007.
- Não reutilizar código do protótipo experimental anterior. Repositório limpo, commits atômicos e reais.
- Nunca versionar `.env`, chaves, credenciais ou `var/`.
- Não declarar uma fase concluída só porque o código foi escrito: testes rodados, requisitos conferidos, evidências registradas.

## 3. Decisões já fechadas (não reabrir)

Estes pontos diferem de versões anteriores do handoff e prevalecem:

- **Runtime do agente:** loop próprio de function calling com Pydantic. **Não haverá benchmark contra PydanticAI** (decisão do Daniel, ADR-001).
- **`make bench`** é o benchmark de **busca** (P2), não de framework.
- **Pagamento combinado e frete:** limites inclusivos em R$ 2.000,00 e R$ 500,00, como suposições documentadas (ADR-007), pendentes de confirmação.
- **`estimated_delivery`** nunca é data de recebimento; devolução sem data ou canal retorna `insufficient_information`.
- **Verificação por pedido + contato** é demonstrativa; identidade autenticada é simulada pelo canal (`--customer`). Login/OTP fica como requisito de produção.
- **Firestore** fica fora do núcleo; só entra como extra após todos os critérios de aceite.

## 4. Pendências que bloqueiam o planejamento

Pergunte ao Daniel antes de fechar o roadmap:

1. **Prazo exato de entrega** (data e hora). Define o escopo das fases e a data de congelamento do repositório.
2. **Provedor e modelo de LLM** (ADR-008). Necessário a partir da fase do agente.
3. Confirmação das suposições listadas na seção 15 da ADR-000.

## 5. Primeira atividade

1. **Verificar o GSD instalado.** O pacote `@opengsd/get-shit-done-redux` foi, segundo fontes públicas, renomeado para `@opengsd/gsd-core`. Verifique qual está instalado e a versão. Não instale nem atualize nada sem mostrar ao Daniel o que encontrou e pedir confirmação. Não sobrescreva configurações existentes.
2. **Descobrir os comandos disponíveis** pela ajuda do GSD instalado (o nome exato do comando de novo projeto varia entre versões, por exemplo `/gsd:new-project` ou `/gsd-new-project`).
3. **Ler a ADR-000 e inspecionar `data/raw/`**, confirmando que as inconsistências da seção 13 da ADR-000 batem com os arquivos.
4. **Fazer as perguntas da seção 4.**
5. **Inicializar o projeto no GSD**, gerando os artefatos de planejamento (`PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md` ou equivalentes da versão instalada), derivados da ADR-000.
6. **Apresentar para aprovação:** roadmap por fases, dependências entre fases, critérios de aceite por fase, matriz de testes, riscos e estratégia de commits.
7. **Parar e aguardar aprovação.**

## 6. Roadmap sugerido

Ajuste o detalhamento ao prazo informado. A ordem das fases deve ser mantida.

| Fase | Entrega | ADRs | Pronto quando |
| --- | --- | --- | --- |
| 1. Fundação + tracer bullet | Esqueleto, uv, Makefile, CI, ingestão com validação, `store.db` ro, `QUALITY.md`, `policies.md`. **Ponta a ponta mínima:** ScriptedLLM → `get_product` real → resposta → trace JSONL | 000, 002 | CI verde; tracer bullet testado |
| 2. Regras comerciais | Disponibilidade, promoção, PIX por item, parcelamento, combinado, frete, horário | 007 (parte 1) | Todos os testes de limite passam, incluindo R$ 500,00 |
| 3. Pedidos e segurança | Identidade, confirmação de posse, `app.db`, `order_access`, tentativas, devoluções, tokenização de PII | 005, 006, 007 (parte 2) | 100% dos testes de segurança de domínio |
| 4. Busca | FTS5 + rapidfuzz, dataset, `make bench`, denso/Qdrant condicional, fallback `auto` | 004 | Benchmark P2 medido e decisão registrada |
| 5. Agente | Contratos e registry das 8 tools, adaptador LLM, loop, prompt com manual, validador, orçamento, escalonamento | 001, 003, 008 | Testes do agente com ScriptedLLM verdes |
| 6. Qualidade e entrega | Histórico, CLI, `emporio trace`, ReplayLLM, `make demo`, golden set, 5 conversas reais, README | 009, 010 | Todos os critérios da seção 12 da ADR-000 |
| Extra | Adapter Firestore | 011 | Só após a fase 6 |

O tracer bullet da fase 1 existe para descobrir cedo problemas de integração entre ingestão, tool, loop e trace.

## 7. Critérios obrigatórios de entrega

- O avaliador clona e roda: `make setup`, `make ingest`, `make test`, `make demo`, `make eval` (com chave), `make bench`.
- `make test` e `make demo` sem credenciais, Docker, GPU ou serviços externos.
- O demo com ReplayLLM é identificado como simulação e não substitui as 5 conversas reais.
- Cinco conversas reais em `examples/`: catálogo, promoção, consulta protegida de pedido, devolução e tentativa de acesso indevido.
- README com instruções, arquitetura, decisões, limitações, resultados do benchmark e declaração do uso de assistentes de IA (revisão multi-IA da arquitetura + Claude Code com GSD na implementação).

## 8. Ao final de cada fase

1. Rodar os testes relevantes e registrar a saída.
2. Conferir os requisitos atendidos contra a ADR-000.
3. Atualizar o estado no GSD.
4. Fazer commits correspondentes ao trabalho real.
5. Relatar problemas, limitações e decisões pendentes ao Daniel.

O objetivo é um agente confiável e defensável numa entrevista técnica, com engenharia demonstrável, testes e decisões justificadas.
