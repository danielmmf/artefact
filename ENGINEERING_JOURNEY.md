# Engineering Journey — Empório AI

> **Caso técnico e retrospectiva da implementação do agente da Empório da Música para o desafio de AI Engineer da Artefact.**  
> **Estado documentado:** release `v1.0.2`, commit `47f58e6edb1486289bfef7b660182cfd0384bdcc`, publicada em 2 de novembro de 2026.  
> **Escopo deste documento:** registro do projeto **executado**. O laboratório de frameworks ao final é uma **proposta experimental**, ainda não um resultado.

## 1. O problema e o objetivo

O desafio era construir um agente conversacional de atendimento, em português, para uma loja fictícia de instrumentos musicais. O agente precisava usar dados estruturados de produtos, clientes, pedidos e promoções, além de interpretar as políticas de um manual em PDF. O maior risco não era produzir uma resposta fluente: era afirmar preço, estoque, status, regra comercial ou acesso a pedido sem evidência confiável.

Adotamos como prioridades a reprodutibilidade por quem clonasse o repositório, o isolamento das regras de negócio em código testável, a proteção de dados de clientes e a capacidade de explicar as escolhas em uma entrevista técnica. As metas quantitativas de avaliação foram **critérios internos do projeto**, não notas atribuídas pela Artefact.

## 2. Arquitetura escolhida e suas razões

### 2.1 Loop próprio de *function calling* (DEC-01)

A solução usa um `ConversationEngine` em Python para orquestrar chamadas de ferramentas feitas por um LLM via protocolo compatível com a API de chat completions da OpenAI. O mecanismo expõe **oito ferramentas** com contratos Pydantic e permite até cinco iterações por turno. O modelo decide quando pedir informações; o Python executa consultas, cálculos, valida argumentos e autoriza o acesso a pedidos.

**Por que não adotamos PydanticAI ou LangGraph na v1?** O escopo era pequeno, com um fluxo predominantemente linear, e o prazo era curto. Um loop próprio deixava explícitos autorização, orçamento de contexto, tratamento de erros e execução das ferramentas. Essa foi uma **decisão de escopo**, não uma demonstração de que frameworks seriam inferiores em qualidade, produtividade ou segurança. O custo assumido foi implementar e manter mais infraestrutura de orquestração por conta própria.

### 2.2 Dados determinísticos antes da resposta do LLM

O catálogo e os pedidos são carregados dos CSVs para um banco SQLite de loja, acessado em modo somente leitura. Outro SQLite guarda estado operacional como sessões, histórico, tentativas de acesso e tickets. Preços, promoções, descontos, parcelas e frete são determinados pelas regras de Python; o LLM não deve calculá-los por conta própria. Dinheiro é tratado em centavos inteiros, com `Decimal` na representação, para evitar erros de ponto flutuante.

Para busca de produtos, a solução combina SQLite FTS5/BM25, filtros SQL exatos e `rapidfuzz` como fallback. A medição local publicada, com apenas dez consultas, foi **recall@5 = 0,800** e **MRR = 0,750**; não é uma comprovação de qualidade em qualquer catálogo.

### 2.3 Manual no contexto, sem RAG

O manual institucional de oito páginas é extraído para Markdown com referências de seção e página e enviado inteiro ao prompt. No volume atual, isso reduz o risco de uma recuperação parcial omitir a regra relevante. Essa escolha consome aproximadamente quatro mil tokens por turno e seria reavaliada num manual maior; não significa rejeitar RAG em geral.

### 2.4 Segurança: autorização não é decisão do modelo

A consulta de um pedido exige autorização verificada em Python. Existe confirmação **demonstrativa** de posse por número do pedido e contato cadastrado; o parâmetro `--customer` da CLI permite escolher uma identidade simulada. **Isso não autentica uma pessoa real.** E-mails e telefones reconhecidos são tokenizados antes de seguir ao provedor, com mapa em memória por sessão; traces são orientados a metadados. Esses mecanismos reduzem riscos, mas não constituem uma garantia geral de privacidade nem substituem autenticação e análise LGPD para produção.

