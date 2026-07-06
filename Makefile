.PHONY: venv deps run test

.venv:
	uv venv -p /bin/python --allow-existing --system-site-packages

venv:	.venv
	@echo "Using .venv"

deps:	venv
	uv sync --extra test

run:	deps
	uv run ./superpaste.py

test:	deps
	uv run python -m pytest tests/ -v