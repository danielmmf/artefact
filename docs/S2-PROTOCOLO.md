# S2 · Protocolo: Qdrant × SQLite FTS5 com o catálogo crescendo

Documento pré-registrado junto com `scenarios/S2-catalogo-grande.yaml`. Os critérios e os parâmetros vivem no YAML; este texto explica como os dados, os rótulos e a medição foram construídos. Nada aqui é ajustado depois de ver resultados.

## 1. Pergunta

Duas perguntas separadas, na escala de 50.000 produtos:

1. **Os embeddings ajudam?** Estratégia D (SQLite FTS5 + embeddings em numpy + RRF) contra A (a busca original da v1.0.2).
2. **O Qdrant se justifica?** Estratégia C (Qdrant híbrido) contra D. Se D empatar com C, o registro é: os embeddings valem a pena e o Qdrant ainda não.

Não se parte da premissa de que o Qdrant é necessário. A estratégia B (Qdrant só denso) é medida como referência de qualidade e custo; não entra em nenhuma das duas decisões.

## 2. Estratégias

| | Recuperação | Banco | Léxico | Vetores |
| --- | --- | --- | --- | --- |
| A | original da v1.0.2 (`SQLiteRepository.search_product_ids`, sem alteração) | SQLite | FTS5/BM25 `unicode61`, fallback RapidFuzz | — |
| B | Qdrant Server, vetor denso (HNSW padrão, cosseno) | Qdrant | — | MiniLM multilíngue, 384 dim |
| C | Qdrant Server, Query API: prefetch denso + prefetch esparso BM25, fusão RRF no servidor | Qdrant | `Qdrant/bm25` do FastEmbed, **stemmer e stopwords em português** (verificado no código: `SnowballStemmer('portuguese')` e lista de stopwords portuguesa), IDF no servidor | idem |
| D | FTS5/BM25 do SQLite (mesma consulta de A, com LIMIT, sem o fallback RapidFuzz) + produto escalar exato em numpy + RRF no processo | SQLite + `.npy` | FTS5 | idem |

