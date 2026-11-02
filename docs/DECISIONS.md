# Decisões, suposições e opções rejeitadas

Registro único que substitui as ADRs 001–011 (decisão de escopo, ADR-000 §16). A especificação completa continua em `docs/adr/ADR-000-especificacao-consolidada.md`; este arquivo registra o **porquê** de cada escolha e toda interpretação do manual `políticas_da_loja.pdf` (v2.1).

- **Responsável:** Daniel Medeiros
- **Última revisão:** 2026-10-31

---

## 1. Decisões de arquitetura

| ID | Decisão | Motivo | Status |
| --- | --- | --- | --- |
| DEC-01 (ex-ADR-001) | Loop próprio de function calling com contratos Pydantic. Sem PydanticAI e sem LangGraph | 8 tools e um fluxo linear não justificam framework; o loop próprio deixa autorização, orçamento e validador explícitos e testáveis com ScriptedLLM | Fechada |
| DEC-02 (ex-ADR-002) | `store.db` (SQLite, `mode=ro`) para dados da loja; `app.db` separado para histórico, acesso a pedidos, tentativas e tickets | O atendimento não consegue alterar preço, estoque ou pedido nem por bug nem por injeção | Fechada |
| DEC-03 (ex-ADR-003) | Manual completo no contexto (`data/processed/policies.md`, marcadores `[§seção · p.página]`) em vez de RAG | Manual de 8 páginas cabe no contexto; RAG adicionaria risco de recuperar o trecho errado sem ganho | Fechada |
| DEC-04 (ex-ADR-004) | Busca: SQLite FTS5/BM25 + rapidfuzz; filtros exatos em SQL; índice só ordena IDs | 65 produtos; reprodutível sem rede. Qdrant/denso adiados (§16). Mini-eval de 10 consultas (`evals/search_queries.yaml`, `make bench`): **recall@5 = 0,8 e MRR = 0,75** (`evals/reports/search.json`); amostra pequena, sem pretensão de generalizar | Fechada; medida |
| DEC-05 (ex-ADR-005) | Identidade autenticada **simulada** pelo canal (`--customer <id>`); confirmação de posse **demonstrativa** (pedido + e-mail ou telefone). Produção exige login ou OTP | Os dados não têm credenciais; a verificação por contato é fraca e precisa ser declarada como demonstrativa no README e na CLI | Fechada |
| DEC-06 (ex-ADR-006) | E-mail e telefone tokenizados (`[EMAIL_1]`, `[PHONE_1]`) antes do LLM; mapa só em memória, por sessão; traces, histórico e tickets sem contato | LGPD (§9 do manual) e redução de superfície de vazamento | Fechada |
| DEC-07 (ex-ADR-008) | Adaptador OpenAI-compatible; provedor configurável **somente** por `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` (nenhum nome específico de provedor) | O avaliador pode usar a chave que tiver | Fechada |
| DEC-11 | Modelo padrão: **DeepSeek `deepseek-chat`** (`LLM_BASE_URL=https://api.deepseek.com`); alternativa documentada: Groq `openai/gpt-oss-120b` (parâmetros e limites medidos na seção 8) | Troca de provedor decidida pelo responsável em 2026-11-01: o plano gratuito do Groq (8.000 tokens/min e 200.000/dia) inviabilizava o golden set e as conversas. `deepseek-reasoner` não é usado porque não suporta function calling | Fechada |
| DEC-08 (ex-ADR-009) | Reprodutibilidade: uv com lock, relógio injetável (`EMPORIO_NOW`), `make test` sem chave, sem rede e sem Docker | Requisito do avaliador | Fechada |
| DEC-09 | Valores em centavos (inteiros), expostos como `Decimal` | Evitar erro de arredondamento nos testes de limite | Fechada |
| DEC-10 | Verificação de posse e acesso checados em Python a cada chamada de `get_order` e `check_return_eligibility` | A defesa contra injeção é a autorização no código, não o prompt | Fechada |

## 2. Interpretações do manual (ex-ADR-007)

Todas confirmadas pelo Daniel em 2026-10-31.

