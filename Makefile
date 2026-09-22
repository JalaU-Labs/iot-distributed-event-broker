.PHONY: help up down logs test lint format typecheck pre-commit install clean

help:
	@echo "Available commands:"
	@echo "  make up          - Start Docker Compose services"
	@echo "  make down        - Stop Docker Compose services"
	@echo "  make logs        - Show Docker Compose logs"
	@echo "  make test        - Run tests with coverage"
	@echo "  make lint        - Run ruff and mypy"
	@echo "  make format      - Format code with ruff"
	@echo "  make typecheck   - Run mypy"
	@echo "  make pre-commit  - Run pre-commit hooks"
	@echo "  make install     - Install pre-commit hooks"
	@echo "  make clean       - Remove caches"

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run mypy src tests

format:
	uv run ruff format .

typecheck:
	uv run mypy src tests

pre-commit:
	uv run pre-commit run --all-files

install:
	uv run pre-commit install

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
