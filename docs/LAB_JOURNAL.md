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

## 2026-11-03 · S2-catalogo-grande: protocolo, critérios e ensaio de desenvolvimento

### Hipótese e pergunta

A busca FTS5 perde qualidade nas consultas por intenção (a hipótese do cenário desde o início do lab). O desenho separa duas perguntas: (1) os embeddings ajudam? (D contra A) e (2) o Qdrant se justifica? (C contra D). Se D empatar com C, o registro será que os embeddings valem a pena e o Qdrant ainda não. Não há expectativa de que o Qdrant vença; o cenário existe para descobrir se vale a pena, não para provar que é necessário.

### O que foi construído

- `src/emporio_lab/s2/`: léxicos (`lexicon.py`), gerador de catálogo por atributos (`catalog.py`), consultas rotuladas (`queries.py`), verificação de vocabulário (`vocab.py`), as quatro estratégias e a confirmação no SQLite (`strategies.py`), indexação (`build.py`), worker de medição por processo (`worker.py`), métricas, avaliação e orquestração (`metrics.py`, `evaluate.py`, `run.py`).
- `scenarios/S2-catalogo-grande.yaml` (parâmetros e critérios), `docs/S2-PROTOCOLO.md`, `docker/qdrant/s2-servers.sh` (Qdrant `v1.20.0` fixado por digest, um servidor por estratégia), `evals/s2_consultas.json` (450 consultas rotuladas, verificadas por hash contra o gerador).
- Dependências do extra `lab`: fastembed 0.8.1, qdrant-client 1.20.0, numpy 2.5.4 (lockfile atualizado). O modelo (`paraphrase-multilingual-MiniLM-L12-v2`, ONNX quantizado, 384 dim, Apache-2.0, 0,22 GB) e o BM25 português do FastEmbed foram baixados uma vez; indexação e consultas são locais.
- A implementação original de busca (`SQLiteRepository.search_product_ids`) e as regras comerciais não foram alteradas; a estratégia A chama o código original.

### Verificações feitas antes de medir

- **BM25 do Qdrant em português:** o modelo `Qdrant/bm25` do FastEmbed aceita `language='portuguese'` e carrega o stemmer Snowball português e uma lista de stopwords portuguesa (verificado no código e numa consulta de teste: "violões confortáveis para iniciante" virou 3 termos, sem "para"). Não é uma limitação.
- **Confusão declarada:** o ramo lexical de C (BM25 com stemming) e o de D (FTS5 sem stemming) são diferentes; parte de uma diferença C−D pode ser do léxico, não do Qdrant.
- **Separação de vocabulário:** as frases de nível e uso das consultas são disjuntas das das descrições (radicais Snowball, exceto 9 radicais de domínio listados em `ALLOWED_STEMS`), verificado na fonte e no catálogo realizado de 50.000. A primeira versão dos léxicos tinha 43 colisões (palavras como "grave", "casa", "linha" estavam nas frases de ruído e de preço das descrições); foram reescritas até a verificação passar. Os sinônimos de tipo repetem palavras genéricas do catálogo ("grave", "escala"): fração média de radicais presentes 0,42, registrada como informativa.
- **HNSW:** abaixo de ~10 MB de vetores densos o Qdrant não constrói o grafo; em 5.000 produtos (7,7 MB) B e C varrem os vetores sem HNSW. Só a escala de 50.000 exercita o índice aproximado.

### Erros e dificuldades

- O contêiner do Qdrant não subiu como usuário comum (`Permission denied` ao criar `.qdrant-initialized` no diretório de trabalho) nem com o `entrypoint.sh` (caminho relativo); resolvido com `--workdir` no volume de dados, `--entrypoint /qdrant/qdrant` e `--config-path`. `docker compose` não existe nesta máquina, então o servidor sobe por script.
- O Docker Compose pareceu a escolha natural, mas não está instalado: o arquivo `docker-compose` que escrevi primeiro foi descartado sem uso.
- **Contenção de threads:** com BLAS em várias threads o produto escalar de D ficou 2 a 3 vezes mais lento depois que o ONNX Runtime foi carregado (microbenchmark: 2,3 ms com 1 thread contra 4,2 a 5,3 ms), e o embedding da consulta em D levou 17 ms contra 3,5 ms em B. Todos os processos de medição rodam com BLAS em 1 thread (registrado no YAML e no protocolo).
- **Desempate do RRF do Qdrant (achado):** no ensaio de desenvolvimento, a mesma consulta no mesmo índice híbrido devolveu ordens diferentes em 91 de 450 consultas (5 execuções cada, no mesmo processo); com 65 produtos, 33% das consultas variavam entre execuções. Não é o modelo nem o índice: B (só denso) estável, D estável. Os empates de score do RRF não têm ordem definida no servidor 1.20.0. B e C passaram a reordenar no cliente por `(-score, id)`; com isso 0 de 450 consultas variam. O critério `instabilidade_top5 <= 0.01` fica como foi escrito.
- `du` somando tamanhos aparentes dava 622 MB para 65 pontos (arquivos esparsos do Qdrant); a medição de disco usa blocos alocados.