- Modelo denso: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` via FastEmbed (ONNX quantizado `qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q`), 384 dimensões, licença Apache-2.0, 0,22 GB, ~50 idiomas, vetores normalizados em L2. Versões exatas de FastEmbed, qdrant-client, onnxruntime e numpy ficam no pré-registro. O download do modelo e das dependências é a única atividade de rede; indexação e consultas são locais.
- Qdrant Server `1.20.0` em Docker, imagem fixada por digest (`docker/qdrant/s2-servers.sh`), um contêiner por estratégia (B e C) para medir RAM e disco de cada uma. Modo local em processo não é usado. HNSW com parâmetros padrão do servidor.
- RRF: `score = Σ 1/(k + posição)` sobre os ramos, o mesmo `k` e a mesma profundidade por ramo em C e D (Qdrant `Rrf(k=…)`; implementação própria em D).
- BLAS com 1 thread nos processos de medição: num microbenchmark anterior ao pré-registro, o produto escalar de 50.000×384 levou 2,3 ms com 1 thread contra 4,2–5,3 ms com mais threads depois de carregar o ONNX Runtime (contenção entre pools de threads). Vale para todas as estratégias.
- **Confusão conhecida e declarada:** o ramo lexical de C (BM25 com stemming) e o de D (FTS5 sem stemming) são diferentes. Parte de uma diferença C−D pode ser do léxico e não do Qdrant. Não há variante para separar os dois; a limitação fica registrada.

## 3. Escalas

| Escala | Produtos | Papel |
| --- | --- | --- |
| smoke65 | 65 (catálogo original) | verificação de integridade; recall@5 e MRR contra a v1 (0,8 e 0,75) |
| catalogo5k | 5.000 | escolha de configuração (desenvolvimento) e leitura intermediária |
| catalogo50k | 50.000 | **decisão** |

Abaixo de ~10 MB de vetores densos o Qdrant não constrói HNSW (limiar padrão de indexação): em 5.000 produtos (7,7 MB) B e C varrem os vetores sem grafo; o grafo só existe em 50.000. O relatório traz a contagem de vetores indexados que o Qdrant informa por escala.

## 4. Catálogo sintético

Gerado por `src/emporio_lab/s2/catalog.py` com seed fixa, a partir de **atributos estruturados**: categoria, tipo (36 tipos em 9 categorias), nível (iniciante, intermediário, avançado, profissional), uso (estudo, palco, gravação, silencioso, viagem, igreja, infantil), faixa de preço (4), disponibilidade (70% disponível, 15% esgotado, 15% descontinuado) e promoção (6%). Marcas fictícias. Nome e descrição são derivados dos atributos por frases de um léxico (`lexicon.py`), com 8% das descrições omitindo o nível e 8% omitindo o uso (ruído realista: o rótulo vale mesmo sem o texto dizer).

- Séries de 2 a 8 variantes (acabamentos) com a mesma marca, tipo e nível e usos que podem variar: candidatos difíceis de distinguir pelo vocabulário de tipo.
- O catálogo de 5.000 é o prefixo do de 50.000; o produto `i` é o mesmo nos dois. Nada é copiado dos 65 produtos originais.
- IDs estáveis: `product_id` do SQLite (a partir de 1001) é o ID do ponto no Qdrant.
- O SQLite sintético tem o mesmo esquema e o mesmo FTS5 (`name, description, category`) da v1.

## 5. Consultas e rótulos

450 consultas em 7 grupos (contagens no YAML), geradas por `queries.py`. **A relevância é um predicado sobre atributos, não sobre texto.**

- Ganho 2: satisfaz o predicado completo e os filtros; ganho 1: predicado parcial; 0: o resto. Filtros (categoria, preço final máximo, disponibilidade) fazem parte da relevância e são avaliados contra o **estado atual** do SQLite.
- Grupos: `nome_codigo` (nome completo, série, código do modelo), `digitacao` (mutações determinísticas de nomes/séries/tipo+marca; a palavra errada nunca é uma palavra válida do catálogo), `intencao`, `sinonimos`, `ambiguas` (marca, acabamento ou só o nome do instrumento), `filtros` (categoria, preço, disponibilidade) e `sem_correspondencia`.
- Toda consulta tem pelo menos 8 produtos de ganho 2 já no catálogo de 5.000. Consultas por nome usam só os 4.000 primeiros produtos, então valem nas duas escalas.
- **Desenvolvimento × validação:** cada grupo é embaralhado com seed e dividido 50/50. A configuração (§7) é escolhida só no desenvolvimento; toda decisão usa só a validação.

### 5.1 Como a separação de vocabulário foi garantida

As consultas de intenção são montadas com frases de nível e uso (`LEVEL_QUERY`, `USE_QUERY`) escritas à parte das frases que as descrições usam (`LEVEL_DESC`, `USE_DESC`, mais as frases de preço, trechos fixos e ruído). Duas verificações automáticas (`vocab.py`, testes em `tests/test_s2_*.py` e nova execução no pré-registro):

1. **Fonte:** nenhum radical de conteúdo (stemmer Snowball português, sem stopwords) de uma frase de consulta aparece em qualquer frase que o gerador pode escrever numa descrição; nenhum sinônimo de tipo reaproveita os radicais do termo do tipo no catálogo.
2. **Realizada:** nenhum radical dessas frases aparece no vocabulário (nomes e descrições) do catálogo efetivamente gerado de 50.000.

Exceções declaradas, em lista fixa de radicais (`ALLOWED_STEMS`): as palavras do domínio impossíveis de evitar (música, instrumento, tocar, cordas) e os substantivos que nomeiam a família do instrumento (guitarra, violão, flauta, piano, teclado). Sem citar o instrumento nenhuma consulta é possível. Os **sinônimos de tipo** são verificados só na camada 1 (não repetem o termo do tipo): como são frases curtas, também usam palavras genéricas que existem no catálogo ("grave", "escala"); a fração média de radicais de sinônimos presentes no vocabulário é registrada no relatório (informativa, não é critério).

## 6. Métricas

Com milhares de relevantes por consulta, recall@5 não discrimina; por isso, na escala grande:

- **Precisão@5** = resultados de ganho 2 no top-5 ÷ min(5, total de ganho 2 no catálogo) (normalizada para consultas com menos de 5 relevantes).
- **nDCG@5** com ganho linear (0/1/2) e ideal calculado pelas contagens do catálogo.
- **Hit@5** = algum ganho 2 no top-5.
- Também: consultas com resposta possível que devolveram lista vazia; fração de consultas `sem_correspondencia` que devolvem algum resultado; violações de filtro; instabilidade do top-5 entre repetições.
- **Recall@5 e MRR** só no smoke de 65 produtos, com as 10 consultas rotuladas da v1 (`evals/search_queries.yaml`).
- Deltas de decisão: média por consulta da diferença entre estratégias, IC95% por bootstrap pareado (2.000 reamostragens, seed fixa) sobre as consultas de validação.

## 7. Configuração (desenvolvimento)

Grade: `rrf_k` ∈ {10, 60} × profundidade por ramo ∈ {50, 100, 200}; 30 candidatos vão à camada SQLite. A regra de escolha está no YAML (sobre o desenvolvimento, escala de 5.000, estratégia D); a mesma configuração vale para C.

## 8. Medição

- Um processo novo por (estratégia, repetição): constrói a estratégia, executa **1 consulta fria** (inclui carregar modelo e conectar), 1 passe de aquecimento sem medir, e 1 passe medido com todas as consultas. Índices prontos antes de começar.
- 4 repetições; a ordem das estratégias segue um quadrado latino (cada estratégia em cada posição uma vez).
- Latência: embedding da consulta (denso e esparso), consulta ao índice (inclui ida e volta ao servidor em B e C, e a consulta FTS5 em D), confirmação no SQLite, e ponta a ponta. p50 e p95 sobre todas as repetições.
- Vazão: consultas por segundo de um cliente sequencial (não mede concorrência).
- RAM: pico (VmHWM) do processo de busca + RSS do contêiner Qdrant após reiniciá-lo com só a coleção da escala carregada (`docker stats`). Disco: uso real dos arquivos (blocos alocados) de cada índice.
- Tempo de indexação: embeddings (denso, esparso), SQLite+FTS5, upload e índice pronto em cada Qdrant.

## 8.1 Ordem de empate (achado do ensaio de desenvolvimento)

Num ensaio de desenvolvimento (antes do pré-registro, sem alterar critério algum), a busca híbrida do Qdrant 1.20.0 devolveu ordens diferentes para a mesma consulta no mesmo índice em 91 de 450 consultas (empates de score no RRF). Por isso B e C reordenam os candidatos no cliente por `(-score, id)`, a mesma regra de desempate de D e da v1. O critério `instabilidade_top5` continua valendo; o comportamento sem desempate fica registrado aqui e no diário.

## 9. Integração

O Qdrant devolve só IDs candidatos. `strategies.hydrate` consulta `SQLiteRepository.get_product` e `get_product_pricing` (camada original) para cada candidato, reaplica categoria, disponibilidade e faixa de preço ao preço final promocional **atual** e descarta o que não vale mais. O payload do Qdrant (categoria, preço no momento da indexação, disponibilidade) serve só de pré-filtro. O relatório inclui uma demonstração: depois da indexação, um produto é esgotado e outro muda de preço numa cópia do SQLite; B, C e D passam a refletir o SQLite. Nada de autorização de pedido existe no banco vetorial.

## 10. Critérios de decisão

Os números estão no YAML, avaliados na escala de 50.000, validação:

- **Embeddings ajudam** quando D−A em nDCG@5 de intenção é pelo menos +0,05 **e** o limite inferior do IC95% é positivo **e** a precisão@5 por nome não cai mais que 0,02, e D cumpre os limites operacionais (p95 ponta a ponta ≤ 200 ms, 0 violações de filtro, instabilidade ≤ 1%).
- **O Qdrant se justifica** se os embeddings ajudam **e** (via qualidade: C−D em nDCG@5 de intenção ≥ +0,03 com IC95% inferior positivo, sem queda de precisão por nome além de 0,02 e C dentro dos limites; **ou** via latência: D acima de 200 ms de p95 e C dentro).
- Se o ganho de D sobre A atinge o mínimo no ponto mas o IC inclui zero: **inconclusivo**.
- Caso contrário: sem evidência suficiente; nenhum vencedor é declarado. Latência, memória, disco e operação são relatados lado a lado, mas só os limites acima entram na decisão.
- Smoke: A precisa reproduzir recall@5 = 0,8 e MRR = 0,75 (a mesma busca da v1 sobre a mesma base).

## 11. Pré-registro e ordem dos fatos

1. Este protocolo, o YAML, o gerador, o código e os testes são commitados.
2. `emporio-lab scenario preregister S2-catalogo-grande` grava `reports/scenarios/S2-catalogo-grande/preregistration.json` (commit dos critérios, hash dos arquivos congelados, hash do catálogo de 5.000 e de 50.000, hash das consultas e da divisão (as consultas rotuladas estão em `evals/s2_consultas.json`), versões e modelos) e é commitado.
3. Só então `make scenario S=S2-catalogo-grande`, que recusa rodar se o registro não for posterior aos critérios, se os arquivos congelados divergirem, se o catálogo/consultas gerados hoje não baterem com os hashes ou se o código tiver alterações.

## 12. Não versionado

Catálogos gerados, embeddings, dados do Qdrant, modelos baixados e caches ficam em `var/s2/` e no cache do FastEmbed (fora do Git). Versionados: gerador com seed, hashes, consultas rotuladas (regeneradas deterministicamente e verificadas por hash), YAML, este protocolo, o script do Qdrant Server com versão e digest, código, testes e relatórios.
