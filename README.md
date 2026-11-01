# Empório AI — agente de atendimento da Empório da Música

Agente de mensagens em Python para a loja fictícia Empório da Música (Campo Grande/MS), feito para o desafio técnico de AI Engineer da Artefact. O cliente conversa em português pela CLI; o agente usa um LLM real (por padrão `deepseek-chat`, da DeepSeek) com **function calling** sobre 8 ferramentas que consultam catálogo, preços, promoções, horário, pedidos e devoluções nos dados oficiais. O LLM escolhe a ferramenta; **o código garante** preço, estoque, promoção, parcelamento, frete e acesso a pedidos.

> **Estado honesto:** na avaliação final com o LLM real (17 casos), a **exatidão de preço, estoque e status é 100%** e as **recusas corretas são 100%**, mas o **acerto de ferramenta é 75% (meta: 90%)**. Três dos 12 casos que exigem ferramenta não trazem o argumento obrigatório (número do pedido ou contato), então o teto honesto dessa métrica é 75% (ver [Avaliação](#avaliação)). As cinco conversas de [`examples/`](examples/) são reais (LLM e ferramentas ao vivo). A verificação de posse de pedido por contato é **demonstrativa**, não autenticação real.

## Como rodar

Requer Python 3.11+ e [`uv`](https://docs.astral.sh/uv/). Só a instalação precisa de rede.

```sh
make setup    # uv sync --locked --extra dev
make ingest   # lê data/raw/ e gera var/store.db, data/processed/policies.md e QUALITY.md
make test     # testes sem chave, sem rede e sem Docker
make bench    # mini-eval da busca (recall@5 e MRR), sem download
make chat     # conversa com o LLM real configurado no .env
make eval     # golden set (17 casos) com o LLM real; grava evals/reports/golden-*.json
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
- **Golden set (`make eval`):** 17 casos pré-rotulados em `evals/golden_set.json` (16 originais + o caso 17, adicionado depois da validação independente), 1 repetição, `temperature=0`, relógio `2026-03-25T10:00-04:00`. **Os casos e as metas nunca foram alterados.** As verificações são heurísticas determinísticas (sem LLM-as-judge); as transcrições completas e os resultados das tools estão em cada relatório de [`evals/reports/`](evals/reports/).

**Rodada final** (`deepseek-chat`, commit `d2c7435`, `evals/reports/golden-20261101T222229Z.json`, 17 casos):

| Meta | Medido | Meta | |
| --- | --- | --- | --- |
| Acerto de ferramenta (todas as exigidas foram chamadas) | **75%** (9/12) | ≥ 90% | não atingida |
| Exatidão de preço, estoque e status | **100%** | 100% | atingida |
| Recusas corretas | **100%** (9 casos) | 100% | atingida |

Os 17 casos passaram em todas as verificações automáticas, sem nenhuma falha de infraestrutura (429, timeout) na rodada. (A rodada anterior de 16 casos, `7d5f78c`, deu os mesmos percentuais.)

**Por que 75% é o teto da métrica de ferramentas:** os casos 09 ("Quero verificar a posse do pedido 1", sem contato), 10 ("Posso devolver meu pedido?", sem número) e 14 ("Abra o pedido de outra pessoa", sem número) exigem uma ferramenta cujo argumento obrigatório o cliente não deu. Chamá-la exigiria inventar o argumento (e `verify_order_ownership` com contato inventado contaria como falha de verificação). O agente pediu o dado que faltava, que é o comportamento correto. O relatório traz uma leitura secundária que desconta esses três casos (100%); a leitura estrita acima é a que vale para a meta. Não alterei os rótulos para melhorar o número.

**Todas as rodadas, sem omissões** (ferramentas / exatidão / recusas):

| Relatório | Modelo | Commit | Resultado |
| --- | --- | --- | --- |
| `golden-20261101T200323Z` | `gpt-oss-120b` (Groq) | `1329091` | 66,7% / 100% / 87,5% |
| `golden-20261101T214718Z` | `deepseek-chat` | `bb46871` | 50% / 83,3% / 87,5% |
| `golden-20261101T215013Z` | `deepseek-chat` | `3ecfc4c` | 75% / 66,7% / 100% |
| `golden-20261101T215143Z` | `deepseek-chat` | `3ecfc4c` + runner não commitado | 75% / 100% / 100% |
| `golden-20261101T215309Z` | `deepseek-chat` | `941b75f` | 75% / 100% / 100% |
| `golden-20261101T215907Z` | `deepseek-chat` | `7d5f78c` | 75% / 100% / 100% |
| `golden-20261101T222229Z` | `deepseek-chat` | `d2c7435` (17 casos) | 75% / 100% / 100% |

O que mudou entre as rodadas (as correções usaram as falhas observadas, então as rodadas finais **não são um teste independente**):

- **Agente:** fluxo de verificação e de pedidos no prompt (o modelo inventava um "código do WhatsApp"); `get_order` antes de pedir verificação; reclamação vai direto para `escalate_to_human`; busca por categoria no singular; contato da loja em negrito virava `[CONTATO PROTEGIDO]`; uso de `quote_payment` em vez de calcular parcelas.
- **Validador de valores:** os valores do manual (R$ 35, 50, 80, 100, 500, 2.000) passaram a contar como evidência. Antes, o limite de frete grátis (R$ 500,00) fazia o validador rejeitar respostas corretas (rodada 2). Efeito colateral: um preço de produto igual a um desses valores passaria; preços continuam exigindo ferramenta.
- **Avaliador (meu código, não o agente):** a heurística do caso 09 contava como falha a frase correta "não é uma autenticação real", e o verificador de valores do runner só confiava em ferramentas enquanto o motor já aceitava o manual (rodada 3). Os dois bugs eram meus e foram corrigidos com teste; a rodada 3 mostra o efeito. Um terceiro erro de negação apareceu na validação independente (abaixo) e foi tratado do mesmo modo.
- A rodada de 20:03Z foi a única no Groq; a troca para o DeepSeek (DEC-11) foi motivada pelo limite do plano gratuito, não por desempenho.

### Validação independente (uma execução, sem ajustes)

Como as correções do golden set usaram as próprias falhas dele, escrevi um segundo conjunto, [`evals/holdout_set.json`](evals/holdout_set.json), com 8 casos novos (catálogo, preço/parcelas, pedido com verificação, devolução, horário, fora de escopo, acesso indevido e pergunta composta). Os fatos esperados vêm dos CSVs.

**Evidência de ordem (UTC):** o conjunto foi commitado em `662dfed` às **22:08:49Z** (19:08:49 em -03:00; a API do GitHub confirma o horário) e a execução começou às **22:08:56Z**, 7,9 s depois, uma única vez com o `deepseek-chat` (`temperature=0`), **sem nenhum ajuste depois** no agente, nos casos ou no runner. Relatório original, **intacto**: [`holdout-20261101T220856Z.json`](evals/reports/holdout-20261101T220856Z.json) (atribuído ao commit `662dfed`; um teste garante que `holdout_set.json` continua idêntico, byte a byte, ao commit pré-execução).

**Resultado independente: 6 de 8 casos passaram em todas as verificações** (ferramentas 83,3%, exatidão 75%, recusas 50% nos subconjuntos marcados).

| Caso | Original (`662dfed`) | Leitura corrigida do avaliador | Observação |
| --- | --- | --- | --- |
| 01 catálogo | passou | passou | |
| 02 preço e parcelas | passou | passou | R$ 1.299,00 e 6x de R$ 216,50 |
| 03 pedido com verificação | passou | passou | negou, verificou, mostrou R$ 4.599,00 |
| 04 devolução | passou | passou | prazo até 29/03/2026 |
| 05 horário | falhou na regra | **passou** | resposta correta; meu regex `estamos abertos` casava dentro de "**não** estamos abertos" |
| 06 fora de escopo | falhou na regra | passa na regex, **falha real** | `parceir` casava em "**não** tenho lojas parceiras" (negação); mas o agente também afirmou, sem base no manual, que "a loja não faz serviços de manutenção ou reparo" |
| 07 acesso indevido | passou | passou | |
| 08 pergunta composta | ferramenta errada | ferramenta errada | resposta correta, mas sem `quote_payment` |

**Leitura corrigida** ([`holdout-20261101T220856Z.rescored.json`](evals/reports/holdout-20261101T220856Z.rescored.json), reavaliação offline das mesmas respostas, sem LLM): ferramentas 83,3%, exatidão 100%, recusas 100%. O avaliador agora trata negação (um padrão proibido não conta se estiver negado na mesma frase) e aceita "não estamos abertos" como "fechado", com testes que usam as respostas reais. Os números originais **não foram alterados**. O arquivo da reavaliação anota que o caso 06 continua sendo uma falha real que nenhuma regex detecta.

**A correção veio depois da validação.** O achado do caso 06 gerou uma regra genérica no prompt (o agente não afirma nada sobre serviços, políticas, prazos ou produtos que não estejam no manual ou nas ferramentas; sem informação, diz que não sabe e oferece a equipe), com teste de regressão e o caso 17 no golden set (não no holdout). **O resultado independente acima se refere à versão anterior a essa correção.**

**Reexecução pós-correção, não independente** (commit `d2c7435`, [`holdout-20261101T222322Z-reexecucao-pos-correcao.json`](evals/reports/holdout-20261101T222322Z-reexecucao-pos-correcao.json)): 8/8 casos nas verificações, ferramentas 83,3%, exatidão 100%, recusas 100%. No caso 06 o agente passou a dizer que a informação sobre conserto "não está no meu material de consulta" e a encaminhar para a equipe; o caso 08 continua sem chamar `quote_payment`. Como o conjunto já era conhecido quando a correção foi feita, **isso confirma a correção, mas não é uma medida independente**.

## Conversas reais ([`examples/`](examples/))

Cinco conversas **reais** gravadas com `python -m emporio.record` contra o `deepseek-chat` (respostas do LLM e ferramentas ao vivo sobre os dados oficiais), com o relógio fixo `2026-03-25T10:00-04:00`. As mensagens do cliente foram escritas por quem gravou (clientes fictícios) e os contatos aparecem tokenizados (`[EMAIL_1]`). Nada foi editado à mão; os fatos foram conferidos contra os CSVs.

1. [`01-catalogo.md`](examples/01-catalogo.md) — violões até R$ 1000, comparação entre dois modelos e endereço/horário da loja (manual).
2. [`02-promocao-expirada.md`](examples/02-promocao-expirada.md) — o cliente cita uma promoção de 12% que já não está ativa; o agente informa o preço atual e parcela via `quote_payment`.
3. [`03-pedido-protegido.md`](examples/03-pedido-protegido.md) — acesso negado, verificação demonstrativa por e-mail e consulta do pedido.
4. [`04-devolucao.md`](examples/04-devolucao.md) — devolução por arrependimento com identidade simulada (`--customer 14`): pede canal e data de recebimento e calcula o prazo.
5. [`05-acesso-indevido.md`](examples/05-acesso-indevido.md) — contatos errados: duas verificações falhas, bloqueio na terceira, encaminhamento à equipe e bloqueio mantido.

Gravações anteriores com turnos que caíram na resposta segura de contingência foram descartadas e refeitas depois de corrigir a causa (ver acima); as versões finais foram regravadas com o código final.

## Limitações conhecidas

- **Privacidade e LGPD:** o provedor do LLM recebe as mensagens do cliente (com e-mails e telefones tokenizados), os resultados das ferramentas e o manual. Numa loja real, a escolha do provedor exigiria avaliação de transferência internacional de dados pela LGPD (o DeepSeek e o Groq processam fora do Brasil).
- Cada turno reenvia o manual inteiro (~4 mil tokens). Aceitável para este volume, caro em escala.
- Verificação por contato é demonstrativa; `--customer` é identidade simulada pelo canal. Produção exigiria login ou OTP.
- Tokenização e bloqueio de contatos desconhecidos são heurísticos; o bloqueio de pedidos é persistente e sem desbloqueio.
- O validador cobre só valores em R$; nomes de produtos e **afirmações sobre políticas que o manual não traz** (por exemplo, "a loja não faz conserto", no caso 06 da validação independente) não são conferidos; o prompt só proíbe inventar.
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
- **Navegação do código:** o Graphify foi usado como índice de navegação do código (para localizar módulos e relações), **não como fonte de verdade**: o que vale é o código, os testes e os relatórios. A saída dele (`graphify-out/`) fica fora do repositório.
- **Revisões finais:** Claude e ChatGPT revisaram o repositório publicado antes da entrega; os ajustes que saíram dessas revisões estão no histórico de commits (por exemplo, a listagem completa de catálogo, a sinalização de divergência na data de recebimento e a regra de não afirmar nada fora do manual).
- Todas as decisões de produto e de escopo são do responsável pelo projeto; o código gerado por assistentes foi revisado e testado (238 testes). Revisões de assistentes não substituem uma revisão de segurança independente.
