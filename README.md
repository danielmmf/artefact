# Empório da Música — fundação

Fundação da Fase 1 para ingestão local e um fluxo de teste simulado. Python 3.11+ e [uv](https://docs.astral.sh/uv/) são necessários. Após a instalação das dependências, ingestão e testes não usam serviços externos, chave, Docker ou GPU.

```sh
make setup
make ingest
make test
```

A ingestão lê `data/raw/` sem alterá-lo, valida os CSVs, cria `var/store.db` e gera `data/processed/policies.md` e `QUALITY.md`. A leitura de atendimento usa SQLite em modo somente leitura. `var/` e `.env` não são versionados; `.env.example` mostra a configuração. O relatório reproduz os fatos verificados na ADR-000 §13 e deve ser reavaliado se os arquivos oficiais mudarem.

O teste `test_tracer_no_personal_data` exercita a sequência mensagem → `ScriptedLLM` → ferramenta `get_product` → repositório SQLite → resultado → resposta → JSONL. O simulador é determinístico e não representa um LLM real. A tokenização de dados pessoais antes de um LLM real ainda pertence à fase de segurança e não foi implementada. O trace básico usa uma lista restrita de campos e não grava mensagens, argumentos nem resultados.

Esta fundação não implementa busca, todas as regras comerciais, autenticação, adaptador de LLM real nem CLI de atendimento. O contrato completo de `get_product`, o loop e a telemetria completa pertencem às fases posteriores. Os arquivos `.planning/` não foram atualizados; o planejamento e a coordenação permanecem com o Claude/GSD.

A ferramenta Python `quote_payment` consulta os dados atuais por `StoreRepository` e não registra compras. As parcelas e a permissão de pagamento combinado usam o subtotal dos produtos, sem frete, com a base indicada na saída: a ADR não especifica explicitamente a inclusão do frete nessas duas bases, que devem ser confirmadas na revisão. O frete é exibido separadamente; sem valor conhecido, o total com frete é nulo. A indicação `special_quote_required` é consultiva: o produto pode exigir cotação especial.

A busca usa SQLite FTS5/BM25 e fallback rapidfuzz quando não há resultados no índice; filtros de categoria, preço final e disponibilidade são aplicados no SQLite. Depois de `make setup`, execute `make bench` sem rede para gerar `evals/reports/search.json`. Com os dez casos rotulados atuais, a medição local foi recall@5 **0,800** e MRR **0,750**; o conjunto pequeno e seus rótulos não exaustivos não demonstram generalização. O trace do agente ainda não registra o backend da busca: a integração pertence à fase do agente.

O frete reconhece Campo Grande e Campo Grande/MS. Falhas SQLite em `quote_payment` produzem erro genérico. As hipóteses de subtotal sem frete para parcelas e pagamento combinado, arredondamento HALF_UP por unidade e distribuição de centavos nas primeiras parcelas permanecem sujeitas à decisão comercial.