## 3. Como o trabalho realmente aconteceu

1. **Arquitetura e especificação.** As alternativas foram debatidas e consolidadas na ADR-000 e em `docs/DECISIONS.md`, incluindo regras de parcelamento, frete, devoluções, verificação de pedidos e como tratar inconsistências dos dados.
2. **Planejamento.** Os artefatos do GSD ajudaram a estruturar requisitos e roadmap. As fases de implementação, porém, **não foram executadas pelo GSD do início ao fim**. A execução envolveu código produzido por diferentes agentes e integração/revisão subsequente pelo Claude Code; os commits e a matriz de aceite são a evidência apropriada.
3. **Implementação do núcleo.** Ingestão, persistência SQLite, oito ferramentas, regras comerciais, CLI, testes sem chave externa e benchmark de busca.
4. **Integração do LLM real.** A alternativa Groq `gpt-oss-120b` foi experimentada, mas os limites do plano disponível restringiam as avaliações. A implementação passou a usar `deepseek-chat` como padrão, preservando o adaptador compatível com outros provedores.
5. **Rodadas de avaliação e correção.** O golden set revelou chamadas de ferramenta ausentes, valores sem respaldo, saídas de contingência e falhas do próprio avaliador. As correções foram registradas em vez de apagar rodadas desfavoráveis.
6. **Holdout e revisão independente.** Um conjunto separado de oito casos foi registrado antes da primeira execução. Suas respostas originais foram preservadas, mesmo após se descobrirem problemas nas verificações automáticas e uma afirmação comercial realmente indevida.
7. **Releases.** `v1.0-mvp` é o marco anterior; `v1.0` consolidou a entrega; `v1.0.1` distinguiu `make eval` de `make eval-strict`; `v1.0.2` corrigiu detecção de formatos de telefone e sua colisão com datas e horários. As tags históricas foram preservadas.

**Nota de proveniência:** esta sequência resume os artefatos e releases publicados; não pretende atribuir a cada assistente todas as linhas ou etapas de código. A seção “Uso de assistentes de IA” do README identifica a colaboração e sua natureza.

## 4. Avaliação: o que os números mostram — e o que não mostram

| Evidência publicada | Resultado | Leitura correta |
| --- | --- | --- |
| CI da `v1.0.2` | **368 testes passando** | Cobertura de cenários implementados, sobretudo regras e regressões offline; não garante ausência de defeitos |
| Busca | **recall@5 0,800; MRR 0,750** | Mini-eval local de dez consultas |
| Golden set final registrado (código `3391bfd`) | **17/17 casos passaram nas verificações automáticas** | Regex, checagem de valores e chamadas de ferramentas; não valida toda a semântica da resposta |
| Seleção de ferramentas — leitura estrita | **75% (9/12), contra meta interna ≥90%** | Meta interna não atingida; resultado mantido sem reclassificação retroativa |
| Leitura secundária de ferramentas | **100% ao desconsiderar casos 09, 10 e 14** | Análise explicativa; **não substitui** a medida estrita nem prova perfeição |
| Holdout original, pré-ajuste | **6/8 casos passaram nas verificações** | Execução original independente; resultado preservado |
| Conversas demonstrativas | **Cinco transcrições com LLM real** | Mostram o fluxo; não representam ensaio estatístico de produção |

### Por que 75%, se o agente agiu corretamente nos três casos?

A meta de 90% foi definida **internamente** na especificação, não pela Artefact. Doze casos exigiam alguma ferramenta segundo os rótulos originais; a ferramenta exigida foi chamada em nove. Os casos 09, 10 e 14 foram escritos esperando uma ferramenta quando faltava argumento essencial: respectivamente contato para confirmar posse, número de pedido para devolução e número de pedido para acesso de terceiros. Solicitar os dados ou recusar foi o comportamento prudente. A métrica estrita, porém, penalizou essas respostas. Mantivemos o resultado histórico de 75%, sem mudar os rótulos após observar as saídas.

