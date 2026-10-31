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
| DEC-04 (ex-ADR-004) | Busca: SQLite FTS5/BM25 + rapidfuzz; filtros exatos em SQL; índice só ordena IDs | 65 produtos; reprodutível sem rede. Qdrant/denso adiados (§16). Mini-eval de ~10 consultas mede recall@5 e MRR; resultado no README | Fechada; resultado pendente da medição |
| DEC-05 (ex-ADR-005) | Identidade autenticada **simulada** pelo canal (`--customer <id>`); confirmação de posse **demonstrativa** (pedido + e-mail ou telefone). Produção exige login ou OTP | Os dados não têm credenciais; a verificação por contato é fraca e precisa ser declarada como demonstrativa no README e na CLI | Fechada |
| DEC-06 (ex-ADR-006) | E-mail e telefone tokenizados (`[EMAIL_1]`, `[PHONE_1]`) antes do LLM; mapa só em memória, por sessão; traces, histórico e tickets sem contato | LGPD (§9 do manual) e redução de superfície de vazamento | Fechada |
| DEC-07 (ex-ADR-008) | Adaptador OpenAI-compatible; provedor configurável por `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | O avaliador pode usar a chave que tiver | Fechada; **modelo padrão pendente** (fase do agente) |
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
| S-l | Capa e §1.2: (67) 3341-4444; §7: (67) 3321-4500; e-mail com e sem acento | Contato oficial informado: (67) 3341-4444 e `contato@emporiodamusica.com.br`. Divergências no `QUALITY.md` |

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

- `pydantic`: validação dos contratos e das linhas de entrada.
- `pypdf`: extração local do manual integral, sem serviço externo.
- `python-dotenv`: leitura opcional de configuração local; variáveis do ambiente têm precedência.
- `pytest`: testes automatizados offline.
- `hatchling`: construção do pacote Python.

As versões exatas são registradas em `uv.lock`. Estas dependências não alteram as decisões arquiteturais anteriores.
