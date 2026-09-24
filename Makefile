.PHONY: install run run-http test test-unit lint format type-check check docker-build docker-up docker-down clean

install:
	uv sync

run:
	uv run jev-mcp

run-http:
	JEV_TRANSPORT=streamable-http uv run jev-mcp

test:
	uv run pytest

test-unit:
	uv run pytest -m unit

lint:
	uv run ruff check .

format:
	uv run ruff format .

type-check:
	uv run mypy .

check: lint type-check test

docker-build:
	docker compose build

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down --remove-orphans

clean:
	rm -rf .venv .mypy_cache .pytest_cache .ruff_cache htmlcov dist *.egg-info
