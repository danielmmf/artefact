# Empório AI — integração demonstrativa offline

Protótipo local para atendimento da Empório da Música. O agente aceita somente um simulador de respostas programadas; não há adaptador LLM real habilitado. A verificação de posse por contato é demonstrativa, e `--customer <id>` define uma identidade simulada: nenhuma das duas é autenticação de produção. A Fase 4 e o gate de privacidade permanecem abertos.

## Arquitetura

```text
CLI com roteiros fixos -> ConversationEngine -> ConversationScriptedLLM
                               |                 (sem rede)
                               +-> ToolRegistry (8 tools, Pydantic)
                               |    +-> regras Python -> StoreRepository -> store.db (somente leitura)
                               |    +-> autorização -> app.db separado
                               +-> histórico tokenizado + trace JSONL de metadados
```

A identidade e o relógio vêm do contexto Python, não dos argumentos do modelo. O loop limita-se a cinco iterações, protege entradas e saídas com tokenização heurística, preserva instruções de sistema e usa uma verificação inicial de valores monetários. Descrições e resultados de ferramentas são dados não confiáveis. A autorização de pedidos é aplicada em Python a cada consulta. Consulte [decisões](docs/DECISIONS.md), [ADR-000](docs/adr/ADR-000-especificacao-consolidada.md) e [matriz de aceite](docs/ACCEPTANCE-MATRIX.md).

## Instalação e execução

Requer Python 3.11+ e `uv`. A instalação pode precisar de rede para obter dependências travadas; após instaladas, ingestão e testes não exigem chave LLM, Docker ou GPU.

```sh
make setup    # uv sync --locked --extra dev
make ingest   # emporio ingest; lê data/raw/ e cria var/store.db e data/processed/
make test     # testes offline
make bench    # miniavaliação local da busca
make chat     # equivale a emporio chat --offline
make eval     # falha explicitamente: adaptador externo bloqueado
```

A CLI é uma **demonstração offline**, não um chatbot com raciocínio real. Escolha `1` para horário, `2` para produto 90 e `sair` para encerrar. `emporio chat --offline --customer 3` configura identidade simulada, sem validar credenciais. A CLI cria os bancos quando necessário, invalida a sessão e fecha as conexões. Para reproduzir o horário, por exemplo:

```sh
EMPORIO_NOW=2026-03-25T10:00:00-04:00 uv run --locked emporio chat --offline
```

A ingestão é reutilizada pelo comando `emporio ingest`; os dados originais não são modificados. `store.db` é aberto somente para leitura; `app.db`, sessões, histórico e traces ficam em `var/`, ignorado pelo Git. O relógio é injetável em Python.

## Ferramentas e limites

| Ferramenta | Função e limite |
| --- | --- |
| `search_products` | Busca lexical e filtros; retorna candidatos, não escolhe produto ambíguo. |
| `get_product` | Detalhes e promoções; retorna ambiguidade quando necessário. |
| `quote_payment` | Cotação, PIX, parcelas e frete; não registra compras. Bases e arredondamento aguardam revisão comercial. |
| `store_status` | Horário local pelo relógio injetado; não cobre feriados. |
| `verify_order_ownership` | Confirmação demonstrativa por pedido e referência de contato; não é login nem OTP. |
| `get_order` | Exige autorização Python; total é o registrado no pedido. Observações livres são omitidas por privacidade. |
| `check_return_eligibility` | Avaliação preliminar após autorização; não aprova devolução e pode exigir dados não disponíveis. |
| `escalate_to_human` | Cria ticket mínimo; resumo livre é descartado, portanto não chega à equipe. |

## Privacidade, trace e segurança

O cofre de contatos fica em memória por sessão, e os contatos reconhecidos são tokenizados antes do simulador. A detecção de texto livre é heurística: não cobre garantidamente todas as formas de contato, nomes ou segredos. O prompt atual inclui o manual integral e contatos institucionais divergentes em claro; sua classificação e tratamento para uso externo aguardam decisão. Consulte [auditoria de privacidade](docs/AUDITORIA-PRIVACIDADE-FASE4.md). Não envie dados a um provedor externo antes da revisão.

O trace JSONL opcional registra hash de sessão com chave efêmera por instância, sequência e UUID de turno, iterações, ferramentas e argumentos omitidos, status, erros, tempos medidos, modelo simulado, tokens desconhecidos `null`, busca, validador, orçamento e autorização abstrata. Não grava prompts, resultados completos ou referências de contato. A sequência reinicia com a instância; erro de gravação do trace não interrompe o atendimento.

Os testes interceptam sockets, resolução de nomes e subprocessos nos caminhos offline que exercitam. Isso não demonstra isolamento universal do processo. Bloqueios persistentes podem causar negação de serviço; contatos compartilhados são negados; nenhuma autenticação real foi implementada.

## Avaliação

`make bench` executa dez consultas locais rotuladas: **Recall@5 = 0,800 e MRR = 0,750**. É uma amostra pequena, não evidência de generalização. O [golden set](evals/golden_set.json) tem 16 casos rotulados antes de execução, abrangendo catálogo, preço, pedidos, loja e ataques. Nenhum caso foi avaliado com LLM real; não existem métricas reais de acerto ou recusa. `make eval` permanece bloqueado até revisão de privacidade e implementação autorizada do adaptador.

## Estratégia e uso de assistentes

A ADR registra revisão de arquitetura com propostas de Claude, ChatGPT, Gemini, DeepSeek e GLM, validadas contra os dados e o manual. Claude Code com GSD foi previsto para planejamento e implementação; GPT/Codex contribuiu para integração offline, testes, trace, CLI e documentação. As decisões pertencem ao responsável pelo projeto; artefatos gerados por assistentes exigem revisão humana e não constituem validação independente de produção.

## O que eu faria com mais tempo

- Avaliar Qdrant e busca densa/híbrida com comparação reproduzível ao baseline lexical.
- Adicionar ReplayLLM, `make demo` e gravações de execuções reais, mantendo-as claramente identificadas.
- Implementar adapter Firestore opcional para `StoreRepository`.
- Investigar LLM-as-judge após avaliação humana e revisão de segurança.
- Criar comando `emporio trace` com controle de acesso e retenção.
- Substituir identidade simulada por login ou OTP real.
- Executar golden set com múltiplas repetições e análise de variância.
- Ampliar o validador de evidências para estoque, número de pedido e nome de produto.

Antes de uso externo, resolver as pendências em `docs/DECISIONS.md`, inclusive modelo, tokenizador, política de contatos, lockout, tickets e avaliação adversarial. O projeto não está pronto para produção.
