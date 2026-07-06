.PHONY: venv deps run

.venv:
	uv venv -p /bin/python --allow-existing --system-site-packages

venv:	.venv
	@echo "Using .venv"

deps:	venv
	uv sync

run:	deps
	uv run ./superpaste.py

test:	deps
	uv run python -m pytest tests/ -v
