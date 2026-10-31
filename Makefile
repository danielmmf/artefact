.PHONY: setup ingest test
setup:
	uv sync --locked --extra dev
ingest:
	uv run --locked emporio ingest
test:
	uv run --locked --extra dev pytest

.PHONY: bench
bench: ingest
	uv run --locked python -m emporio.search_bench
