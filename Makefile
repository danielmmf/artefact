.PHONY: setup ingest test
setup:
	uv sync --locked --extra dev
ingest:
	uv run --locked emporio ingest
test:
	uv run --locked --extra dev pytest