### Ensaio de desenvolvimento (descartado)

Um ensaio com as escalas de 65 e 5.000 produtos, relatórios gravados fora do repositório, serviu para encontrar os erros acima. **Eu li os números de validação desse ensaio antes do pré-registro.** Nenhum critério, limite ou consulta foi alterado em função dos números de qualidade; as mudanças pós-ensaio foram o desempate no cliente, BLAS em 1 thread e rótulos de relatório. Um ajuste de consultas foi feito antes do ensaio final de verificação (consultas de sinônimo com nível exigem pelo menos 8 relevantes em 5.000 produtos). O ensaio rodou com outros processos pesados na máquina e seus tempos não valem.

### Limitações declaradas antes da execução

Rótulos sintéticos por atributos (medem generalização neste gerador, não clientes reais); léxicos diferentes em C e D; modelo denso quantizado; abstenção por limiar não calibrada (consultas sem correspondência medem só se algo foi devolvido); vazão com um cliente sequencial; uma máquina de 20 CPUs com Docker local; no 5.000 o Qdrant não usa HNSW.

## 2026-11-04 · S2-catalogo-grande: medição oficial

Pré-registro em `8b83aa8` (critérios em `6564570`); execução com código sem alterações. 4 repetições, quadrado latino, 450 consultas por passe. Duração e ambiente no `report.md`.

### Medições (50.000 produtos, validação)

- **Embeddings ajudam? Não demonstrado.** nDCG@5 de intenção D−A = +0,0011 (IC95% −0,0465 a +0,0523), contra o mínimo de +0,05. Precisão@5 por nome D−A = −0,373: A acerta 100% dos nomes e códigos; D 0,63, C 0,60, B 0,24. Em hit@5 de intenção B e D chegam a 0,60 e C a 0,55 contra 0,53 de A, dentro do ruído.
- **Qdrant se justifica? Não.** C−D em intenção = +0,0379 (atinge o mínimo de +0,03 no ponto, mas o IC95% vai de −0,020 a +0,098) e em nome = −0,025 (abaixo do limite de −0,02). Via latência: D p95 30 ms, longe do limite de 200 ms.
- Latência p95 ponta a ponta: A 36 ms, B 14, C 16, D 30. A piora com o tamanho (p50 2 ms em 5.000, 21 ms em 50.000: FTS5 com OR de todos os termos ordena todos os casamentos); D segue o mesmo custo no ramo lexical. Memória do processo: A 68 MB, B/C ~720 MB, D 755 MB (modelo ONNX); servidor Qdrant ocioso 380 MB (B) e 164 MB (C). Embeddings de 50.000 documentos: 368 s. Disco: Qdrant 191/213 MB, numpy 77 MB, SQLite 44 MB.
- Zero violações de filtro e zero instabilidade em todas; consultas sem correspondência: A devolve algo em 67%, B/C/D em 100% (sem limiar de abstenção). Smoke de 65: A reproduz 0,8/0,75.

### Erros, ressalvas e o que não se conclui

- **O HNSW nunca foi construído.** Nos padrões do servidor (`indexing_threshold` 10.000 KB por segmento, vários segmentos por causa dos 20 CPUs) `indexed_vectors_count` ficou 0 mesmo com 50.000 pontos; a concordância de B com a busca exata é 1,0 porque B também foi exata. A entrada de 2026-11-03 dizia que 50.000 exercitaria o HNSW: estava errada. Medir o índice aproximado exige configuração explícita (fora do protocolo; fica como pendência).
- A queda de precisão por nome nas estratégias com embeddings vem em parte do modelo denso (MiniLM multilíngue dilui códigos de modelo como "KR-48"); a fusão RRF recupera parte do que A acerta. Uma variante com peso maior no ramo lexical não foi testada e não deve ser ajustada sobre estes resultados.
- Rótulos sintéticos por atributos; descrições geradas por frases e 8% sem nível/uso; léxicos de C e D diferentes; um modelo denso quantizado; abstenção não calibrada; vazão sequencial; uma máquina.
- Nenhum vencedor global é declarado. O resultado é: nas condições medidas, os embeddings não melhoraram as consultas por intenção o suficiente e pioraram nome/código; o Qdrant não se justificou, e a pergunta com HNSW real continua aberta.
