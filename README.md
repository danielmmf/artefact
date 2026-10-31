# Empório da Música — fundação

Fundação da Fase 1 para ingestão local e um fluxo de teste simulado. Python 3.11+ e [uv](https://docs.astral.sh/uv/) são necessários. Após a instalação das dependências, ingestão e testes não usam serviços externos, chave, Docker ou GPU.

```sh
make setup
make ingest
make test
```

A ingestão lê `data/raw/` sem alterá-lo, valida os CSVs, cria `var/store.db` e gera `data/processed/policies.md` e `QUALITY.md`. A leitura de atendimento usa SQLite em modo somente leitura. `var/` e `.env` não são versionados; `.env.example` mostra a configuração. O relatório reproduz os fatos verificados na ADR-000 §13 e deve ser reavaliado se os arquivos oficiais mudarem.

O teste `test_tracer_no_personal_data` exercita a sequência mensagem → `ScriptedLLM` → ferramenta `get_product` → repositório SQLite → resultado → resposta → JSONL. O simulador é determinístico e não representa um LLM real. O trace básico usa uma lista restrita de campos e não grava mensagens, argumentos nem resultados.

Esta fundação não implementa busca, regras comerciais completas, autenticação, adaptador de LLM real nem CLI de atendimento. O contrato completo de `get_product`, o loop e a telemetria completa pertencem às fases posteriores. Os arquivos `.planning/` não foram atualizados; o planejamento e a coordenação permanecem com o Claude/GSD.
