# Protocolo da comparação S0: loop próprio × PydanticAI

Cenário: `scenarios/S0-baseline-comparacao.yaml`. Este protocolo e o YAML são o pré-registro: ficam commitados **antes** de qualquer execução comparativa, e o commit e o hash dos dois arquivos são gravados em `reports/scenarios/S0-baseline/preregistration.json` (também commitado antes da execução).

## Pergunta

O PydanticAI oferece vantagens práticas em relação ao `ConversationEngine` nas condições originais do Empório AI (catálogo de 65 produtos, manual de 8 páginas no prompt, 5 usuários, conversa síncrona)? Não há hipótese de superioridade a provar.

## O que é igual nas duas arquiteturas

- `ToolRegistry` (as 8 ferramentas, contratos Pydantic, regras comerciais, autorização), repositório SQLite e `SecurityStore`.
- Cofre de contatos e `protect_dynamic` (privacidade), validador de valores em reais com a mesma evidência, histórico em SQLite (`load_history`/`save_turn`), orçamento de contexto (`trim_history`), prompt do sistema e trace.
- Relógio fixo (`2026-03-25T10:00:00-04:00`), seed `20261102`, carga sintética idêntica (impressão digital registrada no relatório), mesmo objeto de LLM simulado (`SimulatedLLM`, 300 ms) ou roteirizado (casos funcionais): a arquitetura apenas entrega as mensagens ao mesmo `complete(messages, tools)`.
- Estado isolado: cada execução de cada arquitetura usa uma cópia descartável de `store.db` e um `app.db` novo, então uma execução não aquece nem altera os dados da outra.

## O que é diferente (e é o que se mede)

A orquestração: no PydanticAI, `Agent`, `FunctionToolset` com ferramentas tipadas, `deps` injetadas por `RunContext`, `output_validator` + `ModelRetry`, `UsageLimits(request_limit=5)` e a capacidade `ProcessHistory`. Todo trecho em que o framework não cobre uma regra nossa e foi preciso escrever cola local fica marcado com `# COLA:` no módulo e é contado na decisão. Os esquemas, a serialização das mensagens e as tentativas diante de argumento inválido são do framework e podem diferir; essas diferenças são medidas e documentadas, não escondidas.

## Execução

1. `emporio-lab scenario run S0-baseline-comparacao`.
2. 6 repetições; a ordem alterna (repetições ímpares: v1.0.2 depois PydanticAI; pares: o inverso). Cada repetição executa a carga completa de cada arquitetura em estado isolado, e depois um passe sequencial com um usuário e latência artificial zero (custo local puro).
3. Casos funcionais offline com modelo roteirizado: o mesmo roteiro de decisões nas duas arquiteturas (produto e preço, horário, argumento faltante, pedido sem posse, pedido de outro cliente, contato errado, posse confirmada, devolução, encaminhamento, erro de ferramenta, valor sem evidência recuperável e persistente, contato tokenizado, contato bruto e disfarçado na resposta, limite de iterações, falha do modelo, histórico entre turnos, e três casos de diferença conhecida). As 8 ferramentas precisam ser exercitadas.
4. Registra-se: commit e árvore de `src/emporio_lab`, se o código estava sem alterações, versões, CPUs, carga da máquina antes e depois de cada repetição, dispersão (mediana, mínimo, máximo, desvio) e pré-registro comprovado ou não.

## Critérios (definidos no YAML)

Paridade funcional é exigida: nenhuma concessão indevida de acesso, nenhum preço inventado aceito, nenhuma regressão de privacidade, nenhum caso reprovado, zero divergência entre as arquiteturas nos casos críticos e nos casos com paridade exigida, 8/8 ferramentas cobertas, busca inalterada (recall@5 0,8; MRR 0,75), zero erros e contingências na carga, sobrecarga local p95 ≤ 100 ms. Os critérios por arquitetura valem em **todas** as repetições.

Desempenho, tokens, complexidade e dependências são **referências**: não decidem sozinhos. Mais rápido não significa melhor, e mais código não significa pior.

## Verificação do pré-registro

A execução é recusada, e o relatório marca "NÃO comprovado", a menos que: o registro exista e esteja commitado em commit posterior ao dos critérios; os arquivos atuais sejam, byte a byte, os do commit registrado (`git show <commit>:<arquivo> | sha256sum`); esse commit seja ancestral do atual; e o código (`src/`, `pyproject.toml`, `uv.lock`) esteja sem alterações. "Arquivo rastreado e limpo" isoladamente não é aceito como prova.

## Limites

Nenhum LLM real nem API paga. Os resultados valem para dados sintéticos, LLM simulado e as condições originais; não extrapolam para mil usuários (S1), catálogos maiores ou qualidade de linguagem. Os critérios não são recalibrados a partir do golden set original.

## Transparência sobre o que veio antes do pré-registro

O mecanismo foi ensaiado com uma versão reduzida do cenário (2 usuários × 4 turnos, 5 ms de latência, 3 repetições, `--allow-dirty`, relatório descartado) só para depurar o harness. Esse ensaio sugeriu que a orquestração do PydanticAI custa mais tempo local que o loop próprio; o ensaio não foi usado para escolher nem ajustar nenhum critério, e os limites acima repetem os do S0 original (sobrecarga local p95 ≤ 100 ms). A execução oficial é a única que vale como resultado.