**Lição de avaliação:** o laboratório deve medir separadamente (a) necessidade de chamar ferramenta, (b) escolha correta da ferramenta quando executável, (c) pedido correto de esclarecimento e (d) recusa/autorização. O novo instrumento de medição precisa ser especificado **antes** das novas execuções. As avaliações históricas devem permanecer imutáveis, inclusive quando um erro de avaliação for reconhecido.

### O aprendizado do holdout

A avaliação original de oito casos registrou 6/8. Uma verificação interpretou incorretamente negações, e outra não detectou uma afirmação realmente não suportada: que a loja não faria serviços de conserto. A reavaliação offline das **mesmas respostas** e a reexecução posterior foram publicadas separadamente. A reexecução depois das correções **não é uma nova validação independente**. Os casos também mostraram que uma resposta composta pode estar informativamente correta e ainda deixar de chamar uma ferramenta esperada.

## 5. Falhas encontradas e correções que mudaram o projeto

- **Evidência monetária insuficiente.** O validador inicial aceitava valores do manual sem considerar adequadamente o contexto. Foi endurecido para conferir resultados de ferramentas do turno, faixas de preço informadas pelo cliente e contexto de regras do manual. Persistiu uma limitação conhecida: um preço de produto pode coincidir com um valor permitido pelo manual numa frase sobre o tema correto.
- **Qualidade do próprio avaliador.** Verificações por regex aceitaram algumas respostas semanticamente erradas; foram adicionados testes de mutação e tratamento de negações. A limitação geral de usar heurísticas permanece.
- **Proteção de contato versus dados legítimos.** Separadores Unicode e, depois, `:`, `/` e `_` em telefones exigiram correções. O detector anterior também confundia datas com horários com telefones ou bloqueava o turno. A `v1.0.2` acrescentou regressões para essas situações, inclusive contra os 50 telefones do CSV, chegando aos 368 testes. Telefones sem DDD ou em formatos atípicos ainda podem seguir em claro; números não telefônicos que parecem telefones válidos podem ser tokenizados.
- **Fluxo de atendimento.** O modelo foi orientado a consultar ferramentas em vez de calcular parcelas ou preços, informar totais de listagens, evitar códigos de verificação inexistentes e não afirmar que um ticket local já chegou a uma equipe humana.
- **Confiabilidade da avaliação executável.** A `v1.0.1` passou a usar `make eval` para executar e gravar o relatório mesmo quando uma meta falha (código 0 em execução válida), e `make eval-strict` como gate de metas. Falhas reais de configuração ou infraestrutura continuam diferenciadas.

## 6. Limites da v1: demo sólida não é produto de produção

- **Identidade:** `--customer` é simulação selecionável na CLI; contato + pedido não prova identidade real.
- **Privacidade:** tokenização heurística não detecta todos os contatos; o texto remanescente segue ao provedor externo, com avaliação LGPD pendente para uso real.
- **Informações:** validador de valores monetários não garante que nomes, especificações ou afirmações de política estejam corretos.
- **Encaminhamento:** `escalate_to_human` registra um protocolo local; não entrega um ticket a uma pessoa, fila ou sistema externo.
- **Operação:** bloqueio persistente após tentativas falhas não possui desbloqueio automático; o manual inteiro é reenviado a cada turno.
- **Variabilidade:** `temperature=0` não torna as respostas de um provedor LLM perfeitamente reprodutíveis.

Esses limites são parte explícita da entrega. Não devem ser apagados de uma apresentação ou confundidos com requisitos já resolvidos.

## 7. O próximo passo: laboratório de frameworks (**proposto, não executado**)

### Pergunta de pesquisa

> **O loop próprio foi a escolha mais simples e defensável para este caso, ou um framework como PydanticAI teria reduzido o custo de desenvolvimento/manutenção sem perder controle, segurança e reprodutibilidade?**

### Hipóteses a testar

