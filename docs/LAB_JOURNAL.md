# Diário do laboratório

Registro cronológico do que foi feito, medido e concluído no `lab/cenarios`. Entradas não são reescritas; correções entram como nova entrada. O histórico da v1 está em [`ENGINEERING_JOURNEY.md`](../ENGINEERING_JOURNEY.md), documento separado, mantido como estava.

## 2026-11-02 · S0-baseline (referência)

A v1.0.2 sem alternativa: 5 usuários, LLM simulado de 300 ms, uma execução. Critérios atendidos; sobrecarga local p95 20,1 ms; gargalo atribuído ao LLM e ao tamanho do prompt. Relatório: `reports/scenarios/S0-baseline/report.md` (imutável). Ressalva já registrada: uma execução, sem variância.

## 2026-11-03 · S0-baseline-comparacao: loop próprio × PydanticAI

### Hipótese

Sem hipótese de superioridade. Expectativa registrada antes de medir (no YAML): se houver diferença, aparece em complexidade e testabilidade, não em desempenho, e nenhum controle de privacidade, acesso ou valores pode ser dispensado pelo framework.

### Implementação

- `src/emporio_lab/pydanticai_agent.py`: `Agent` com `FunctionToolset` de 8 ferramentas tipadas, `deps` injetadas (`RunContext`), `output_validator` + `ModelRetry` para a revalidação de valores, `UsageLimits(request_limit=5)` e `ProcessHistory` para o orçamento. `pydantic-ai-slim` 1.107.9, só no extra `lab` (lockfile atualizado; `pydantic` permaneceu em 2.14.2). Documentação consultada: páginas de Agent e de testes do PydanticAI.
- Camada compartilhada, sem alteração: `ToolRegistry`, repositório, cofre de contatos, `protect_dynamic`, validador monetário, `load_history`/`save_turn`, `trim_history`, prompt e trace. O `ConversationEngine` não é usado pela nova arquitetura.
- `cases.py`: 23 casos funcionais offline com um roteiro de modelo comum às duas arquiteturas, mais verificações independentes (acesso concedido, valor em reais sem respaldo, contato bruto no que chegou ao modelo, ao histórico ou ao cliente).
- `compare.py`: estado isolado por execução (cópia descartável de `store.db`, `app.db` novo), 6 repetições com ordem alternada, passe sequencial com latência zero, medições estáticas, pré-registro verificável por commit e hash. `runner.run` agora aceita várias arquiteturas, o S0 de uma só segue igual.
- Pré-registro: critérios e protocolo no commit `d29111e`; registro (SHA e hash) em commit posterior; a execução só vale se os arquivos forem byte a byte os do commit registrado e o código estiver sem alterações. "Rastreado e limpo" não basta. Um ensaio reduzido do mecanismo precedeu o pré-registro e foi descartado (descrito no protocolo).

### Diferenças relevantes

- Argumento inválido ou ferramenta inexistente: o framework recusa e pede nova tentativa ao modelo, sem chamar o domínio; o loop próprio converte em resultado `invalid_input` e registra no trace. Resposta final e histórico coincidiram nos três casos medidos.
- Esquemas das ferramentas gerados pelo framework: 1.388 tokens contra 1.877. Parte é ruído removível (`title`), parte é perda de informação das minhas assinaturas (sem `Literal` nem restrições). Não corrigido, para não alterar o código medido.
- Prompts: o mesmo manual e as mesmas instruções; −5% de tokens por pedido, todos devidos aos esquemas.

### Erros e dificuldades

- Colisão do parâmetro `name` entre o wrapper `_call` e a ferramenta `get_product`: gerou `TypeError` no meio de uma pilha de dezenas de quadros do framework e foi convertido em contingência segura; só apareceu instrumentando.
- `Agent.override(model=...)` exige modelo na própria chamada nesta versão; `output_retries` está obsoleto; conexões SQLite presas à thread forçaram ferramentas `async`.
- Meus primeiros testes de pré-registro dependiam do YAML ainda não commitado; o commit do código foi refeito (local, não publicado) para ficar verde sem ele.
- Um primeiro ensaio quebrou porque a busca lia `evals/` da cópia isolada; corrigido para ler o repositório real, somente leitura.