| ID | Trecho do manual | Interpretação adotada |
| --- | --- | --- |
| S-a | §3.1: "Parcelamento em até 3x: sem juros, sem valor mínimo de parcela (exceto abaixo de R$ 50,00)." | 2x e 3x exigem parcela ≥ R$ 50,00. 1x não tem mínimo |
| S-b | §3 (tabela): "Até 12x sem juros — Parcela mínima de R$ 100,00" vs §3.1 (faixas) | §3.1 prevalece por ser a regra específica: 4–6x ≥ R$ 80,00; 7–12x ≥ R$ 100,00 (inclusivos) |
| S-c | §5.1: "Frete grátis para pedidos acima de R$ 500,00. Para pedidos abaixo de R$ 500,00, taxa fixa de R$ 35,00." | R$ 500,00 exato tem frete grátis (interpretação mais favorável ao consumidor, CDC art. 47). Testado em 499,99 / 500,00 / 500,01 |
| S-d | §3.1: "Combinação de formas de pagamento: permitida (ex.: PIX + cartão) para compras acima de R$ 2.000,00." | Permitida a partir de R$ 2.000,00, inclusive (mesma lógica de S-c). Testado em 1.999,99 / 2.000,00 |
| S-e | §5.1 não define a base do "pedido" | Base do frete: subtotal com promoção, antes do desconto PIX |
| S-f | §5.1: "Região Metropolitana de Campo Grande" (municípios não listados) | No MVP, só a cidade de Campo Grande. Demais cidades: §5.2 |
| S-g | §4.3: "Trocas por preferência ... em até 7 dias, mediante disponibilidade" (marco inicial não definido) | Contados do recebimento. Sem `received_at`: `insufficient_information` |
| S-h | — | Relógio da demonstração e dos testes: `EMPORIO_NOW=2026-03-25T10:00-04:00` |
| S-i | §5.2: "Instrumentos de grande porte (baterias acústicas, pianos digitais, contrabaixos) **podem exigir** frete especial com cotação individual." | O agente diz que o produto "pode exigir cotação especial", nunca que exige. Lista explícita, sem inferência pela descrição: **135, 136, 137, 138** (categoria 2, "contrabaixo") e **139, 140, 141** (baterias acústicas). Nenhum produto é piano digital. O 136 está descontinuado e não é vendável |
| S-j | §6.2: "O desconto de PIX (5%) não se aplica sobre preços já promocionais." | PIX item a item, só em itens sem promoção ativa |
| S-k | §7.1: "Sugerir lojas parceiras quando possível." | O manual não lista parceiros: acessórios são recusados sem citar lojas |
| S-m | §3 lista PIX, cartão de débito, cartão de crédito e boleto; dinheiro não é mencionado | O agente informa as formas documentadas. Se o cliente perguntar sobre dinheiro, orienta confirmar com a equipe, sem afirmar que aceita nem que recusa. Testado com ScriptedLLM e no golden set |
| S-l | Capa e §1.2: (67) 3341-4444; §7: (67) 3321-4500; e-mail com e sem acento | Contato oficial informado: (67) 3341-4444 e `contato@emporiodamusica.com.br`. Divergências no `QUALITY.md` |
| S-n | §4.1: recebimento declarado pelo cliente (sem comprovação); `estimated_delivery` é só previsão | Se a data de recebimento declarada for mais de **14 dias** posterior à previsão de entrega registrada (ex.: pedido 7, previsão 17/02, cliente diz 20/03), `check_return_eligibility` devolve `divergences` com a nota "a equipe vai conferir"; o status e o prazo continuam calculados sobre a data declarada, o pedido não é negado e a previsão nunca vira data de recebimento (A2). O limite de 14 dias é uma suposição do implementador, **a confirmar** pelo responsável. |

## 3. Tratamento dos dados

