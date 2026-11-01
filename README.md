# Empório AI — agente de atendimento da Empório da Música

Agente de mensagens em Python para a loja fictícia Empório da Música (Campo Grande/MS), feito para o desafio técnico de AI Engineer da Artefact. O cliente conversa em português pela CLI; o agente usa um LLM real (por padrão `deepseek-chat`, da DeepSeek) com **function calling** sobre 8 ferramentas que consultam catálogo, preços, promoções, horário, pedidos e devoluções nos dados oficiais. O LLM escolhe a ferramenta; **o código garante** preço, estoque, promoção, parcelamento, frete e acesso a pedidos.

> **Estado honesto:** a primeira rodada do golden set com o LLM real **não atingiu todas as metas** (ver [Avaliação](#avaliação)). As correções feitas depois dela ainda não foram remedidas, e as cinco conversas reais de `examples/` ainda não foram gravadas, porque a cota diária do plano gratuito do Groq acabou. Nada foi simulado ou fabricado. A verificação de posse de pedido por contato é **demonstrativa**, não autenticação real.

## Como rodar

Requer Python 3.11+ e [`uv`](https://docs.astral.sh/uv/). Só a instalação precisa de rede.

```sh
make setup    # uv sync --locked --extra dev
make ingest   # lê data/raw/ e gera var/store.db, data/processed/policies.md e QUALITY.md
make test     # testes sem chave, sem rede e sem Docker
make bench    # mini-eval da busca (recall@5 e MRR), sem download
make chat     # conversa com o LLM real configurado no .env
make eval     # golden set (16 casos) com o LLM real; grava evals/reports/golden-*.json
```

Para o LLM real, copie `.env.example` para `.env` e preencha (qualquer provedor compatível com a API de chat completions da OpenAI):

```sh
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat   # não use deepseek-reasoner: não suporta function calling
LLM_API_KEY=...           # nunca versionar; .env está no .gitignore
```

Alternativa documentada: Groq (`LLM_BASE_URL=https://api.groq.com/openai/v1`, `LLM_MODEL=openai/gpt-oss-120b`). O adaptador só envia `reasoning_effort` a modelos `gpt-oss`.

- `uv run emporio chat --customer 3` simula a identidade autenticada do cliente 3 pelo canal (só vê os pedidos dele).
- `uv run emporio chat --offline` roda um roteiro fixo, sem chave, só para demonstrar as ferramentas.
- `EMPORIO_NOW=2026-03-25T10:00:00-04:00` fixa o relógio (usado nos testes, no golden set e nos exemplos).
- `uv run python -m emporio.record --out examples/NN-nome.md --title "..." "mensagem 1" "mensagem 2"` grava uma conversa real em Markdown, com contatos tokenizados.

Cada turno envia o manual inteiro (~4 mil tokens). A troca do Groq (plano gratuito: 8.000 tokens/min e 200.000/dia, turnos de ~1 min) pelo DeepSeek foi motivada por esses limites; o adaptador ainda espera o tempo sugerido pelo provedor em 429 por minuto e falha rápido quando uma cota diária acaba.

## Arquitetura

```text
CLI (emporio chat) ──> ConversationEngine ──> LLM (OpenAI-compatible, HTTP)
                            │  loop de function calling (até 5 iterações)
                            │  tokeniza contatos de clientes antes do LLM
                            │  valida valores em R$ contra os resultados das tools
                            ├──> ToolRegistry (8 tools, contratos Pydantic)
                            │      ├─ regras em Python (preço, PIX, parcelas, frete, horário, devolução)
                            │      ├─ StoreRepository ──> store.db   (somente leitura)
                            │      └─ autorização     ──> app.db     (sessões, acesso a pedidos, tentativas, tickets, histórico)
                            └──> trace JSONL por turno (só metadados) em var/traces/
```

- **Manual no prompt, sem RAG.** As 8 páginas do manual vão inteiras no prompt de sistema (`data/processed/policies.md`, com marcadores `[§seção · p.página]`). É pequeno o bastante para caber, e evita recuperar o trecho errado.
- **Regras comerciais em Python, não no prompt.** Disponibilidade, promoção, PIX por item, parcelamento, pagamento combinado, frete e horário têm testes de limite (por exemplo frete em R$ 499,99 / 500,00 / 500,01).
- **Loop próprio de function calling** com Pydantic, sem framework de agentes: são 8 tools e um fluxo linear, e assim autorização, orçamento de contexto e validador ficam explícitos e testáveis.
- **Busca:** SQLite FTS5/BM25 com fallback fuzzy (rapidfuzz). Filtros exatos em SQL; o índice só ordena IDs.
- **Dinheiro em centavos inteiros**, exposto como `Decimal`. Totais históricos usam sempre `orders.total_brl` ("total registrado no pedido").
- **Duas bases SQLite:** `store.db` aberto com `mode=ro` (o atendimento não consegue alterar preço, estoque ou pedido) e `app.db` separado para estado do atendimento.

### Ferramentas

| Ferramenta | Função e limite |
| --- | --- |
| `search_products` | Busca por texto, categoria (singular/plural, com ou sem acento) e faixa de preço; devolve candidatos, não escolhe produto ambíguo. |
| `get_product` | Detalhes, promoção ativa e promoções inativas; `ambiguous` com candidatos. A descrição é omitida para os 7 produtos cujo nome diverge da descrição (T-2). |
| `quote_payment` | Cotação com PIX (5% só em itens sem promoção), parcelas, pagamento combinado e frete; produtos não vendáveis ficam fora dos totais. |
| `store_status` | Aberto/fechado e próxima abertura pelo relógio injetado; feriados fora do escopo. |
| `verify_order_ownership` | Confirmação **demonstrativa** de posse por pedido + e-mail ou telefone do cliente do pedido. |
| `get_order` | Só com acesso autorizado; devolve o total registrado e só o primeiro nome do cliente. |
| `check_return_eligibility` | Avalia arrependimento (7 dias do recebimento), defeito (30 dias da compra) e preferência; nunca aprova devolução. |
| `escalate_to_human` | Cria ticket sem dados pessoais; retorno em 24 horas úteis. |

## Decisões, suposições e privacidade

Todas as decisões e interpretações do manual estão em [`docs/DECISIONS.md`](docs/DECISIONS.md) (ex.: R$ 500,00 e R$ 2.000,00 inclusivos, parcela mínima de R$ 50 em 2–3x, §3.1 prevalece sobre a tabela da §3, frete antes do PIX, pagamento em dinheiro orienta confirmar com a equipe). A especificação completa é a [ADR-000](docs/adr/ADR-000-especificacao-consolidada.md); o que foi cortado ou adiado pelo prazo está na seção 16. As inconsistências dos dados estão em `data/processed/QUALITY.md` (gerado por `make ingest`).

**Privacidade (ADR-000 §8):** e-mails e telefones de **clientes** viram `[EMAIL_1]`/`[PHONE_1]` antes do LLM, com o mapa só em memória por sessão. O restante do texto do usuário e os resultados das tools vão completos (as tools nunca devolvem contato nem nome completo). Telefones e e-mail **da loja** são dados institucionais públicos e seguem em claro. O trace JSONL só guarda metadados (sessão com hash, ferramentas, status, latências, validador, erros), nunca texto de conversa. A detecção de contatos em texto livre é heurística e não garante cobertura de todos os formatos.

**Segurança de pedidos:** o acesso é verificado em Python a cada chamada, nunca pelo LLM. Pedido inexistente e contato errado dão a mesma resposta; 3 falhas bloqueiam o pedido (persistente, sem desbloqueio automático); o acesso expira em 15 minutos; o contato é comparado com o cliente **do pedido** (o e-mail repetido dos clientes 11 e 43 não abre o pedido do outro).

## Avaliação

- **Busca (`make bench`):** 10 consultas locais; recall@5 = 0,800 e MRR = 0,750. Amostra pequena, sem pretensão de generalizar.
- **Golden set (`make eval`):** 16 casos pré-rotulados em `evals/golden_set.json`, 1 repetição, `temperature=0`, modelo `openai/gpt-oss-120b` (Groq) na primeira rodada, relógio `2026-03-25T10:00-04:00`. Os casos e as metas **não foram alterados**. As verificações são heurísticas determinísticas (sem LLM-as-judge) e as transcrições completas ficam no relatório.

**Primeira rodada** (commit `1329091`, relatório `evals/reports/golden-20261101T200323Z.json`):

| Meta | Medido | Meta |
| --- | --- | --- |
| Acerto de ferramenta (todas as exigidas foram chamadas) | **66,7%** (8/12) | ≥ 90% |
| Exatidão de preço, estoque e status | **100%** | 100% |
| Recusas corretas | **87,5%** (7/8) | 100% |

O que a rodada mostrou:

- **Três casos não são cumpríveis como rotulados** (09, 10 e 14): exigem uma ferramenta, mas o cliente não deu o argumento obrigatório (número do pedido ou contato). Chamar a ferramenta exigiria inventar o argumento, então mesmo um agente correto fica limitado a 9/12 = 75% nessa métrica. O relatório traz uma leitura secundária que desconta esses casos; a leitura estrita acima é a que vale para as metas.
- **Falha de recusa (caso 09):** o agente pediu uma "referência de contato (código do WhatsApp)" que não existe, em vez de pedir e-mail ou telefone e avisar que a confirmação é demonstrativa.
- **Falhas de infraestrutura:** nenhuma nessa rodada. Depois dela, a cota diária do Groq acabou (429 por tokens por dia), o que impediu a nova rodada.

Correções feitas **depois** dessa rodada, usando suas falhas (por isso a próxima rodada não é um teste independente): fluxo de verificação no prompt e na descrição da ferramenta, e e-mail institucional em negrito que virava `[CONTATO PROTEGIDO]`. Antes dela, o smoke test já havia corrigido a busca por categoria no singular e a invenção de produtos após uma busca vazia.

## Conversas reais (`examples/`)

**Pendentes.** Devem ser cinco: catálogo, promoção expirada, pedido protegido com verificação, devolução e acesso indevido, todas gravadas com `python -m emporio.record` contra o LLM real e o relógio fixo. Nenhuma será simulada ou editada à mão.

## Limitações conhecidas

- **Privacidade e LGPD:** o provedor do LLM recebe as mensagens do cliente (com e-mails e telefones tokenizados), os resultados das ferramentas e o manual. Numa loja real, a escolha do provedor exigiria avaliação de transferência internacional de dados pela LGPD (o DeepSeek e o Groq processam fora do Brasil).
- Cada turno reenvia o manual inteiro (~4 mil tokens). Aceitável para este volume, caro em escala.
- Verificação por contato é demonstrativa; `--customer` é identidade simulada pelo canal. Produção exigiria login ou OTP.
- Tokenização e bloqueio de contatos desconhecidos são heurísticos; o bloqueio de pedidos é persistente e sem desbloqueio.
- O validador cobre só valores em R$; nomes de produtos citados pelo modelo não são conferidos (o prompt proíbe inventar).
- A sessão do canal expira em 15 minutos.
- Modelos diferentes podem exigir ajustes de prompt; foram exercitados `openai/gpt-oss-120b` (Groq) e `deepseek-chat`.
- Feriados fora do escopo; "região metropolitana" é só Campo Grande.

## O que eu faria com mais tempo

- Qdrant/busca densa ou híbrida, comparada ao baseline lexical.
- ReplayLLM e `make demo` com gravações de execuções reais.
- Adapter Firestore para o `StoreRepository`.
- LLM-as-judge para o golden set, com múltiplas repetições e análise de variância.
- Comando `emporio trace` com controle de acesso e retenção.
- Login ou OTP reais; política de desbloqueio e auditoria de pedidos bloqueados.
- Validador de evidências também para estoque, número de pedido e nome de produto.
- Reduzir o prompt (manual por seção, cache de prompt do provedor).

## Uso de assistentes de IA

- **Arquitetura:** propostas e revisões cruzadas de Claude, ChatGPT, Gemini, DeepSeek e GLM, validadas contra os CSVs e o manual e consolidadas pelo responsável na ADR-000.
- **Planejamento:** Claude Code com o GSD (`gsd-core`) gerou o `.planning/` (requisitos, roadmap de 5 fases) a partir da ADR-000.
- **Implementação das fases 1 a 4 (offline):** GPT/Codex, em ramos separados, integrados por revisão de Claude Code.
- **Caminho real com LLM, correções do smoke test e do golden set, gravador de conversas e documentação final:** Claude Code.
- Todas as decisões de produto e de escopo são do responsável pelo projeto; o código gerado por assistentes foi revisado e testado (202 testes). Revisões de assistentes não substituem uma revisão de segurança independente.
