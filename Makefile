.PHONY: setup ingest test
setup:
	uv sync --locked --extra dev --extra lab
ingest:
	uv run --locked emporio ingest
test:
	uv run --locked --extra dev --extra lab pytest

.PHONY: bench
bench: ingest
	uv run --locked python -m emporio.search_bench

.PHONY: chat eval eval-strict scenario scenario-list
chat:
	uv run --locked emporio chat

eval:
	uv run --locked python -m emporio.eval_runner

eval-strict:
	uv run --locked python -m emporio.eval_runner --strict

scenario:
	@test -n "$(S)" || { echo "Uso: make scenario S=<nome>  (veja make scenario-list)"; exit 2; }
	uv run --locked --extra lab emporio-lab scenario run $(S)

scenario-list:
	uv run --locked --extra lab emporio-lab scenario list