**H1:** PydanticAI pode reduzir código de orquestração e oferecer ferramentas de teste e injeção de dependências mais convenientes, sem mudar regras de negócio. **H2:** o loop próprio pode ter menos dependências, menor overhead e melhor previsibilidade para este fluxo linear. **H3:** LangGraph só trará ganho material se incluirmos fluxos com estado persistente, pausas, recuperação de falhas e aprovação humana; não deve ser imposto a um problema que não exige esses recursos.

### Desenho experimental para evitar comparação injusta

1. **Baseline congelado:** usar o código `v1.0.2` como referência somente leitura; não mudar release ou relatórios históricos.
2. **Mesmo domínio:** reutilizar exatamente os mesmos dados sintéticos, as oito ferramentas/contratos, políticas, relógio, permissões e regras comerciais; comparar a camada de orquestração, não reescrever regras em cada variante.
3. **Primeiro, testes offline:** construir casos determinísticos com LLM falso/modelo de teste e falhas injetadas (dados ausentes, ferramenta recusada, preço incorreto, timeout e privacidade).
4. **Depois, comparação real controlada:** somente após autorização para usar chave e orçamento, rodar as variantes com o mesmo provedor/modelo/parâmetros, múltiplas repetições e registro de custo e latência.
5. **Duas avaliações separadas:** conservar golden e holdout históricos como material de comparação retrospectiva, sem rebatizá-los como “novos testes cegos”; criar e congelar um **novo conjunto inédito** antes de testar o modelo real.
6. **Indicadores:** acerto funcional, chamada correta de ferramenta, esclarecimento quando faltam argumentos, bloqueio de acesso não autorizado, fundamentação de valores, vazamento de contatos, contingências, latência, custo, dependências diretas e linhas de orquestração. Manutenção e legibilidade exigem revisão qualitativa, não apenas contagem de linhas.
7. **Terceira variante condicional:** avaliar LangGraph apenas se houver um cenário concreto de retomada/checkpoint/human-in-the-loop no qual possa demonstrar uma vantagem própria.

### Critérios para uma conclusão honesta

O relatório deve explicar **em quais cenários** cada solução ganhou, perdeu ou empatou; apresentar a versão exata das dependências; separar medições reproduzíveis de impressões; não usar testes ajustados depois das respostas como validação independente; e não declarar framework vencedor antes dos resultados.

## 8. Referências verificáveis

- [Código entregue — `v1.0.2`](https://github.com/danielmmf/artefact/tree/v1.0.2)
- [Release `v1.0.2` e limitações do patch](https://github.com/danielmmf/artefact/releases/tag/v1.0.2)
- [README original da entrega](https://github.com/danielmmf/artefact/blob/v1.0.2/README.md)
- [Decisões registradas — DEC-01 a DEC-11](https://github.com/danielmmf/artefact/blob/v1.0.2/docs/DECISIONS.md)
- [Especificação consolidada — ADR-000](https://github.com/danielmmf/artefact/blob/v1.0.2/docs/adr/ADR-000-especificacao-consolidada.md)
- [Baseline de avaliação e relatórios](https://github.com/danielmmf/artefact/blob/v1.0.2/evals/reports/baseline.md)
- [Conjunto golden de 17 casos](https://github.com/danielmmf/artefact/blob/v1.0.2/evals/golden_set.json)
- [Holdout de oito casos](https://github.com/danielmmf/artefact/blob/v1.0.2/evals/holdout_set.json)
- [Documentação oficial do PydanticAI](https://pydantic.dev/docs/ai/overview/) e [testes com modelos simulados](https://pydantic.dev/docs/ai/guides/testing/)
- [Documentação de persistência do LangGraph](https://docs.langchain.com/oss/python/langgraph/persistence)

---

**Síntese:** a v1 é uma entrega técnica demonstrável, com decisões explícitas e limitações honestamente reportadas. O laboratório não existe para reescrever essa história ou produzir números melhores; existe para descobrir, com critérios fixos e evidências reproduzíveis, se faríamos escolhas diferentes numa segunda implementação.