| ID | Situação nos dados | Tratamento |
| --- | --- | --- |
| T-1 | Totais divergentes dos itens (pedidos 3 e 20) | Sempre `orders.total_brl`, descrito como "total registrado no pedido"; divergência no `QUALITY.md` sem atribuir causa |
| T-2 | Nome divergente da descrição ou das specs: **135, 136, 137, 139, 140, 142, 144** | Nome e specs são a fonte de verdade. A descrição desses produtos **não é enviada ao LLM** pelas tools; fica só no índice de busca. Teste garante que o agente não cita marca vinda dessas descrições |
| T-3 | Parcelamentos históricos fora da §3.1 (pedidos 9, 16, 18) | Apenas registro no `QUALITY.md`. As regras valem para cotações novas |
| T-4 | Pedidos PIX sem desconto no total (1, 5, 10, 13, 17) | Apenas registro no `QUALITY.md` (coerente com T-1) |
| T-5 | E-mail repetido nos clientes 11 e 43 | A confirmação de posse compara o contato com o cliente **do pedido**, nunca com qualquer cliente que tenha o contato. Teste dedicado |
| T-6 | Nomes de arquivo com espaços (`desafio_tecnico_ai_eng - <tabela>.csv`) | O loader localiza cada CSV pelo sufixo (`categories`, `customers`, `order_items`, `orders`, `products`, `promotions`), tolerando espaços; ausência ou ambiguidade falha a ingestão |
| T-7 | Duas promoções ativas no mesmo produto | Falha na ingestão (não ocorre nos dados atuais; testado com dado sintético) |
| T-8 | Sem data de recebimento nem canal nos pedidos; `estimated_delivery` é previsão | `estimated_delivery` nunca vira data de recebimento; devolução sem data ou canal retorna `insufficient_information` |
| T-9 | Demais inconsistências da ADR-000 §13 | Listadas no `QUALITY.md` gerado pela ingestão |

## 4. Opções rejeitadas (ex-ADR-010)

| Opção | Motivo |
| --- | --- |
| PydanticAI, LangGraph | Ver DEC-01 |
| Firebase/Firestore obrigatório | Dependência externa sem ganho para o protótipo |
| RAG das políticas como caminho principal | Ver DEC-03 |
| Roteador de intenções paralelo ao LLM | Duplica a decisão que o function calling já toma |
| Embeddings via API paga | Quebra a reprodutibilidade sem chave |
| Consulta de pedido por nome do cliente | Nomes não identificam ninguém com segurança |
| Filtro de injeção por palavras-chave | Contornável; a defesa é a autorização em Python |
| Sleep fixo contra ataque de timing | Não resolve; respostas idênticas e bloqueio por tentativas resolvem |

## 5. Adiados (README, "o que eu faria com mais tempo")

Qdrant e busca densa/híbrida · ReplayLLM e `make demo` · adapter Firestore · LLM-as-judge · comando `emporio trace` · login/OTP real · golden set com múltiplas repetições · validador de evidências para estoque, pedido e nome de produto.

## 6. Dependências da fundação

- `rapidfuzz`: fallback lexical determinístico para nomes quando FTS5 não encontra resultados.
- `pydantic`: validação dos contratos e das linhas de entrada.
- `pypdf`: extração local do manual integral, sem serviço externo.
- `python-dotenv`: leitura opcional de configuração local; variáveis do ambiente têm precedência.
- `pytest`: testes automatizados offline.
- `hatchling`: construção do pacote Python.

As versões exatas são registradas em `uv.lock`. Estas dependências não alteram as decisões arquiteturais anteriores.

## 7. Auditoria de coerência e decisões pendentes

S-a a S-l e T-1 a T-9 permanecem como registrados acima; esta seção não altera as interpretações aprovadas. As dependências correntes estão em `pyproject.toml` e `uv.lock`: as bibliotecas de execução listadas na seção 6 incluem `python-dotenv`; `pytest` é dependência de desenvolvimento e `hatchling` é usado no build. O mini-eval usa dez casos locais e mede recall@5 e MRR (`evals/search_queries.yaml`). A ADR §16 prevê golden set de aproximadamente 15 casos com uma repetição; §11 prevê temperatura zero quando suportada. Há **17** casos pré-rotulados em `evals/golden_set.json` (16 originais + o caso 17, adicionado depois da validação independente) e 8 casos em `evals/holdout_set.json` (validação independente, imutável desde `662dfed`), executados com o LLM real por `make eval` (resultados no README e em `evals/reports/`). O modelo padrão está decidido em DEC-11 (detalhes na seção 8).

