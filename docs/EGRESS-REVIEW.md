# Revisão candidata de saída para LLM — offline

**Estado: GO para solicitar revisão técnica independente; NO-GO para rede, provedor ou atendimento real.** A projeção é experimental e ainda não foi aprovada. Nenhum LLM real, smoke test HTTP ou avaliação de modelo foi executado. Não se declara a Fase 4 concluída.

## Evidência e escopo

- Base: `7ea91b759aae4494b9a85d26980d9611f133d10f`. Implementação e testes: `ee700d53c648a4e97182376233f67bb7f71c2a16`. Este relatório é incluído em commit posterior, cujo SHA pode ser conferido no histórico do PR.
- No commit de implementação, `make setup`, `make ingest`, `make bench`, `make test` e `git diff --check` passaram; **182 testes**, sendo 12 casos novos em `tests/test_egress_candidate.py`. Com `UV_OFFLINE=1` e variáveis de LLM removidas após instalação, benchmark lexical: Recall@5 0,800, MRR 0,750. Nenhuma métrica é de LLM.
- O motor continua aceitando apenas `ConversationScriptedLLM`; o adaptador aceita apenas `CaptureTransport`, que não implementa HTTP. Testes interceptam conexão, resolução DNS e subprocessos nos caminhos exercitados; `tests/test_offline_phase4.py` e `tests/test_openai_compat.py` também verificam CLI/eval e variáveis LLM. Isso não constitui isolamento universal do processo.
- A captura de revisão usa mensagens e schemas efetivamente montados pelo motor offline, aplica a projeção experimental e serializa pelo adaptador até a entrada do transporte simulado. Não há ligação automática entre essa projeção e um futuro adaptador de produção. A captura é removida da lista do transporte em `finally`, inclusive em falha de inspeção; não há garantia de apagamento físico nem de cópias feitas por um observador.

## Manual e decisões

`data/processed/policies.md` e a extração integral permanecem intactos. `candidate_prompt` aceita somente o SHA-256 conhecido do manual e o hash conhecido das instruções, verifica seções §1–§10 e substitui telefone, e-mails, endereço e CEP institucionais identificados por marcadores, sem designar contato oficial. Uma alteração de qualquer byte falha fechada para nova revisão. Não há allowlist de contatos em mensagens ou ferramentas dinâmicas. A checagem de hash restringe a evidência à versão exata examinada; não é detector geral de contatos nem aprovação das regras do manual.

Impacto **pendente**: DEC-03 e AGT-04 exigem manual completo no contexto; a candidata suprime contatos e endereço. DEC-06 exige tokenização, enquanto a proposta usa marcadores fixos em conteúdo institucional. Claude e o responsável devem decidir se e como conciliar esses requisitos; nenhuma exceção foi aprovada.

## Inventário da projeção de resultados

Todos os resultados são projetados por nome de ferramenta e campos permitidos; falhas preservam apenas códigos conhecidos, sem mensagens livres. Tipos e enums são restritos. Campos não listados são omitidos; a presença de um campo permitido não garante que sua origem esteja correta ou que seja seguro em todos os cenários.

| Ferramenta | Campos candidatos preservados | Omissões e conflitos |
| --- | --- | --- |
| `search_products` | IDs de produto, disponibilidade, estoque, preços/desconto, total e backend | Nome e categoria textuais não chegam ao modelo; prejudica seleção de produto. |
| `get_product` | ID/categoria numéricos, estoque, disponibilidade, preço/desconto, alternativas estruturadas, indicador de cotação | Nome, descrição, especificações e promoções inativas textuais omitidos; conflito com detalhes do catálogo. |
| `quote_payment` | Produtos e quantidades numéricos, estado, preços e totais, elegibilidade PIX, parcelas numéricas/válidas, frete estruturado e indicador de cotação | Nomes, motivos, modalidades textuais e explicações omitidos; reduz a capacidade de explicar a cotação. |
| `store_status` | Apenas `is_open` | Horários e próxima abertura omitidos; conflito funcional de atendimento. |
| `verify_order_ownership` | `granted` booleano | Contato, referência e prazo omitidos; não habilita verificação externa. |
| `get_order` | Estado, total e itens numéricos | Pedido, nome, observações, rastreio, pagamento e datas omitidos; conflito com ORD-02. |
| `check_return_eligibility` | Estado, dias restantes e aprovação booleana | Condições, datas, exclusões e informação faltante omitidas; conflito com ORD-03. |
| `escalate_to_human` | Apenas sucesso ou erro estruturado | ID e prazo textuais omitidos; ticket continua sem resumo útil. |

A projeção de mensagens omite **todo** texto livre de usuário e assistente e substitui argumentos de ferramentas por `{}`. IDs de chamadas são renumerados localmente. Isso evita o envio dos exemplos adversariais, mas quebra a função conversacional e o reuso de argumentos. Os schemas são os mesmos produzidos pelo registry confiável e são comparados à versão gerada localmente; não são uma autorização para enviar schemas alterados ou dados dinâmicos. Cálculos e autorização no Python original não foram modificados.

## Testes integrados e limitações

Os testes incluem contatos privados e telefones formatados, nome completo, segredo sintético e instruções em descrição de produto, nota de pedido, histórico de outra sessão, token inventado e valor monetário sem evidência. Verificam os segmentos `system`, `user`, `assistant`, `tool` e schemas no JSON capturado; o pedido de terceiro continua negado e o validador exige regeneração para o valor sem evidência. Verificam que sessão e chave fictícia não aparecem no corpo, que a captura é descartada e que alterações no manual ou schemas falham fechadas. Nenhum payload completo é persistido em relatório.

Esses cenários são uma amostra, não prova de ausência universal de dados pessoais ou injeção. Campos numéricos ainda podem ter semântica sensível; conteúdos de schemas, fontes estruturadas, nomes de ferramentas e os próprios dados de negócio precisam de revisão de proveniência. Mensagens livres e argumentos exigem desenho funcional e de privacidade novo antes de uso. A separação de sessões testada depende do contexto confiável e do histórico do motor; não substitui autenticação real.

## Pontos para Gemini e coordenação

1. Decidir formalmente o impacto da projeção em DEC-03, DEC-06 e AGT-04 e como verificar contatos institucionais.
2. Definir políticas seguras e úteis para texto de usuário, histórico, identificadores e argumentos; a projeção atual é deliberadamente inutilizável para atendimento real.
3. Rever as omissões por ferramenta e reconciliar ORD-02/03, catálogo, horário e tickets sem liberar campos livres indiscriminadamente.
4. Auditar proveniência e tipos de campos estruturados, schemas, segredos, tentativas adversariais adicionais e retenção de memória/artefatos.
5. Somente após aprovação específica, projetar e revisar transporte real, autenticação, limites, timeouts, observabilidade e bloqueios de rede. Não liberar API apenas porque esta suíte passou.