### Testes e medições

- 410 testes passando. Novos: arquitetura nativa (não encapsula o engine), as 8 ferramentas expostas com esquemas tipados, `TestModel` sem credenciais (com `ALLOW_MODEL_REQUESTS=False`), paridade nos 20 casos, diferenças conhecidas medidas, três mutações que o conjunto precisa detectar (validador monetário desligado, barreira de privacidade desligada, acesso concedido a quem não é dono), isolamento de estado e as regras do pré-registro.
- Execução oficial: 6 repetições, relatório em `reports/scenarios/S0-baseline/comparison.md`. Todos os critérios atendidos pelas duas; sobrecarga local p95 19,5 ms (17,7–28,2) contra 7,5 ms (7,3–8,1); turno p95 622 contra 609 ms; vazão −1,2%; 257 contra 201 linhas; 16 pacotes e ~8,7 MB a mais; importação 242 contra 80 ms.

### Interpretação (revisada no fechamento, 2026-11-03)

**Duas perguntas distintas.** (1) Vale migrar a v1 existente para PydanticAI? (2) Teria sido melhor começar do zero com ele? O experimento responde só à primeira: migrar não trouxe ganho suficiente nas condições do S0. Nada se conclui sobre a segunda, e não se afirma que o PydanticAI seria pior num projeto novo.

Originalmente registrado: sem regressão funcional e sem ganho prático: o framework cobre o encanamento (laço, retries, validação de argumentos), e os controles que dão valor ao produto continuam sendo código nosso. O desempenho piora pouco em termos absolutos (cerca de 12 ms no p95 local, 2% do turno com LLM de 300 ms). Decisão e limites em `reports/scenarios/S0-baseline/decision.md`: manter o loop próprio na v1.x; resultado conclusivo apenas para as condições do S0, com LLM simulado, uma máquina e implementação feita por quem conhece melhor o loop próprio.

### Fechamento: contagem de linhas, esquemas e observabilidade

- **Linhas.** 201 no loop próprio; 257 no arquivo do PydanticAI, dos quais 46 são a adaptação ao LLM simulado (`# >>> PONTE`) e 211 são orquestração. As duas contagens ficam registradas e nenhum vencedor é declarado por quantidade de código.
- **Esquemas não equivalentes.** `reason`, `category` e `purchase_channel` ficaram como `str` nas ferramentas do PydanticAI, enquanto o registry os declara como `Literal`; restrições numéricas e de tamanho também não aparecem. Uma comparação ideal exigiria contratos equivalentes. Por isso a diferença de tokens (1.388 contra 1.877) não é vantagem do framework. Não corrigido para não alterar o código medido.
- **OpenTelemetry nativo (NÃO TESTADA).** A documentação descreve trace por execução e spans por requisição ao modelo e por chamada de ferramenta, com argumentos e resultados de ferramenta como atributos, exceções nos spans e `include_content=False` para excluir conteúdo; não descreve erros de validação como evento próprio. Fica registrada, **sem teste**, a hipótese de que isso recuperaria a visibilidade perdida sobre argumentos inválidos; há tensão com a política de privacidade do trace.
- **Limitações da comparação.** LLM simulado; uma máquina; 6 repetições; implementação feita por quem conhece melhor o loop próprio; controles de privacidade escritos para o loop próprio e portados; contratos de ferramenta não equivalentes; sem qualidade de linguagem, concorrência na mesma sessão, streaming ou provedor real.
- **Calendário.** O `lab/cenarios` congela junto com a entrega à Artefact. S1 e experimentos posteriores serão publicados em repositório separado, criado a partir do branch congelado, com critérios pré-registrados. O S1 não foi executado.
- Medições, critérios, hashes e relatórios originais, e o código medido, permanecem inalterados.

### Pendências

- `Literal` e restrições nos esquemas do PydanticAI, caso ele seja reavaliado depois do S1.
- Concorrência dentro da mesma sessão, streaming e provedor real não foram exercitados.
- `ENGINEERING_JOURNEY.md` entrou no repositório como estava na cópia local; no fechamento recebeu apenas um adendo datado ao final da seção 7, sem editar o corpo.
