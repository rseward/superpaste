.PHONY: venv deps run

venv:
	uv venv -p /bin/python --allow-existing --system-site-packages

deps:
	uv sync

run:
	uv run ./superpaste.py