| Assunto | Estado | Pendência para revisão |
| --- | --- | --- |
| Contatos institucionais divergentes e DEC-06 | RESOLVIDO | Telefone, e-mail e endereço da loja são dados institucionais públicos, não pessoais (§8 abaixo); só contatos de clientes são tokenizados. |
| Projeção do manual para serviço externo | RESOLVIDO | Sem projeção: o manual vai inteiro no prompt (DEC-03), incluindo contatos institucionais (§8 abaixo). |
| Subtotal sem frete para parcelas e pagamento combinado | PENDENTE | Confirmar a base usada atualmente em `quote_payment` com a área comercial. |
| Arredondamento e distribuição de centavos | RESOLVIDO | Decidido pelo responsável em 2026-11-01: n−1 parcelas iguais (piso de total÷n) e a última absorve o resto, de modo que a soma fecha o total exato (ex.: 8x de R$ 2.199,00 = 7 × 274,87 + 274,91). A parcela mínima vale para a menor parcela. Desconto de promoção segue HALF_UP por unidade. |
| Bloqueio persistente por pedido | PENDENTE | Definir desbloqueio, auditoria e mitigação de negação de serviço; o bloqueio atual não expira automaticamente. |
| Contatos compartilhados | PENDENTE | Definir prova adicional e política para contatos compartilhados; a implementação nega a verificação por contato compartilhado. |
| Tickets humanos | PENDENTE | Definir dados úteis e seguros: atualmente o resumo livre é descartado. |
| Estimativa de tokens | PENDENTE | Selecionar tokenizador e margem por modelo; bytes UTF-8/3 é apenas aproximação. |
| Modelo LLM e parâmetros de avaliação | RESOLVIDO | DEC-11 (seção 8); golden set com temperature 0 e 1 repetição, casos e metas inalterados. |

## 8. Decisão do responsável (2026-11-01)

- **Privacidade (ADR-000 §8 e D10, nada além):** e-mails e telefones de clientes são tokenizados antes do LLM; o restante do texto do usuário vai normalmente; argumentos e resultados das tools vão completos, como nos contratos (as tools só devolvem o primeiro nome do cliente). O manual vai inteiro no prompt, com telefone, e-mail e endereço da loja, que são dados institucionais públicos (lista em `emporio.security.contacts.INSTITUTIONAL`).
- **Revisão de egress descartada** por exceder a ADR-000: removidos `src/emporio/egress/`, seus testes e os documentos `EGRESS-REVIEW`, `FUNCTIONAL-EGRESS-STATUS` e `ADAPTADOR-INATIVO`; a admissão por texto exato do golden set violava a regra de honestidade da avaliação.
- **DEC-11 (modelo padrão):** DeepSeek `deepseek-chat` (`LLM_BASE_URL=https://api.deepseek.com`), escolhido pelo responsável em 2026-11-01 no lugar do Groq `openai/gpt-oss-120b`, que permanece como alternativa documentada (`openai/gpt-oss-20b` também). Motivo da troca: o plano gratuito do Groq limita esse modelo a 8.000 tokens/min e 200.000 tokens/dia; cada turno envia o manual inteiro (~4 mil tokens), então o golden set e as conversas reais ficavam inviáveis (turnos de ~1 min e cota diária esgotada na primeira rodada). `deepseek-reasoner` não suporta function calling. Parâmetros comuns: `temperature=0`, `max_tokens=2048`, timeout de 60 s e 2 retentativas em 429/5xx/timeout com backoff de 1 s e 3 s (até 4 retentativas em 429 com espera informada pelo provedor; espera acima de 70 s falha na hora). `reasoning_effort=low` só é enviado a modelos `gpt-oss`. Transporte pela biblioteca padrão (`urllib`), sem dependência nova. Smoke test no DeepSeek em 2026-11-01: turnos de 2 a 4 s.
- **Evidência de valores (revisada em 2026-11-01 após a revisão independente do ChatGPT sobre `12ceae9`):** um valor em R$ da resposta precisa (a) vir de resultado de ferramenta do turno, ou (b) ser a faixa de preço (`min_price`/`max_price`) enviada à busca **e dita pelo cliente na mensagem do turno** (valor inventado pelo modelo e número solto não contam), ou (c) ser um valor do manual **na frase do tema a que pertence**: R$ 35 e R$ 500 só em frases de frete, R$ 50, 80 e 100 só em frases de parcela mínima, R$ 2.000 só em frases de pagamento combinado. Valores do manual nunca valem como preço de produto (a regra anterior os aceitava em qualquer frase). Resíduo: uma frase do tema certo que cite também um preço de produto igual ao valor do manual ainda pode passar. Valores de turnos anteriores da conversa não valem (o agente consulta de novo), e diferenças ou somas calculadas pelo modelo são rejeitadas.

